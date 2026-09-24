import time

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..database import Session
from ..moments.service import get_moment
from .models import AIEvaluation
from .providers import OllamaProvider
from .schemas import AISettings
from .service import ai, evaluations, evaluation_dict, ranking, statistics

router = APIRouter(tags=['AI evaluation'])


@router.get('/ai/settings')
def settings():
    return ai.config.model_dump()


@router.put('/ai/settings')
async def save_settings(config: AISettings):
    return ai.save(config)


@router.get('/ai/status')
def status():
    return ai.status()


@router.get('/ai/statistics')
def metrics():
    return statistics()


@router.get('/ai/ranking')
def top_moments(limit: int = Query(5, ge=1, le=20)):
    return ranking(limit)


@router.get('/ai/providers')
def providers():
    return [{'id': 'ollama', 'name': 'Ollama · Local', 'requires_api_key': False, 'processing': 'LOCAL'}]


@router.get('/ai/models')
async def models():
    try:
        return await OllamaProvider(ai.config).models()
    except Exception as exc:
        raise HTTPException(503, 'No se pudo consultar Ollama local.') from exc


@router.post('/ai/settings/test')
async def test(config: AISettings):
    start = time.monotonic()
    try:
        available = await OllamaProvider(config).models()
        if not any(model['name'] == config.model for model in available):
            raise ValueError('El modelo no está instalado en Ollama.')
        return {'connected': True, 'model_available': True,
                'latency_ms': int((time.monotonic() - start) * 1000),
                'message': 'Ollama local responde y el modelo está disponible.'}
    except Exception as exc:
        raise HTTPException(400, 'No se pudo verificar Ollama local, el endpoint o el modelo.') from exc


@router.get('/ai/queue')
def queue():
    with Session() as db:
        rows = db.scalars(select(AIEvaluation).where(AIEvaluation.status.in_(['QUEUED', 'EVALUATING', 'RETRYING'])))
        return [evaluation_dict(row) for row in rows]


@router.get('/ai/evaluations')
def all_evaluations():
    return evaluations()


@router.get('/moments/{identifier}/evaluations')
def history(identifier: str):
    try:
        get_moment(identifier)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return evaluations(identifier)


@router.post('/moments/{identifier}/evaluate', status_code=202)
async def evaluate(identifier: str):
    try:
        return ai.enqueue(identifier)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post('/moments/{identifier}/reevaluate', status_code=202)
async def reevaluate(identifier: str):
    try:
        return ai.enqueue(identifier, reevaluate=True)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


class Batch(BaseModel):
    moment_ids: list[str] = Field(min_length=1, max_length=100)


@router.post('/ai/evaluate-batch')
async def batch(request: Batch):
    result = []
    for identifier in dict.fromkeys(request.moment_ids):
        try:
            result.append({'moment_id': identifier, 'evaluation': ai.enqueue(identifier)})
        except ValueError as exc:
            result.append({'moment_id': identifier, 'error': str(exc)})
    return result
