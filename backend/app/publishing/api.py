from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from html import escape

from .accounts import accounts
from .schemas import CreatePublications, PublishingSettings
from .service import publishing

router = APIRouter(prefix='/publishing', tags=['Social publishing'])


@router.get('/settings')
def settings(): return publishing.config.model_dump()


@router.put('/settings')
def save_settings(value: PublishingSettings):
    try: return publishing.save(value)
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc


@router.get('/status')
def status(): return publishing.status()


@router.get('/capabilities')
def capabilities(): return accounts.capabilities(publishing.mock_mode)


@router.get('/accounts')
def social_accounts(): return accounts.list()


@router.post('/accounts/{platform}/connect')
def connect(platform: str):
    try:
        if publishing.mock_mode: return {'account': accounts.ensure_mock(platform), 'authorization_url': ''}
        return accounts.oauth_start(platform)
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc


@router.delete('/accounts/{identifier}')
def disconnect(identifier: str):
    try: return accounts.disconnect(identifier)
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc


@router.get('/oauth/{platform}/callback', response_class=HTMLResponse)
async def oauth_callback(platform: str, state: str = Query(...), code: str = Query(...)):
    try:
        account = await accounts.oauth_callback(platform, state, code)
        return HTMLResponse(f'<h1>LiveClip AI</h1><p>{escape(account["display_name"])} conectada. Ya puedes cerrar esta ventana.</p>')
    except ValueError as exc:
        return HTMLResponse(f'<h1>No se pudo conectar</h1><p>{escape(str(exc))}</p>', status_code=400)


@router.post('/jobs', status_code=202)
def create_jobs(request: CreatePublications):
    try: return publishing.create(request)
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        from .publishers import PublishingError
        if isinstance(exc, PublishingError): raise HTTPException(409, str(exc)) from exc
        raise


@router.get('/jobs')
def jobs(clip_id: str | None = None): return publishing.jobs(clip_id)


@router.get('/jobs/{identifier}')
def job(identifier: str):
    try: return publishing.get(identifier)
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc


@router.get('/jobs/{identifier}/attempts')
def attempts(identifier: str): return publishing.attempts(identifier)


@router.post('/jobs/{identifier}/retry', status_code=202)
def retry(identifier: str):
    try: return publishing.retry(identifier)
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc


@router.post('/jobs/{identifier}/cancel')
def cancel(identifier: str):
    try: return publishing.cancel(identifier)
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc
