from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
import logging
from uuid import uuid4

import httpx
from sqlalchemy import select

from ..database import Session, serialize
from ..ai.models import AIEvaluation
from ..moments.models import Moment
from ..detection.models import now
from .accounts import accounts
from .models import (PublicationAttempt, PublicationJob, PublishingConfiguration,
                     SocialAccount)
from .publishers import MockSocialPublisher, PublishingError
from .schemas import CreatePublications, PublishingSettings
from .validator import PrePublishValidator

log = logging.getLogger(__name__)


def job_dict(row: PublicationJob) -> dict:
    data = serialize(row)
    with Session() as db:
        account = db.get(SocialAccount, row.account_id)
        data['account_name'] = account.display_name if account else 'Unknown account'
        data['account_mode'] = account.provider_mode if account else ''
    return data


class PublicationService:
    def __init__(self):
        self.config = PublishingSettings()
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
        self.queued: set[str] = set()
        self.events = deque(maxlen=300)
        self.sequence = 0
        self.active: set[str] = set()
        self.semaphore = asyncio.Semaphore(2)
        self.retry_delays = (5, 15, 45, 90)
        self.validator = PrePublishValidator()
        self.publisher_factory = None

    @property
    def mock_mode(self) -> bool:
        return self.config.safe_publish_mode or self.config.publishing_mode == 'mock'

    def load(self):
        self.queue = asyncio.Queue(maxsize=200); self.queued.clear(); self.active.clear()
        with Session.begin() as db:
            stored = db.get(PublishingConfiguration, 1)
            self.config = PublishingSettings.model_validate(stored.value) if stored else PublishingSettings()
            for row in db.scalars(select(PublicationJob).where(
                    PublicationJob.status.in_(['VALIDATING', 'UPLOADING', 'PROCESSING', 'RETRYING']))):
                row.status, row.error_code = 'FAILED', 'INTERRUPTED_UNCERTAIN'
                row.last_error = 'La aplicación se cerró durante una operación remota. Revisa la plataforma antes de reintentar.'
                row.updated_at = now()
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent_publications)
        accounts.load(self.mock_mode)
        with Session() as db:
            queued = list(db.scalars(select(PublicationJob.id).where(PublicationJob.status == 'QUEUED')))
        for identifier in queued:
            self._queue(identifier)
        self.scheduler_tick()

    def save(self, config: PublishingSettings) -> dict:
        if not config.safe_publish_mode and config.publishing_mode != 'real':
            raise ValueError('Desactiva Safe Mode únicamente junto con publishing_mode=real.')
        with Session.begin() as db:
            row = db.get(PublishingConfiguration, 1)
            if row: row.value = config.model_dump()
            else: db.add(PublishingConfiguration(id=1, value=config.model_dump()))
        self.config = config
        if not self.active:
            self.semaphore = asyncio.Semaphore(config.max_concurrent_publications)
        accounts.load(self.mock_mode)
        return config.model_dump()

    def status(self) -> dict:
        with Session() as db:
            scheduled = len(list(db.scalars(select(PublicationJob.id).where(PublicationJob.status == 'SCHEDULED'))))
        return {'status': 'PROCESSING' if self.active else 'READY', 'safe_publish_mode': self.config.safe_publish_mode,
                'publishing_mode': 'mock' if self.mock_mode else 'real', 'active': list(self.active),
                'active_count': len(self.active), 'queued': self.queue.qsize(), 'scheduled': scheduled,
                'max_concurrent_publications': self.config.max_concurrent_publications}

    def jobs(self, clip_id: str | None = None, limit: int = 250) -> list[dict]:
        with Session() as db:
            query = select(PublicationJob)
            if clip_id: query = query.where(PublicationJob.clip_id == clip_id)
            rows = db.scalars(query.order_by(PublicationJob.created_at.desc()).limit(limit))
            return [job_dict(row) for row in rows]

    def attempts(self, job_id: str) -> list[dict]:
        with Session() as db:
            rows = db.scalars(select(PublicationAttempt).where(PublicationAttempt.job_id == job_id)
                              .order_by(PublicationAttempt.attempt_number))
            return [serialize(row) for row in rows]

    def create(self, request: CreatePublications) -> list[dict]:
        if not self.config.social_publishing_enabled:
            raise ValueError('Social Publishing está desactivado.')
        scheduled = request.scheduled_at.astimezone(timezone.utc) if request.scheduled_at else None
        created: list[str] = []
        for selection in request.platforms:
            self.validator.prepare(request.clip_id, selection.platform, selection.account_id,
                                   selection.overrides, self.config)
            publisher = self._publisher(selection.platform)
            if scheduled and not publisher.capabilities.get('schedule'):
                raise ValueError(f'{selection.platform.title()} no admite programación con la configuración actual.')
            with Session() as db:
                duplicate = db.scalar(select(PublicationJob).where(
                    PublicationJob.clip_id == request.clip_id,
                    PublicationJob.platform == selection.platform,
                    PublicationJob.account_id == selection.account_id,
                    PublicationJob.status.in_(['QUEUED', 'SCHEDULED', 'VALIDATING', 'UPLOADING',
                                               'PROCESSING', 'PUBLISHED', 'RETRYING']))
                    .order_by(PublicationJob.created_at.desc()))
            if duplicate and not request.explicit_republish:
                if duplicate.status == 'PUBLISHED':
                    raise ValueError('Este clip ya fue publicado en esta cuenta.')
                created.append(duplicate.id)
                continue
            identifier = uuid4().hex
            status = 'SCHEDULED' if scheduled and scheduled > datetime.now(timezone.utc) else 'QUEUED'
            with Session.begin() as db:
                db.add(PublicationJob(id=identifier, clip_id=request.clip_id, platform=selection.platform,
                    account_id=selection.account_id, status=status,
                    scheduled_at=scheduled.isoformat() if scheduled else '', overrides=selection.overrides,
                    explicit_republish=request.explicit_republish))
            created.append(identifier)
            self.emit('publication_scheduled' if status == 'SCHEDULED' else 'publication_queued', identifier)
            if status == 'QUEUED': self._queue(identifier)
            log.info('PUBLICATION_JOB_CREATED job_id=%s clip_id=%s platform=%s', identifier, request.clip_id, selection.platform)
        return [self.get(identifier) for identifier in created]

    def get(self, identifier: str) -> dict:
        with Session() as db:
            row = db.get(PublicationJob, identifier)
            if not row: raise ValueError('Publication Job no encontrado.')
            return job_dict(row)

    def _queue(self, identifier: str):
        if identifier not in self.queued:
            self.queue.put_nowait(identifier); self.queued.add(identifier)

    def emit(self, event: str, identifier: str):
        self.sequence += 1
        self.events.append({'sequence': self.sequence, 'type': event, 'data': self.get(identifier)})

    def update(self, identifier: str, **values):
        with Session.begin() as db:
            row = db.get(PublicationJob, identifier)
            if not row: raise ValueError('Publication Job no encontrado.')
            for key, value in values.items(): setattr(row, key, value)
            row.updated_at = now()

    def _publisher(self, platform: str):
        if self.publisher_factory:
            return self.publisher_factory(platform)
        return accounts.publisher(platform, self.mock_mode)

    async def worker(self):
        while True:
            identifier = await self.queue.get(); self.queued.discard(identifier)
            try:
                async with self.semaphore:
                    await self.run(identifier)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception('PUBLICATION_WORKER_FAILED job_id=%s', identifier)
                self._fail(identifier, 'UNKNOWN_ERROR', 'Error interno del worker de publicación.')
            finally:
                self.active.discard(identifier); self.queue.task_done()

    async def run(self, identifier: str):
        job = self.get(identifier)
        if job['status'] not in ('QUEUED', 'RETRYING'): return
        self.active.add(identifier)
        starting_attempt = job['attempt_count']
        for number in range(starting_attempt + 1, starting_attempt + self.config.max_retry_attempts + 1):
            if self.get(identifier)['status'] == 'CANCELLED':
                return
            self.update(identifier, status='VALIDATING', started_at=job['started_at'] or now(),
                        attempt_count=number, error_code='', last_error='', progress=None, stage='validating')
            self.emit('publication_started', identifier)
            attempt_id = self._attempt(identifier, number)
            try:
                current = self.get(identifier)
                path, payload, account = self.validator.prepare(current['clip_id'], current['platform'],
                    current['account_id'], current['overrides'], self.config)
                credentials = await accounts.credentials(current['account_id'])
                publisher = self._publisher(current['platform'])

                async def progress(stage: str, percent: int | None):
                    status = 'PROCESSING' if stage == 'PROCESSING' else 'UPLOADING'
                    self.update(identifier, status=status, stage=stage.lower(), progress=percent)
                    self.emit('publication_processing' if status == 'PROCESSING' else 'publication_progress', identifier)

                result = await publisher.publish(identifier, path, payload, account, credentials, progress)
                if result.status == 'PROCESSING':
                    self.update(identifier, status='PROCESSING', stage='platform_processing', progress=None,
                                platform_media_id=result.platform_media_id, publication_url=result.publication_url)
                    self._finish_attempt(attempt_id, 'PROCESSING')
                    self.emit('publication_processing', identifier)
                else:
                    self.update(identifier, status='PUBLISHED', stage='published', progress=100,
                                platform_media_id=result.platform_media_id, publication_url=result.publication_url,
                                published_at=now())
                    self._finish_attempt(attempt_id, 'PUBLISHED')
                    self.emit('publication_completed', identifier)
                return
            except PublishingError as exc:
                self._finish_attempt(attempt_id, 'FAILED', exc.code, str(exc))
                if exc.retriable and number - starting_attempt < self.config.max_retry_attempts:
                    self.update(identifier, status='RETRYING', error_code=exc.code, last_error=str(exc), stage='retrying')
                    self.emit('publication_retrying', identifier)
                    await asyncio.sleep(self.retry_delays[min(number - 1, len(self.retry_delays) - 1)])
                    continue
                status = 'AUTH_REQUIRED' if exc.code in ('AUTH_ERROR', 'PERMISSION_ERROR') else 'FAILED'
                self.update(identifier, status=status, error_code=exc.code, last_error=str(exc), stage='failed', progress=None)
                self.emit('publication_failed', identifier); return
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                self._finish_attempt(attempt_id, 'FAILED', 'NETWORK_ERROR', 'Error temporal de red.')
                if number - starting_attempt < self.config.max_retry_attempts:
                    self.update(identifier, status='RETRYING', error_code='NETWORK_ERROR', last_error='Error temporal de red.')
                    self.emit('publication_retrying', identifier)
                    await asyncio.sleep(self.retry_delays[min(number - 1, len(self.retry_delays) - 1)]); continue
                self._fail(identifier, 'NETWORK_ERROR', 'No fue posible contactar la plataforma.'); return

    def _attempt(self, job_id: str, number: int) -> int:
        with Session.begin() as db:
            row = PublicationAttempt(job_id=job_id, attempt_number=number, status='STARTED')
            db.add(row); db.flush(); return row.id

    def _finish_attempt(self, identifier: int, status: str, code: str = '', message: str = ''):
        with Session.begin() as db:
            row = db.get(PublicationAttempt, identifier)
            row.status, row.error_code, row.error_message, row.finished_at = status, code, message[:1000], now()

    def _fail(self, identifier: str, code: str, message: str):
        self.update(identifier, status='FAILED', error_code=code, last_error=message, stage='failed', progress=None)
        self.emit('publication_failed', identifier)

    def cancel(self, identifier: str) -> dict:
        job = self.get(identifier)
        if job['status'] not in ('QUEUED', 'SCHEDULED', 'RETRYING'):
            raise ValueError('Este job ya no se puede cancelar de forma segura.')
        self.update(identifier, status='CANCELLED', stage='cancelled')
        self.emit('publication_cancelled', identifier)
        return self.get(identifier)

    def retry(self, identifier: str) -> dict:
        job = self.get(identifier)
        if job['status'] not in ('FAILED', 'AUTH_REQUIRED'):
            raise ValueError('Solo se pueden reintentar jobs fallidos.')
        self.validator.prepare(job['clip_id'], job['platform'], job['account_id'], job['overrides'], self.config)
        self.update(identifier, status='QUEUED', error_code='', last_error='', stage='queued')
        self._queue(identifier); self.emit('publication_queued', identifier)
        return self.get(identifier)

    def scheduler_tick(self):
        current = datetime.now(timezone.utc)
        with Session() as db:
            rows = list(db.scalars(select(PublicationJob).where(PublicationJob.status == 'SCHEDULED')))
        for row in rows:
            if not row.scheduled_at or datetime.fromisoformat(row.scheduled_at) > current: continue
            if self.config.missed_schedule_policy == 'ASK_USER': continue
            if self.config.missed_schedule_policy == 'CANCEL':
                self.update(row.id, status='CANCELLED', stage='missed_schedule')
                self.emit('publication_cancelled', row.id)
            else:
                self.update(row.id, status='QUEUED', stage='queued')
                self._queue(row.id); self.emit('publication_queued', row.id)

    async def scheduler(self):
        while True:
            self.scheduler_tick()
            await self.poll_processing()
            await asyncio.sleep(2)

    async def poll_processing(self):
        if self.mock_mode:
            return
        with Session() as db:
            rows = list(db.scalars(select(PublicationJob).where(PublicationJob.status == 'PROCESSING')))
        for row in rows:
            publisher = self._publisher(row.platform)
            if not publisher.capabilities.get('status_check') or not row.platform_media_id:
                continue
            try:
                credentials = await accounts.credentials(row.account_id)
                result = await publisher.get_status(row.platform_media_id, credentials)
                if result.get('status') == 'PUBLISHED':
                    self.update(row.id, status='PUBLISHED', stage='published', progress=100,
                                platform_media_id=result.get('platform_media_id', row.platform_media_id),
                                publication_url=result.get('publication_url', ''), published_at=now())
                    self.emit('publication_completed', row.id)
                elif result.get('status') == 'FAILED':
                    self._fail(row.id, 'PROCESSING_ERROR', result.get('error', 'La plataforma no pudo procesar el video.'))
            except PublishingError as exc:
                if not exc.retriable:
                    self._fail(row.id, exc.code, str(exc))

    def auto_publish(self, clip_id: str):
        """Conservative extension point; defaults keep it completely inactive."""
        if not (self.config.auto_publish and self.config.publication_workflow == 'AUTOMATIC'):
            return
        with Session() as db:
            moment = db.scalar(select(Moment).where(Moment.clip_id == clip_id))
            evaluation = (db.scalar(select(AIEvaluation).where(
                AIEvaluation.moment_id == moment.id, AIEvaluation.status == 'EVALUATED'
            ).order_by(AIEvaluation.created_at.desc())) if moment else None)
            if not evaluation or (evaluation.overall_score or 0) < self.config.minimum_score:
                return
            if self.config.allowed_content_types and evaluation.content_type not in self.config.allowed_content_types:
                return
            if evaluation.content_type in self.config.blocked_content_types:
                return
            selections = []
            for platform in self.config.auto_publish_platforms:
                account = db.scalar(select(SocialAccount).where(
                    SocialAccount.platform == platform, SocialAccount.status == 'CONNECTED',
                    SocialAccount.provider_mode == ('mock' if self.mock_mode else 'real')))
                if account:
                    selections.append({'platform': platform, 'account_id': account.id})
        if selections:
            from .schemas import CreatePublications
            self.create(CreatePublications(clip_id=clip_id, platforms=selections))


publishing = PublicationService()
