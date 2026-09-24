import asyncio
import logging
import shutil
import time
from uuid import uuid4
from sqlalchemy import select
from ..config import settings
from ..database import Session, Clip, serialize
from ..detection.runtime import signals
from ..detection.repository import rules_repository
from ..services.media import run_ffmpeg
from .models import Moment, MomentFeedback
from .detector import detect, duplicate

log = logging.getLogger(__name__)
ROOT = settings.storage_dir / 'moments'
ROOT.mkdir(parents=True, exist_ok=True)

def get_moment(identifier: str) -> dict:
    with Session() as db:
        row = db.get(Moment, identifier)
        if row is None:
            raise ValueError('Momento no encontrado.')
        return serialize(row)

def list_moments() -> list[dict]:
    with Session() as db:
        return [serialize(row) for row in db.scalars(select(Moment).order_by(Moment.created_at.desc()).limit(250))]

def update_moment(identifier: str, **values):
    with Session.begin() as db:
        row = db.get(Moment, identifier)
        for key, value in values.items():
            setattr(row,key,value)

class MomentService:
    def __init__(self):
        self.tasks: set[asyncio.Task] = set()
        self.last_window = {}
        self.error = ''
        self.clip_lock = None
        self.on_candidate = None

    def recover(self):
        self.clip_lock = asyncio.Lock()
        self.last_window = {}
        with Session.begin() as db:
            for row in db.scalars(select(Moment).where(Moment.media_status == 'PROCESSING')):
                row.media_status, row.media_error = 'FAILED', 'Preparación interrumpida; candidato conservado.'
        for path in ROOT.glob('*/*.ts'):
            path.unlink(missing_ok=True)

    async def worker(self, manager):
        last_prune = 0
        while True:
            try:
                if time.monotonic()-last_prune > 60:
                    self.prune_previews()
                    last_prune = time.monotonic()
                for session in manager.sessions:
                    self.tick(session)
                current = {session.stream_id for session in manager.sessions}
                self.last_window = {k: v for k, v in self.last_window.items() if k in current}
            except Exception:
                self.error = 'No se pudo procesar un candidato; la captura continúa.'
                log.exception('MOMENT_DETECTION_FAILED')
            await asyncio.sleep(1)

    def tick(self, manager):
        stream_id, parts, language = signals.window(manager.stream_id)
        if not stream_id or stream_id != manager.stream_id or not parts:
            return
        snapshot = rules_repository.cache.snapshot
        key = (stream_id, parts[-1]['end'],snapshot.revision)
        if key == self.last_window.get(stream_id):
            return
        self.last_window[stream_id] = key
        candidate = detect(parts, language, snapshot, settings.detection_threshold)
        if not candidate:
            return
        with Session() as db:
            previous = [serialize(row) for row in db.scalars(select(Moment).where(
                Moment.stream_id==stream_id).order_by(Moment.end.desc()).limit(30))]
        if duplicate(candidate, previous):
            return
        identifier = uuid4().hex
        with Session.begin() as db:
            row = Moment(id=identifier,stream_id=stream_id,start=candidate.start,end=candidate.end,
                         transcript_excerpt=candidate.text,language=language,moment_type=candidate.kind,
                         detection_confidence=candidate.confidence,detection_reasons=candidate.reasons,
                         rule_revision=candidate.revision)
            db.add(row)
        log.info('MOMENT_DETECTED moment_id=%s confidence=%s',identifier,candidate.confidence)
        self.preserve(identifier,manager.buffer)
        if self.on_candidate:
            self.on_candidate(identifier)

    def preserve(self, identifier, buffer):
        moment = get_moment(identifier)
        segments = buffer.select(moment['start'],moment['end']) if buffer else []
        directory = ROOT / identifier
        directory.mkdir(exist_ok=True)
        try:
            self.prune_previews()
            if len(self.tasks)>=2 or shutil.disk_usage(ROOT).free<512*2**20:
                raise ValueError('Preview omitido por límites de recursos. La transcripción está conservada.')
            if not segments or segments[0].start > moment['start']+.15 or segments[-1].end < moment['end']-.2:
                raise ValueError('Los segmentos del momento ya no están completos en el buffer.')
            for segment in segments:
                shutil.copy2(segment.path, directory / segment.path.name)
            task = asyncio.create_task(asyncio.to_thread(self.encode,identifier,segments))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
        except Exception as exc:
            update_moment(identifier,media_status='UNAVAILABLE',media_error=str(exc)[:300])
            for path in directory.glob('*.ts'):
                path.unlink(missing_ok=True)

    def encode(self,identifier,segments):
        moment = get_moment(identifier)
        directory = ROOT / identifier
        try:
            playlist = directory / 'source.ffconcat'
            playlist.write_text('ffconcat version 1.0\n'+''.join(f"file '{s.path.name}'\n" for s in segments))
            run_ffmpeg(['-f','concat','-safe','1','-i',str(playlist),'-ss',str(max(0,moment['start']-segments[0].start)),
                        '-t',str(moment['end']-moment['start']),'-map','0:v:0','-map','0:a:0?',
                        '-c:v','libx264','-preset','veryfast','-threads','2','-crf','24','-c:a','aac',
                        '-movflags','+faststart',str(directory/'preview.mp4')])
            update_moment(identifier,media_status='READY',media_error='')
        except Exception:
            log.exception('MOMENT_PREVIEW_FAILED moment_id=%s',identifier)
            update_moment(identifier,media_status='FAILED',media_error='No se pudo codificar el preview.')
        finally:
            for path in directory.glob('*.ts'):
                path.unlink(missing_ok=True)
            (directory/'source.ffconcat').unlink(missing_ok=True)

    def prune_previews(self):
        with Session() as db:
            ready = set(db.scalars(select(Moment.id).where(Moment.media_status == 'READY')))
        files = sorted((p for p in ROOT.glob('*/preview.mp4') if p.parent.name in ready),key=lambda path:path.stat().st_mtime)
        total = sum(path.stat().st_size for path in files)
        for path in files:
            size = path.stat().st_size
            if total <= settings.moment_preview_budget_mb*2**20 and time.time()-path.stat().st_mtime<86400:
                continue
            path.unlink(missing_ok=True)
            total -= size
            update_moment(path.parent.name,media_status='EXPIRED',media_error='Preview temporal expirado; transcripción conservada.')

    async def create_clip(self,identifier: str):
        async with self.clip_lock:
            moment = get_moment(identifier)
            if moment['clip_id']:
                with Session() as db:
                    row=db.get(Clip,moment['clip_id'])
                    if row and row.status in ('ready','processing'):
                        return serialize(row)
            source = ROOT/identifier/'preview.mp4'
            if moment['media_status']!='READY' or not source.exists():
                raise ValueError('Este momento no tiene video disponible. Su transcripción se conserva.')
            clip_id=uuid4().hex
            directory=settings.storage_dir/'clips'/clip_id
            directory.mkdir()
            with Session.begin() as db:
                db.add(Clip(id=clip_id,stream_id=moment['stream_id'],title=f"Momento {moment['start']:.0f}s",
                            status='processing',duration=moment['end']-moment['start'],
                            source_start=moment['start'],source_end=moment['end']))
                db.get(Moment,identifier).clip_id=clip_id
            try:
                # Copy is short and runs on the loop so pruning cannot race it.
                shutil.copy2(source,directory/'original.mp4')
                with Session.begin() as db:
                    db.get(Clip,clip_id).status='ready'
                    db.add(MomentFeedback(moment_id=identifier,action='CLIP_CREATED'))
                try:
                    await asyncio.to_thread(run_ffmpeg,['-i',str(directory/'original.mp4'),'-frames:v','1',
                                                       '-vf','scale=480:-2',str(directory/'thumbnail.jpg')])
                except Exception:
                    pass
            except Exception:
                with Session.begin() as db:
                    row=db.get(Clip,clip_id)
                    row.status,row.error='error','No se pudo copiar el video del momento.'
                raise ValueError('No se pudo guardar el clip.')
            with Session() as db:
                return serialize(db.get(Clip,clip_id))

moments = MomentService()
