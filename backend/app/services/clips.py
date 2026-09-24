import asyncio
import shutil
import uuid
from pathlib import Path
from ..config import settings
from ..database import Session, Clip, serialize
from .media import run_ffmpeg
from .clip_settings import get_timing

class ClipGenerator:
    def __init__(self):
        self.pending: dict[str, dict] = {}
        self.tasks: set[asyncio.Task] = set()

    def create(self, stream_id, title, buffer, anchor=None):
        timing = get_timing()
        before, after = timing['before_seconds'], timing['after_seconds']
        if buffer.latest < before or buffer.duration < before:
            raise ValueError(f'Espera hasta disponer de {before} segundos de buffer.')
        if len(self.pending) + len(self.tasks) >= 3:
            raise ValueError('Ya hay tres clips en proceso.')
        clip_id = uuid.uuid4().hex
        directory = settings.storage_dir / 'clips' / clip_id
        directory.mkdir()
        anchor = max(buffer.latest, anchor or 0)
        job = {'directory': directory, 'start': anchor - before,
               'end': anchor + after, 'after_seconds': after, 'segments': {}, 'stream_id': stream_id}
        with Session.begin() as db:
            row = Clip(id=clip_id, stream_id=stream_id, title=title,
                       source_start=job['start'], source_end=job['end'], duration=before + after)
            db.add(row)
            db.flush()
            result = serialize(row)
        self.pending[clip_id] = job
        self.collect(buffer)
        return result

    def collect(self, buffer):
        for clip_id, job in list(self.pending.items()):
            for segment in buffer.select(job['start'], job['end']):
                if segment.path.name not in job['segments']:
                    shutil.copy2(segment.path, job['directory'] / segment.path.name)
                    job['segments'][segment.path.name] = segment
            if buffer.latest >= job['end']:
                del self.pending[clip_id]
                task = asyncio.create_task(asyncio.to_thread(self.encode, clip_id, job))
                self.tasks.add(task)
                task.add_done_callback(self.tasks.discard)

    def encode(self, clip_id: str, job: dict):
        directory: Path = job['directory']
        try:
            self.update(clip_id, status='processing')
            segments = sorted(job['segments'].values(), key=lambda s: s.start)
            playlist = directory / 'input.ffconcat'
            playlist.write_text('ffconcat version 1.0\n' + ''.join(
                f"file '{s.path.name}'\n" for s in segments))
            run_ffmpeg(['-f', 'concat', '-safe', '1', '-i', str(playlist),
                        '-ss', str(job['start'] - segments[0].start), '-t', str(job['end'] - job['start']),
                        '-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'libx264', '-preset', 'veryfast',
                        '-threads', '2', '-crf', '23', '-c:a', 'aac', '-movflags', '+faststart',
                        str(directory / 'original.mp4')])
            try:
                run_ffmpeg(['-i', str(directory / 'original.mp4'), '-frames:v', '1',
                            '-vf', 'scale=480:-2', str(directory / 'thumbnail.jpg')])
            except Exception:
                pass
            self.update(clip_id, status='ready', duration=job['end'] - job['start'])
        except Exception as exc:
            self.update(clip_id, status='error', error=str(exc)[-500:])
        finally:
            for path in directory.glob('*.ts'):
                path.unlink(missing_ok=True)
            (directory / 'input.ffconcat').unlink(missing_ok=True)

    def fail_pending(self):
        for clip_id, job in self.pending.items():
            self.update(clip_id, status='error', error=f"La transmisión terminó antes de completar el clip ({job['after_seconds']} segundos posteriores).")
            for path in job['directory'].glob('*.ts'):
                path.unlink(missing_ok=True)
        self.pending.clear()

    @staticmethod
    def update(clip_id, **values):
        with Session.begin() as db:
            row = db.get(Clip, clip_id)
            for key, value in values.items():
                setattr(row, key, value)
