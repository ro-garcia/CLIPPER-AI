"""REST endpoints for Settings, render queue, exports and subtitle files."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import settings
from .schemas import RenderSettings
from .service import renderer

router = APIRouter(tags=['Final rendering'])


@router.get('/render/settings')
def render_settings():
    return renderer.config.model_dump()


@router.put('/render/settings')
def save_render_settings(config: RenderSettings):
    return renderer.save(config)


@router.get('/render/status')
def render_status():
    return renderer.status()


@router.post('/clips/{identifier}/render', status_code=202)
def render_clip(identifier: str):
    try:
        return renderer.enqueue(identifier)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post('/clips/{identifier}/render/regenerate', status_code=202)
def regenerate_clip(identifier: str):
    try:
        return renderer.enqueue(identifier, force=True)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/clips/{identifier}/vertical')
def vertical_video(identifier: str, download: bool = False):
    path = settings.storage_dir / 'clips' / identifier / 'vertical.mp4'
    if not path.exists():
        raise HTTPException(404, 'El render vertical todavía no está disponible.')
    return FileResponse(path, media_type='video/mp4', filename=f'LiveClip-vertical-{identifier[:8]}.mp4' if download else None)


@router.get('/clips/{identifier}/subtitles/{extension}')
def subtitle_file(identifier: str, extension: str):
    if extension not in ('srt', 'ass'):
        raise HTTPException(404, 'Formato de subtítulos no disponible.')
    path = settings.storage_dir / 'clips' / identifier / f'subtitles.{extension}'
    if not path.exists():
        raise HTTPException(404, 'Los subtítulos todavía no están disponibles.')
    media = 'application/x-subrip' if extension == 'srt' else 'text/x-ssa'
    return FileResponse(path, media_type=media, filename=f'LiveClip-{identifier[:8]}.{extension}')
