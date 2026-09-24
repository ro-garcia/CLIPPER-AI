import asyncio
from contextlib import asynccontextmanager, suppress
import logging
from logging.handlers import RotatingFileHandler
import shutil
import subprocess
import psutil
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from .config import settings, ffmpeg
from .database import Base, engine, Session, Clip, Stream, Transcript, serialize, upgrade_clip_schema
from .services.stream import manager
from .services.clip_settings import ClipTiming, get_timing, save_timing
from .services.media import analyze, validate_url
from .detection.api import router as detection_router
from .detection.repository import rules_repository
from .detection.runtime import signals
from .moments.api import router as moments_router
from .moments.service import moments, list_moments
from .ai.api import router as ai_router
from .ai.models import upgrade_ai_schema
from .ai.service import ai, evaluations, ranking, statistics
from .rendering.api import router as render_router
from .rendering.service import renderer
from .metadata.api import router as metadata_router
from .metadata.models import ClipMetadata, MetadataConfiguration
from .metadata.service import metadata
from .publishing.api import router as publishing_router
from .publishing.models import (OAuthSession, PublicationAttempt, PublicationJob,
                                PublishingConfiguration, SocialAccount)
from .publishing.service import publishing
from .publishing.accounts import accounts

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), RotatingFileHandler(
    settings.storage_dir / 'logs' / 'app.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')])
ORIGINS = ['http://127.0.0.1:5173', 'http://localhost:5173']

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    upgrade_clip_schema()
    upgrade_ai_schema()
    rules_repository.load()
    moments.recover()
    ai.load()
    renderer.load()
    metadata.load()
    publishing.load()
    ai.manager = manager
    moments.on_candidate = ai.candidate
    moment_worker = asyncio.create_task(moments.worker(manager))
    ai_worker = asyncio.create_task(ai.worker())
    render_worker = asyncio.create_task(renderer.worker())
    metadata_worker = asyncio.create_task(metadata.worker())
    renderer.on_completed = metadata.auto_enqueue
    metadata.on_completed = publishing.auto_publish
    publication_workers = [asyncio.create_task(publishing.worker()) for _ in range(4)]
    publication_scheduler = asyncio.create_task(publishing.scheduler())
    with Session.begin() as db:
        for clip in db.scalars(select(Clip).where(Clip.status.in_(['capturing', 'processing']))):
            clip.status, clip.error = 'error', 'El proceso anterior fue interrumpido.'
    # Startup recovery: these directories contain only disposable working data.
    for directory in (settings.storage_dir / 'buffer', settings.storage_dir / 'audio'):
        for path in directory.iterdir():
            shutil.rmtree(path) if path.is_dir() else path.unlink()
    for path in (settings.storage_dir / 'clips').glob('*/*.ts'):
        path.unlink()
    # Async queues belong to this application lifecycle, not a previous event loop.
    manager.transcription.queue = asyncio.Queue(maxsize=12)
    manager.transcription.pending.clear()
    worker = asyncio.create_task(manager.transcription.worker())
    yield
    await manager.stop()
    for task in (moment_worker, ai_worker, render_worker, metadata_worker,
                 publication_scheduler, *publication_workers):
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    if moments.tasks:
        await asyncio.gather(*moments.tasks)
    await manager.finish_clips()
    await manager.transcription.queue.join()
    worker.cancel()
    with suppress(asyncio.CancelledError):
        await worker

app = FastAPI(title='LiveClip AI', lifespan=lifespan)
app.include_router(detection_router)
app.include_router(moments_router)
app.include_router(ai_router)
app.include_router(render_router)
app.include_router(metadata_router)
app.include_router(publishing_router)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', 'testserver'])
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Content-Type'])

@app.middleware('http')
async def local_origin(request: Request, call_next):
    if request.headers.get('origin') and request.headers['origin'] not in ORIGINS:
        return Response('Origin not allowed', status_code=403)
    return await call_next(request)

class Source(BaseModel):
    url: str = Field(min_length=8, max_length=4096)

@app.get('/health')
def health():
    with engine.connect() as connection:
        connection.execute(text('SELECT 1'))
    return {'status': 'ok', 'database': 'connected', 'version': '0.1.0'}

@app.get('/system/status')
def system_status():
    try:
        available = bool(ffmpeg())
    except Exception:
        available = False
    return {'backend': 'online', 'ffmpeg': 'installed' if available else 'missing',
            'whisper': manager.transcription.status, 'model': settings.whisper_model,
            'device': settings.whisper_device, 'database': 'connected',
            'capture_mode': settings.capture_mode, 'whisper_threads': settings.whisper_threads,
            'capture_max_height': settings.capture_max_height}

@app.get('/system/resources')
def resources():
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage(settings.storage_dir)
    return {'cpu': psutil.cpu_percent(), 'ram_used': memory.used / 2**30,
            'ram_total': memory.total / 2**30, 'storage_free': disk.free / 2**30,
            'gpu': None}

@app.get('/settings/clips')
def clip_timing():
    return get_timing()

@app.put('/settings/clips')
def update_clip_timing(value: ClipTiming):
    return save_timing(value)

@app.post('/streams/analyze')
async def analyze_stream(source: Source):
    try:
        info = await asyncio.to_thread(analyze, source.url)
        return {k: v for k, v in info.items() if k not in ('media_url', 'headers')}
    except Exception as exc:
        raise HTTPException(400, str(exc)[:500]) from exc

@app.post('/streams/start')
async def start(source: Source):
    try:
        validate_url(source.url)
        return await manager.start(source.url)
    except Exception as exc:
        raise HTTPException(400, str(exc)[:500]) from exc

@app.post('/streams/stop')
async def stop(stream_id: str | None = None):
    try:
        return await manager.stop(stream_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

@app.get('/streams/active')
def active_streams():
    return manager.snapshots()

@app.get('/streams/status')
def stream_status():
    return manager.snapshot()

@app.get('/streams')
def streams():
    with Session() as db:
        return [serialize(row) for row in db.scalars(select(Stream).order_by(Stream.created_at.desc()).limit(10))]

@app.get('/transcriptions')
def transcriptions(stream_id: str | None = None):
    with Session() as db:
        rows = db.scalars(select(Transcript).where(Transcript.stream_id == (stream_id or manager.stream_id))
                          .order_by(Transcript.id.desc()).limit(200)).all()
        return [serialize(row) for row in reversed(rows)]

@app.post('/clips/create', status_code=202)
async def create_clip(stream_id: str | None = None):
    try:
        session = manager.get(stream_id)
        if session.state != 'live':
            raise ValueError('No hay una transmisión activa.')
        if sum(len(s.clips.pending) + len(s.clips.tasks) for s in manager.sessions) >= 3:
            raise ValueError('Ya hay tres clips en proceso. Espera a que termine uno.')
        return session.clips.create(session.stream_id, session.info['title'], session.buffer, session.media_time)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

@app.get('/clips')
def clips():
    with Session() as db:
        return [serialize(row) for row in db.scalars(select(Clip).order_by(Clip.created_at.desc()).limit(200))]

@app.get('/clips/{clip_id}')
def clip_details(clip_id: str):
    with Session() as db:
        row = db.get(Clip, clip_id)
        if not row:
            raise HTTPException(404, 'Clip no encontrado.')
        return serialize(row)

@app.get('/clips/{clip_id}/video')
def clip_video(clip_id: str, download: bool = False):
    row = clip_details(clip_id)
    if row['status'] != 'ready':
        raise HTTPException(409, 'El clip no está listo.')
    return FileResponse(settings.storage_dir / 'clips' / row['id'] / 'original.mp4',
                        media_type='video/mp4', filename=f'LiveClip-{clip_id[:8]}.mp4' if download else None)

@app.get('/clips/{clip_id}/thumbnail')
def thumbnail(clip_id: str):
    row = clip_details(clip_id)
    path = settings.storage_dir / 'clips' / row['id'] / 'thumbnail.jpg'
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)

@app.get('/preview/live.m3u8')
def preview():
    session = manager.primary()
    if not session.buffer or not session.buffer.segments:
        raise HTTPException(404)
    segments = session.buffer.segments[-6:]
    import math
    lines = ['#EXTM3U', '#EXT-X-VERSION:3', f'#EXT-X-TARGETDURATION:{math.ceil(max(s.end-s.start for s in segments))}',
             f'#EXT-X-MEDIA-SEQUENCE:{int(segments[0].path.stem.split("_")[-1])}',
             f'#EXT-X-DISCONTINUITY-SEQUENCE:{int(segments[0].path.stem.split("_")[-1])}']
    for segment in segments:
        lines += ['#EXT-X-DISCONTINUITY', f'#EXTINF:{segment.end-segment.start:.3f},',
                  f'/preview/{session.stream_id}/{segment.path.name}']
    return Response('\n'.join(lines) + '\n', media_type='application/vnd.apple.mpegurl', headers={'Cache-Control': 'no-store'})

@app.get('/preview/{stream_id}/{name}')
def preview_segment(stream_id: str, name: str):
    session = next((s for s in manager.sessions if s.stream_id == stream_id), None)
    if not session or not session.buffer:
        raise HTTPException(404)
    segment = next((s for s in session.buffer.segments if s.path.name == name), None)
    if not segment or not segment.path.exists():
        raise HTTPException(404)
    return FileResponse(segment.path, media_type='video/mp2t')

@app.websocket('/ws/live')
async def live(websocket: WebSocket):
    if websocket.headers.get('origin') not in ORIGINS:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    cursor = ai.sequence
    render_cursor = renderer.sequence
    metadata_cursor = metadata.sequence
    publication_cursor = publishing.sequence
    try:
        while True:
            await websocket.send_json({'stream': manager.snapshot(), 'streams': manager.snapshots(), 'clip_timing': get_timing(),
                                       'transcripts_by_stream': {s.stream_id: transcriptions(s.stream_id) for s in manager.sessions if s.stream_id},
                                       'detection_by_stream': {s.stream_id: signals.status(s.stream_id) for s in manager.sessions if s.stream_id},
                                       'transcripts': transcriptions(), 'clips': clips(),
                                       'detection': signals.status(), 'moments': list_moments(),
                                       'ai': ai.status(), 'ai_statistics': statistics(), 'ai_ranking': ranking(),
                                       'evaluations': evaluations(), 'render': renderer.status(),
                                       'metadata': metadata.status(), 'publishing': publishing.status(),
                                       'publications': publishing.jobs(), 'social_accounts': accounts.list()})
            for event in list(ai.events):
                if event['sequence'] > cursor:
                    await websocket.send_json(event)
                    cursor = event['sequence']
            for event in list(renderer.events):
                if event['sequence'] > render_cursor:
                    await websocket.send_json(event)
                    render_cursor = event['sequence']
            for event in list(metadata.events):
                if event['sequence'] > metadata_cursor:
                    await websocket.send_json(event)
                    metadata_cursor = event['sequence']
            for event in list(publishing.events):
                if event['sequence'] > publication_cursor:
                    await websocket.send_json(event)
                    publication_cursor = event['sequence']
            await asyncio.sleep(3)
    except (WebSocketDisconnect, RuntimeError):
        pass
