import asyncio
import logging
from pathlib import Path
from ..config import settings
from ..database import Session, Transcript
from .media import run_ffmpeg
from ..detection.runtime import signals

log = logging.getLogger(__name__)

class TranscriptionEngine:
    def __init__(self):
        self.model = None
        self.status = 'not_loaded'
        self.error = ''
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=12)
        self.pending: dict[str, int] = {}

    def can_enqueue(self, stream_id):
        return not self.queue.full() and self.pending.get(stream_id, 0) < 6

    def enqueue(self, path, stream_id, offset):
        self.queue.put_nowait((path, stream_id, offset))
        self.pending[stream_id] = self.pending.get(stream_id, 0) + 1

    def load(self):
        from faster_whisper import WhisperModel
        self.status = 'loading'
        self.model = WhisperModel(settings.whisper_model, device=settings.whisper_device,
                                  compute_type='int8', cpu_threads=settings.whisper_threads,
                                  download_root=str(settings.storage_dir / 'models'))
        self.status = 'ready'
        self.error = ''

    def transcribe(self, path: Path, stream_id: str, offset: float):
        if self.model is None:
            self.load()
        wav = path.with_suffix('.wav')
        try:
            run_ffmpeg(['-i', str(path), '-vn', '-ac', '1', '-ar', '16000', str(wav)])
            segments, info = self.model.transcribe(str(wav), beam_size=1, vad_filter=True)
            parts = []
            with Session.begin() as db:
                for segment in segments:
                    parts.append({'start': offset + segment.start, 'end': offset + segment.end,
                                  'text': segment.text.strip()})
                    db.add(Transcript(stream_id=stream_id, start=offset + segment.start,
                                      end=offset + segment.end, text=segment.text.strip()))
            try:
                signals.observe(stream_id, parts, info.language or '*')
            except Exception:
                log.exception('DETECTION_SIGNALS_FAILED')
            self.status = 'ready'
            self.error = ''
        finally:
            wav.unlink(missing_ok=True)

    async def worker(self):
        while True:
            path, stream_id, offset = await self.queue.get()
            try:
                for attempt in range(2):
                    try:
                        await asyncio.to_thread(self.transcribe, path, stream_id, offset)
                        break
                    except Exception as exc:
                        self.status, self.error = 'error', str(exc)[:300]
                        log.exception('TRANSCRIPTION_FAILED')
                        if attempt == 0:
                            await asyncio.sleep(3)
            finally:
                path.unlink(missing_ok=True)
                remaining = self.pending.get(stream_id, 1) - 1
                if remaining:
                    self.pending[stream_id] = remaining
                else:
                    self.pending.pop(stream_id, None)
                self.queue.task_done()
