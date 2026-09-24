from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Literal
from ..database import Session
from .models import MomentFeedback
from .service import moments,list_moments,get_moment,update_moment,ROOT

router=APIRouter(tags=['Moments'])

@router.get('/moments')
def all_moments():
    return list_moments()

@router.get('/moments/{identifier}')
def detail(identifier:str):
    try:
        return get_moment(identifier)
    except ValueError as exc:
        raise HTTPException(404,str(exc)) from exc

@router.get('/moments/{identifier}/video')
def video(identifier:str):
    row=detail(identifier)
    path=ROOT/row['id']/'preview.mp4'
    if row['media_status']!='READY' or not path.exists():
        raise HTTPException(410,'El preview no está disponible; la transcripción se conserva.')
    return FileResponse(path,media_type='video/mp4')

@router.post('/moments/{identifier}/clip')
async def clip(identifier:str):
    detail(identifier)
    try:
        return await moments.create_clip(identifier)
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc

class FeedbackInput(BaseModel):
    action:Literal['APPROVED','DISMISSED','THUMBS_UP','THUMBS_DOWN']
    evaluation_id:str|None=None

@router.post('/moments/{identifier}/feedback')
def feedback(identifier:str,payload:FeedbackInput):
    detail(identifier)
    with Session.begin() as db:
        if payload.evaluation_id:
            from ..ai.models import AIEvaluation
            evaluation=db.get(AIEvaluation,payload.evaluation_id)
            if not evaluation or evaluation.moment_id!=identifier:
                raise HTTPException(422,'La evaluación no pertenece a este momento.')
        db.add(MomentFeedback(moment_id=identifier,evaluation_id=payload.evaluation_id,action=payload.action))
    if payload.action=='DISMISSED':
        update_moment(identifier,status='DISMISSED')
    return {'saved':True}
