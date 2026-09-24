import asyncio
import logging
import shutil
import subprocess
import time
import threading
import uuid
from ..config import settings, ffmpeg
from ..database import Session, Stream
from .buffer import CircularBuffer
from .media import CREATE_NO_WINDOW, analyze
from .clips import ClipGenerator
from .transcription import TranscriptionEngine
from ..detection.runtime import signals

log = logging.getLogger(__name__)

class StreamManager:
    def __init__(self, transcription=None):
        self.process = None
        self.task = None
        self.state = 'idle'
        self.error = ''
        self.info = None
        self.stream_id = None
        self.started = 0
        self.elapsed = 0.0
        self.media_time = 0.0
        self.dropped_segments = 0
        self.buffer = None
        self.transcription = transcription or TranscriptionEngine()
        self.clips = ClipGenerator()
        self.lock = asyncio.Lock()

    async def start(self, url):
        async with self.lock:
            if self.state in ('starting', 'live', 'stopping'):
                raise ValueError('Ya existe una captura activa.')
            self.state, self.error = 'starting', ''
            try:
                if shutil.disk_usage(settings.storage_dir).free < 512 * 2**20:
                    raise ValueError('Se necesitan al menos 512 MB libres para capturar.')
                if self.buffer:
                    shutil.rmtree(self.buffer.directory, ignore_errors=True)
                self.info = await asyncio.to_thread(analyze, url)
                self.stream_id = uuid.uuid4().hex
                signals.reset(self.stream_id)
                directory = settings.storage_dir / 'buffer' / self.stream_id
                directory.mkdir()
                self.buffer = CircularBuffer(directory, settings.buffer_minutes * 60)
                with Session.begin() as db:
                    db.add(Stream(id=self.stream_id, title=self.info['title'], url=url))
                headers = ''.join(f'{k}: {v}\r\n' for k, v in self.info['headers'].items()
                                  if '\n' not in str(v) and '\r' not in str(v))
                codecs = (['-c', 'copy'] if settings.capture_mode == 'copy' else
                          ['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '25', '-threads', '2',
                           '-vf', f'scale=-2:min(ih\\,{settings.capture_max_height})',
                           '-pix_fmt', 'yuv420p', '-force_key_frames', 'expr:gte(t,n_forced*5)', '-c:a', 'aac'])
                command = [ffmpeg(), '-hide_banner', '-loglevel', 'warning', '-y',
                           '-progress', 'pipe:1', '-stats_period', '0.5',
                           '-rw_timeout', '15000000', '-reconnect', '1', '-reconnect_streamed', '1',
                           '-reconnect_delay_max', '5', '-re', '-headers', headers,
                           '-i', self.info['media_url'], '-map', '0:v:0', '-map', '0:a:0?',
                           *codecs, '-f', 'segment', '-segment_time', '5',
                           '-segment_list', str(directory / 'segments.csv'), '-segment_list_size', '400',
                           '-reset_timestamps', '1', str(directory / 'segment_%08d.ts')]
                self.logfile = open(settings.storage_dir / 'logs' / f'capture-{self.stream_id}.log', 'w')
                self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                stderr=self.logfile, creationflags=CREATE_NO_WINDOW)
                self.media_time = 0.0
                threading.Thread(target=self.read_progress, args=(self.process,), daemon=True).start()
                self.started = time.monotonic()
                self.elapsed = 0.0
                self.task = asyncio.create_task(self.watch())
                log.info('STREAM_CONNECTING %s', self.stream_id)
            except Exception:
                if getattr(self, 'logfile', None):
                    self.logfile.close()
                self.state = 'error'
                self.error = 'No se pudo iniciar la captura. Revisa la URL y los logs.'
                raise
        return self.snapshot()

    def read_progress(self, process):
        for line in iter(process.stdout.readline, b''):
            if line.startswith(b'out_time_us='):
                try:
                    self.media_time = max(self.media_time, int(line.split(b'=')[1]) / 1_000_000)
                except ValueError:
                    pass

    def ingest(self):
        fresh = self.buffer.refresh()
        self.clips.collect(self.buffer)
        for segment in fresh:
            if self.transcription.can_enqueue(self.stream_id):
                target = settings.storage_dir / 'audio' / f'{self.stream_id}_{segment.path.name}'
                shutil.copy2(segment.path, target)
                self.transcription.enqueue(target, self.stream_id, segment.start)
            else:
                self.dropped_segments += 1
        self.buffer.prune()

    async def watch(self):
        try:
            while self.process.poll() is None:
                if shutil.disk_usage(settings.storage_dir).free < 256 * 2**20:
                    raise RuntimeError('Captura detenida: quedan menos de 256 MB libres en disco.')
                self.ingest()
                if self.buffer.latest and self.state == 'starting':
                    self.state = 'live'
                await asyncio.sleep(1)
            self.ingest()
            if self.state != 'stopping':
                self.state = 'ended' if self.process.returncode == 0 else 'error'
                if self.state == 'error':
                    self.error = f'La fuente se desconectó o FFmpeg falló. Consulta capture-{self.stream_id}.log.'
        except Exception as exc:
            log.exception('CAPTURE_FAILED')
            self.state, self.error = 'error', str(exc)
            if self.process.poll() is None:
                self.process.terminate()
                await asyncio.to_thread(self.process.wait)
        finally:
            self.elapsed = time.monotonic() - self.started
            self.clips.fail_pending()
            self.logfile.close()
            if self.state == 'stopping':
                self.state = 'idle'

    async def stop(self):
        async with self.lock:
            if self.process and self.process.poll() is None:
                self.state = 'stopping'
                try:
                    self.process.stdin.write(b'q\n')
                    self.process.stdin.flush()
                    await asyncio.wait_for(asyncio.shield(self.task), 20)
                except (asyncio.TimeoutError, OSError):
                    self.process.kill()
                    await self.task
            return self.snapshot()

    def snapshot(self):
        return {'state': self.state, 'error': self.error, 'stream_id': self.stream_id,
                'info': {k: v for k, v in self.info.items() if k not in ('media_url', 'headers')} if self.info else None,
                'elapsed': time.monotonic() - self.started if self.state in ('live', 'starting', 'stopping') else self.elapsed,
                'buffer_seconds': self.buffer.duration if self.buffer else 0,
                'buffer_capacity': settings.buffer_minutes * 60,
                'transcription_status': self.transcription.status,
                'transcription_error': self.transcription.error,
                'transcription_queue': self.transcription.pending.get(self.stream_id, 0),
                'dropped_segments': self.dropped_segments,
                'capture_mode': settings.capture_mode}

ACTIVE = ('starting', 'live', 'stopping')


class StreamPool:
    """Two isolated captures sharing one bounded transcription worker."""
    def __init__(self):
        self.transcription = TranscriptionEngine()
        self.sessions = []
        self.lock = asyncio.Lock()
        self.empty = StreamManager(self.transcription)

    def primary(self):
        return next((s for s in self.sessions if s.state in ACTIVE),
                    self.sessions[-1] if self.sessions else self.empty)

    @property
    def stream_id(self):
        return self.primary().stream_id

    @property
    def state(self):
        return self.primary().state

    def get(self, stream_id=None):
        if stream_id is None:
            active = [s for s in self.sessions if s.state in ACTIVE]
            if len(active) > 1:
                raise ValueError('Selecciona la transmisión para crear el clip.')
            return self.primary()
        session = next((s for s in self.sessions if s.stream_id == stream_id), None)
        if session is None:
            raise ValueError('Transmisión no encontrada.')
        return session

    async def start(self, url):
        async with self.lock:
            active = [s for s in self.sessions if s.state in ACTIVE]
            if len(active) >= 2:
                raise ValueError('Solo se permiten dos transmisiones simultáneas.')
            if any(s.info and s.info['source_url'] == url for s in active):
                raise ValueError('Esta fuente ya se está grabando.')
            # Keep completed jobs alive; discard only fully retired sessions.
            for old in list(self.sessions):
                if old.state not in ACTIVE and not old.clips.tasks:
                    if old.buffer:
                        shutil.rmtree(old.buffer.directory, ignore_errors=True)
                    signals.discard(old.stream_id)
                    self.sessions.remove(old)
            session = StreamManager(self.transcription)
            self.sessions.append(session)
            return await session.start(url)

    async def stop(self, stream_id=None):
        async with self.lock:
            targets = [self.get(stream_id)] if stream_id else list(self.sessions)
            for session in targets:
                await session.stop()
        return self.snapshot()

    def snapshot(self):
        return self.primary().snapshot()

    def snapshots(self):
        return [s.snapshot() for s in self.sessions]

    async def finish_clips(self):
        tasks = [task for s in self.sessions for task in s.clips.tasks]
        if tasks:
            await asyncio.gather(*tasks)


manager = StreamPool()
