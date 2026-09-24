"""Bounded local final-render queue. It never blocks capture, Whisper, or AI scoring."""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
import logging
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from sqlalchemy import select

from ..config import ffmpeg, settings
from ..database import Clip, Session, serialize
from ..services.media import CREATE_NO_WINDOW, run_ffmpeg, media_slot
from .models import RenderConfiguration
from .reframing import strategy_for
from .schemas import RenderSettings
from .subtitles import create_subtitle_files

log = logging.getLogger(__name__)


class FinalRenderService:
    def __init__(self):
        self.config = RenderSettings()
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=25)
        self.events = deque(maxlen=200)
        self.sequence = 0
        self.active: str | None = None
        self.error = ''
        self.on_completed = None

    def load(self) -> None:
        self.queue = asyncio.Queue(maxsize=25)
        self.active, self.error = None, ''
        with Session.begin() as db:
            stored = db.get(RenderConfiguration, 1)
            self.config = RenderSettings.model_validate(stored.value) if stored else RenderSettings()
            if stored and stored.value != self.config.model_dump():
                stored.value = self.config.model_dump()
            for clip in db.scalars(select(Clip).where(Clip.render_status.in_(['QUEUED', 'PROCESSING']))):
                clip.render_status = 'FAILED'
                clip.render_stage = 'FAILED'
                clip.render_error = 'Render interrumpido al cerrar la aplicación. Puedes regenerarlo.'

    def save(self, config: RenderSettings) -> dict:
        with Session.begin() as db:
            row = db.get(RenderConfiguration, 1)
            if row:
                row.value = config.model_dump()
            else:
                db.add(RenderConfiguration(id=1, value=config.model_dump()))
        self.config, self.error = config, ''
        return config.model_dump()

    def status(self) -> dict:
        return {'status': 'PROCESSING' if self.active else 'ERROR' if self.error else 'READY',
                'queued': self.queue.qsize(), 'active': self.active, 'active_count': 1 if self.active else 0,
                'max_concurrent_renders': 1, 'error': self.error, 'processing_local': True}

    def _clip(self, identifier: str) -> dict:
        with Session() as db:
            row = db.get(Clip, identifier)
            if not row:
                raise ValueError('Clip no encontrado.')
            return serialize(row)

    def update(self, identifier: str, **values) -> dict:
        with Session.begin() as db:
            row = db.get(Clip, identifier)
            if not row:
                raise ValueError('Clip no encontrado.')
            for key, value in values.items():
                setattr(row, key, value)
            db.flush()
            return serialize(row)

    def emit(self, event: str, identifier: str) -> None:
        try:
            data = self._clip(identifier)
        except ValueError:
            return
        self.sequence += 1
        self.events.append({'sequence': self.sequence, 'type': event, 'data': data})

    def enqueue(self, identifier: str, force: bool = False) -> dict:
        clip = self._clip(identifier)
        if clip['status'] != 'ready':
            raise ValueError('Espera a que el MP4 original esté listo antes de renderizarlo.')
        source = settings.storage_dir / 'clips' / identifier / 'original.mp4'
        if not source.exists():
            raise ValueError('No se encontró el MP4 original de este clip.')
        if clip['render_status'] in ('QUEUED', 'PROCESSING'):
            return clip
        if clip['render_status'] == 'READY' and not force:
            return clip
        if self.queue.full():
            raise ValueError('La cola de render está llena. Intenta más tarde.')
        snapshot = self.config.model_dump()
        saved = self.update(identifier, render_status='QUEUED', render_progress=0, render_stage='PREPARING',
                            render_error='', render_settings=snapshot)
        self.queue.put_nowait(identifier)
        self.emit('render_started', identifier)
        return saved

    async def worker(self) -> None:
        while True:
            identifier = await self.queue.get()
            try:
                await self.run(identifier)
            except asyncio.CancelledError:
                self.update(identifier, render_status='FAILED', render_stage='FAILED',
                            render_error='Render interrumpido.')
                self.emit('render_failed', identifier)
                raise
            except Exception:
                log.exception('FINAL_RENDER_WORKER_FAILED clip_id=%s', identifier)
                self.update(identifier, render_status='FAILED', render_stage='FAILED',
                            render_error='No se pudo completar el render. Puedes regenerarlo.')
                self.emit('render_failed', identifier)
            finally:
                self.active = None
                self.queue.task_done()

    async def run(self, identifier: str) -> None:
        clip = self._clip(identifier)
        config = RenderSettings.model_validate(clip.get('render_settings') or self.config.model_dump())
        self.active = identifier
        self.update(identifier, render_status='PROCESSING', render_progress=3, render_stage='PREPARING', render_error='')
        self.emit('render_progress', identifier)
        try:
            await asyncio.to_thread(self.render_blocking, identifier, config)
        except Exception as exc:
            message = str(exc).strip()[-1200:] or 'No se pudo completar el render.'
            self.error = message
            self.update(identifier, render_status='FAILED', render_stage='FAILED', render_error=message)
            self.emit('render_failed', identifier)
            return
        self.error = ''
        self.update(identifier, render_status='READY', render_progress=100, render_stage='COMPLETED', render_error='',
                    output_width=config.output_width, output_height=config.output_height,
                    rendered_at=datetime.now(timezone.utc).isoformat())
        self.emit('render_completed', identifier)
        if self.on_completed:
            try:
                self.on_completed(identifier)
            except Exception:
                log.exception('METADATA_AUTO_ENQUEUE_FAILED clip_id=%s', identifier)

    def render_blocking(self, identifier: str, config: RenderSettings) -> None:
        """Run only in a worker thread; all input comes from an already-created local clip."""
        if shutil.disk_usage(settings.storage_dir).free < 256 * 2**20:
            raise ValueError('Se necesitan al menos 256 MB libres para renderizar el clip.')
        directory = settings.storage_dir / 'clips' / identifier
        source = directory / 'original.mp4'
        if not source.exists():
            raise ValueError('No se encontró el MP4 original de este clip.')
        subtitle_file: Path | None = None
        if config.subtitles_enabled:
            self.update(identifier, render_progress=10, render_stage='GENERATING_SUBTITLES')
            self.emit('render_progress', identifier)
            _, subtitle_file, _ = create_subtitle_files(identifier, config)
        self.update(identifier, render_progress=30, render_stage='PROCESSING_VIDEO')
        self.emit('render_progress', identifier)
        temporary = directory / f'.vertical-{uuid4().hex}.mp4'
        final = directory / 'vertical.mp4'
        try:
            video_filter = strategy_for(config).video_filter(config, subtitle_file)
            command = [ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y', '-threads', '2',
                       '-filter_complex_threads', '1', '-i', str(source),
                       '-filter_complex', video_filter, '-map', '[v]', '-map', '0:a:0?', '-c:v', config.video_codec,
                       '-preset', 'veryfast', '-threads', '2', '-crf', str(config.crf), '-pix_fmt', 'yuv420p', '-c:a', config.audio_codec,
                       '-movflags', '+faststart', '-progress', 'pipe:1', '-nostats']
            if config.fps:
                command += ['-r', str(config.fps)]
            command.append(str(temporary))
            with media_slot:
                self._run_ffmpeg_with_progress(identifier, command, max(1.0, float(self._clip(identifier)['duration'])))
            temporary.replace(final)
            self.update(identifier, render_progress=96, render_stage='FINALIZING')
            self.emit('render_progress', identifier)
            try:
                run_ffmpeg(['-i', str(final), '-frames:v', '1', '-vf', 'scale=360:-2', str(directory / 'vertical-thumbnail.jpg')])
            except Exception:
                log.info('Vertical thumbnail unavailable clip_id=%s', identifier)
        finally:
            temporary.unlink(missing_ok=True)

    def _run_ffmpeg_with_progress(self, identifier: str, command: list[str], duration: float) -> None:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   encoding='utf-8', errors='replace', creationflags=CREATE_NO_WINDOW)
        last = 30
        assert process.stdout is not None
        for line in process.stdout:
            if line.startswith(('out_time_us=', 'out_time_ms=')):
                try:
                    value = float(line.split('=', 1)[1].strip()) / 1_000_000
                except ValueError:
                    continue
                progress = min(94, max(last, 30 + int(value / duration * 64)))
                if progress > last:
                    last = progress
                    self.update(identifier, render_progress=progress, render_stage='ENCODING')
                    self.emit('render_progress', identifier)
        stderr = process.stderr.read() if process.stderr else ''
        if process.wait() != 0:
            raise RuntimeError(stderr[-1200:] or 'FFmpeg no pudo codificar el video.')


renderer = FinalRenderService()
