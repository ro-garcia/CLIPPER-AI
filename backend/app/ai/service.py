"""Bounded local AI evaluation queue, separate from capture and Whisper."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import deque
from uuid import uuid4

import httpx
from pydantic import ValidationError
from sqlalchemy import func, select

from ..config import settings
from ..database import Session, serialize, Transcript
from ..detection.models import now
from ..moments.models import Moment
from ..moments.service import get_moment
from .context import AIContextBuilder
from .models import AIConfiguration, AIEvaluation
from .prompts.moment_evaluator import VERSION
from .providers import OllamaProvider, ProviderResult
from .schemas import (AISettings, CONTENT_TYPES, EMOTIONAL_TONES, MomentAIEvaluation,
                      overall, quality_level, recommendation)

log = logging.getLogger(__name__)


_SCORE_FIELDS = ('interest_score', 'clarity_score', 'virality_score', 'standalone_score',
                 'hook_score', 'ending_score', 'information_value_score',
                 'context_dependency_score', 'completeness_score')


def evaluation_dict(row: AIEvaluation) -> dict:
    data = serialize(row)
    if row.interest_score is not None:
        data['result'] = {field: getattr(row, field) for field in _SCORE_FIELDS}
        data['result'].update({
            'content_type': row.content_type, 'detected_topic': row.detected_topic,
            'emotional_tone': row.emotional_tone, 'requires_context': row.requires_context,
            'moment_summary': row.moment_summary, 'evaluation_reason': row.evaluation_reason,
            'overall_score': row.overall_score, 'quality_level': row.quality_level,
            'recommended_action': row.recommended_action,
        })
    return data


def evaluations(moment_id: str | None = None) -> list[dict]:
    with Session() as db:
        query = select(AIEvaluation)
        if moment_id:
            query = query.where(AIEvaluation.moment_id == moment_id)
        return [evaluation_dict(row) for row in db.scalars(query.order_by(AIEvaluation.created_at.desc()).limit(500))]


def _latest_evaluations(db) -> dict[str, AIEvaluation]:
    latest: dict[str, AIEvaluation] = {}
    for row in db.scalars(select(AIEvaluation).order_by(AIEvaluation.created_at.desc(), AIEvaluation.id.desc())):
        latest.setdefault(row.moment_id, row)
    return latest


def statistics() -> dict:
    with Session() as db:
        latest = _latest_evaluations(db)
        candidates = db.scalar(select(func.count()).select_from(Moment)) or 0
    values = list(latest.values())
    evaluated = [row for row in values if row.status == 'EVALUATED' and row.overall_score is not None]
    counts = {level: sum(row.quality_level == level for row in evaluated)
              for level in ('HIGH_POTENTIAL', 'GOOD', 'MEDIUM', 'LOW')}
    return {
        'candidates': candidates,
        'evaluated': len(evaluated),
        'high_potential': counts['HIGH_POTENTIAL'], 'good': counts['GOOD'],
        'medium': counts['MEDIUM'], 'low': counts['LOW'],
        'failed': sum(row.status == 'FAILED' for row in values),
        'queued': sum(row.status in ('QUEUED', 'RETRYING') for row in values),
        'evaluating': sum(row.status == 'EVALUATING' for row in values),
        'average_score': round(sum(row.overall_score for row in evaluated) / len(evaluated), 1) if evaluated else None,
        'average_latency_ms': round(sum(row.latency_ms for row in evaluated) / len(evaluated)) if evaluated else None,
    }


def ranking(limit: int = 5) -> list[dict]:
    with Session() as db:
        latest = _latest_evaluations(db)
        rows = [row for row in latest.values() if row.status == 'EVALUATED' and row.overall_score is not None]
        rows.sort(key=lambda row: (-row.overall_score, row.created_at, row.id))
        result = []
        for row in rows:
            moment = db.get(Moment, row.moment_id)
            if moment and moment.status != 'DISMISSED':
                result.append({'rank': len(result) + 1, 'moment_id': row.moment_id, 'overall_score': row.overall_score,
                               'quality_level': row.quality_level, 'moment_summary': row.moment_summary,
                               'start_time': moment.start, 'created_at': row.created_at})
                if len(result) == limit:
                    break
        return result


class AIService:
    def __init__(self):
        self.config = AISettings()
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        self.events = deque(maxlen=200)
        self.sequence = 0
        self.error = ''
        self.active: str | None = None
        self.provider_factory = OllamaProvider
        self.manager = None

    def _migrate_legacy_evaluations(self) -> None:
        """Expose preview v1 history through the v2 direct-column contract."""
        with Session.begin() as db:
            for row in db.scalars(select(AIEvaluation).where(AIEvaluation.status == 'EVALUATED',
                                                              AIEvaluation.interest_score.is_(None))):
                old = row.result or {}
                if not old:
                    continue
                content_type = str(old.get('content_type', 'OTHER')).upper()
                tone = str(old.get('emotional_tone', 'OTHER')).upper()
                row.interest_score = old.get('interest_score')
                row.clarity_score = old.get('clarity_score')
                row.virality_score = old.get('virality_score')
                row.standalone_score = old.get('standalone_score')
                row.hook_score = old.get('hook_quality')
                row.ending_score = old.get('ending_quality')
                row.information_value_score = old.get('interest_score')
                context_score = old.get('context_score')
                row.context_dependency_score = round(10 - context_score, 1) if isinstance(context_score, (int, float)) else None
                if isinstance(row.clarity_score, (int, float)) and isinstance(row.ending_score, (int, float)):
                    row.completeness_score = round((row.clarity_score + row.ending_score) / 2, 1)
                row.content_type = content_type if content_type in CONTENT_TYPES else 'OTHER'
                row.detected_topic = old.get('detected_topic', 'unknown')
                row.emotional_tone = tone if tone in EMOTIONAL_TONES else 'OTHER'
                row.requires_context = old.get('requires_context')
                row.moment_summary = old.get('moment_summary')
                row.evaluation_reason = old.get('evaluation_reason')
                if all(getattr(row, field) is not None for field in _SCORE_FIELDS):
                    response = MomentAIEvaluation(**{field: getattr(row, field) for field in _SCORE_FIELDS},
                        content_type=row.content_type, detected_topic=row.detected_topic,
                        emotional_tone=row.emotional_tone, requires_context=row.requires_context,
                        moment_summary=row.moment_summary, evaluation_reason=row.evaluation_reason,
                        language=old.get('language', 'es'))
                    settings_snapshot = AISettings.model_validate(row.settings_snapshot)
                    row.overall_score = overall(response, settings_snapshot)
                    row.quality_level = quality_level(row.overall_score, settings_snapshot)
                    row.recommended_action = recommendation(row.overall_score, settings_snapshot)

    def load(self):
        self.queue = asyncio.Queue(maxsize=100)
        self.active = None
        self.error = ''
        with Session.begin() as db:
            row = db.get(AIConfiguration, 1)
            self.config = AISettings.model_validate(row.value) if row else AISettings()
            if row and row.value != self.config.model_dump():
                row.value = self.config.model_dump()
            for job in db.scalars(select(AIEvaluation).where(AIEvaluation.status.in_(['QUEUED', 'EVALUATING', 'RETRYING']))):
                job.status, job.error_code = 'FAILED', 'INTERRUPTED'
                job.error_message = 'Evaluación interrumpida al cerrar la aplicación. Puedes reevaluar.'
                job.updated_at = now()
        self._migrate_legacy_evaluations()

    def save(self, config: AISettings):
        with Session.begin() as db:
            row = db.get(AIConfiguration, 1)
            if row:
                row.value = config.model_dump()
            else:
                db.add(AIConfiguration(id=1, value=config.model_dump()))
        self.config = config
        self.error = ''
        return config.model_dump()

    def _cache_key(self, moment: dict, config: AISettings) -> str:
        payload = {'transcript': moment['transcript_excerpt'], 'provider': config.provider,
                   'model': config.model, 'prompt_version': VERSION, 'settings': config.model_dump()}
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def emit(self, event: str, identifier: str):
        with Session() as db:
            row = db.get(AIEvaluation, identifier)
            data = evaluation_dict(row)
        self.sequence += 1
        self.events.append({'sequence': self.sequence, 'type': event, 'data': data})
        log.info('%s moment_id=%s evaluation_id=%s', event, data['moment_id'], identifier)

    def update(self, identifier: str, **values):
        with Session.begin() as db:
            row = db.get(AIEvaluation, identifier)
            for key, value in values.items():
                setattr(row, key, value)
            row.updated_at = now()

    def enqueue(self, moment_id: str, reevaluate: bool = False, automatic: bool = False):
        config = self.config
        if not config.enabled:
            raise ValueError('Activa AI Evaluation en Settings → AI.')
        moment = get_moment(moment_id)
        if moment['status'] == 'DISMISSED':
            raise ValueError('El momento fue descartado.')
        if moment['detection_confidence'] < settings.detection_threshold:
            raise ValueError('El candidato no pasa el umbral heurístico configurado.')
        cache_key = self._cache_key(moment, config)
        with Session() as db:
            existing = db.scalars(select(AIEvaluation).where(
                AIEvaluation.moment_id == moment_id, AIEvaluation.cache_key == cache_key,
            ).order_by(AIEvaluation.created_at.desc())).first()
            if existing and not reevaluate and existing.status in ('QUEUED', 'EVALUATING', 'RETRYING', 'EVALUATED'):
                return evaluation_dict(existing)
            count = db.scalar(select(func.count()).select_from(AIEvaluation).join(Moment).where(
                Moment.stream_id == moment['stream_id'])) or 0
        if count >= config.per_stream_limit:
            raise ValueError('Límite de evaluaciones de esta transmisión alcanzado.')
        if self.queue.full():
            raise ValueError('La cola de IA está llena. Intenta más tarde.')
        identifier = uuid4().hex
        snapshot = config.model_dump()
        snapshot['automatic'] = automatic
        with Session.begin() as db:
            row = AIEvaluation(id=identifier, moment_id=moment_id, provider=config.provider, model=config.model,
                               evaluation_version=VERSION, cache_key=cache_key, settings_snapshot=snapshot)
            db.add(row)
            db.flush()
            result = evaluation_dict(row)
        self.queue.put_nowait(identifier)
        self.emit('ai_evaluation_queued', identifier)
        return result

    def candidate(self, identifier: str):
        if self.config.enabled and self.config.evaluation_mode == 'AUTOMATIC':
            try:
                self.enqueue(identifier, automatic=True)
            except ValueError as exc:
                self.error = str(exc)

    def status(self):
        metrics = statistics()
        return {'status': 'DISABLED' if not self.config.enabled else 'PROCESSING' if self.active else 'ERROR' if self.error else 'READY',
                'error': self.error, 'queued': self.queue.qsize(), 'active': self.active,
                'active_count': 1 if self.active else 0, 'provider': self.config.provider,
                'model': self.config.model, 'evaluation_mode': self.config.evaluation_mode,
                'processing_local': True, 'completed': metrics['evaluated'], 'failed': metrics['failed']}

    async def worker(self):
        while True:
            identifier = await self.queue.get()
            try:
                await self.run(identifier)
            except asyncio.CancelledError:
                self.update(identifier, status='FAILED', error_code='INTERRUPTED', error_message='Evaluación interrumpida.')
                self.emit('ai_evaluation_failed', identifier)
                raise
            except Exception:
                log.exception('AI_WORKER_FAILED evaluation_id=%s', identifier)
                self.update(identifier, status='FAILED', error_code='INTERNAL', error_message='Falló el worker de IA; puedes reevaluar.')
                self.emit('ai_evaluation_failed', identifier)
            finally:
                self.active = None
                self.queue.task_done()

    async def run(self, identifier: str):
        with Session() as db:
            job = evaluation_dict(db.get(AIEvaluation, identifier))
        saved = dict(job['settings_snapshot'])
        automatic = saved.pop('automatic', False)
        config = AISettings.model_validate(saved)
        if not self.config.enabled or (automatic and self.config.evaluation_mode != 'AUTOMATIC'):
            self.update(identifier, status='FAILED', error_code='DISABLED', error_message='Evaluación desactivada antes de comenzar.')
            self.emit('ai_evaluation_failed', identifier)
            return
        moment = get_moment(job['moment_id'])
        self.active = identifier
        self.update(identifier, status='EVALUATING')
        self.emit('ai_evaluation_started', identifier)
        # Wait for post-context asynchronously; Whisper keeps owning its own queue.
        deadline = time.monotonic() + min(60, config.post_context_seconds + 20)
        while (self.manager and any(s.stream_id == moment['stream_id'] and s.state == 'live'
                                   for s in self.manager.sessions)
               and time.monotonic() < deadline):
            with Session() as db:
                latest = db.scalar(select(func.max(Transcript.end)).where(Transcript.stream_id == moment['stream_id'])) or 0
            if latest >= moment['end'] + config.post_context_seconds:
                break
            if not self.config.enabled:
                break
            await asyncio.sleep(1)
        if not self.config.enabled:
            self.update(identifier, status='FAILED', error_code='DISABLED', error_message='IA desactivada.')
            self.emit('ai_evaluation_failed', identifier)
            return
        try:
            context = AIContextBuilder().build(moment, config)
        except ValueError as exc:
            self.update(identifier, status='FAILED', error_code='CONTEXT_LIMIT', error_message=str(exc))
            self.emit('ai_evaluation_failed', identifier)
            return
        context_meta = {key: value for key, value in context.items()
                        if key not in ('candidate', 'previous_context', 'following_context')}
        self.update(identifier, context_metadata=context_meta)
        started = time.monotonic()
        for attempt in range(config.max_retries + 1):
            if not self.config.enabled:
                self.update(identifier, status='FAILED', error_code='DISABLED', error_message='IA desactivada antes del siguiente intento.')
                self.emit('ai_evaluation_failed', identifier)
                return
            self.update(identifier, status='EVALUATING', attempts=attempt + 1)
            try:
                provider_result = await asyncio.wait_for(
                    self.provider_factory(config).evaluate_moment(context), timeout=config.timeout_seconds)
                if not isinstance(provider_result, ProviderResult):
                    raise ValueError('El proveedor no devolvió una evaluación estructurada.')
                response = provider_result.evaluation
                value = overall(response, config)
                level = quality_level(value, config)
                action = recommendation(value, config)
                stored_result = response.model_dump() | {'overall_score': value, 'quality_level': level,
                                                          'recommended_action': action}
                self.update(identifier, status='EVALUATED', result=stored_result, overall_score=value,
                            quality_level=level, recommended_action=action, input_tokens=provider_result.input_tokens,
                            output_tokens=provider_result.output_tokens, latency_ms=int((time.monotonic() - started) * 1000),
                            error_message='', error_code='', **response.model_dump())
                self.error = ''
                self.emit('ai_evaluation_completed', identifier)
                return
            except (TimeoutError, httpx.TimeoutException):
                code, message = 'FAILED_TIMEOUT', 'El modelo superó el tiempo límite. Puedes aumentarlo en Settings → AI.'
            except (ValidationError, KeyError, ValueError, TypeError):
                code, message = 'INVALID_RESPONSE', 'El modelo devolvió JSON inválido o incompleto.'
            except httpx.HTTPError:
                code, message = 'PROVIDER_UNAVAILABLE', 'Ollama no está disponible o rechazó la solicitud. Prueba la conexión.'
            if attempt < config.max_retries:
                self.update(identifier, status='RETRYING', error_code=code, error_message=message)
                await asyncio.sleep(min(2 ** attempt, 4))
        self.error = message
        self.update(identifier, status='FAILED', error_code=code, error_message=message,
                    latency_ms=int((time.monotonic() - started) * 1000))
        self.emit('ai_evaluation_failed', identifier)


ai = AIService()
