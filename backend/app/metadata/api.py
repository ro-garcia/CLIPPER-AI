from fastapi import APIRouter, HTTPException

from .schemas import ContentMetadata, MetadataSettings, RegenerateRequest
from .service import metadata

router = APIRouter(tags=['Content metadata'])


@router.get('/metadata/settings')
def settings():
    return metadata.config.model_dump()


@router.put('/metadata/settings')
def save_settings(config: MetadataSettings):
    return metadata.save_settings(config)


@router.get('/metadata/status')
def status():
    return metadata.status()


@router.get('/clips/{clip_id}/metadata')
def get_metadata(clip_id: str):
    try:
        return metadata.get(clip_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post('/clips/{clip_id}/metadata/generate', status_code=202)
def generate_metadata(clip_id: str, request: RegenerateRequest = RegenerateRequest()):
    try:
        return metadata.enqueue(clip_id, request.scope)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.put('/clips/{clip_id}/metadata')
def update_metadata(clip_id: str, value: ContentMetadata):
    try:
        return metadata.update_manual(clip_id, value)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
