import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.database import Base, Clip, Session, Stream, engine
from app.metadata.models import ClipMetadata
from app.publishing.accounts import accounts
from app.publishing.models import PublicationJob
from app.publishing.publishers import MockSocialPublisher, PublishingError
from app.publishing.schemas import CreatePublications, PublishingSettings
from app.publishing.service import PublicationService
from app.publishing.validator import PrePublishValidator
from app.config import settings


def ready_clip(with_file=True, with_metadata=True):
    Base.metadata.create_all(engine)
    clip_id, stream_id = uuid4().hex, uuid4().hex
    with Session.begin() as db:
        db.add(Stream(id=stream_id, title='Publishing fixture', url='https://example.com'))
        db.add(Clip(id=clip_id, stream_id=stream_id, title='Clip listo', status='ready', duration=30,
                    source_start=0, source_end=30, render_status='READY', metadata_status='METADATA_READY'))
        if with_metadata:
            tags = ['#LiveClip', '#Gaming', '#Shorts']
            db.add(ClipMetadata(clip_id=clip_id, general_metadata={
                'title': 'Una reacción inesperada', 'description': 'La jugada cambió el momento.',
                'caption': 'Nadie esperaba esa reacción', 'hashtags': tags},
                platform_metadata={
                    'youtube_shorts': {'title': 'Una reacción inesperada', 'description': 'La jugada cambió el momento.', 'hashtags': tags},
                    'tiktok': {'caption': 'Nadie esperaba esa reacción', 'hashtags': tags},
                    'instagram_reels': {'caption': 'La reacción cambió el momento.', 'hashtags': tags},
                    'facebook_reels': {'caption': 'Así cambió la partida.', 'hashtags': tags}}, ai_model='test'))
    if with_file:
        directory = settings.storage_dir / 'clips' / clip_id; directory.mkdir(parents=True, exist_ok=True)
        (directory / 'vertical.mp4').write_bytes(b'fake-safe-mode-video')
    return clip_id


def request_for(clip_id, platform='youtube', scheduled_at=None, explicit=False):
    return CreatePublications(clip_id=clip_id,
        platforms=[{'platform': platform, 'account_id': f'mock-{platform}'}],
        scheduled_at=scheduled_at, explicit_republish=explicit)


async def run_queued(service, identifier):
    service.queued.discard(identifier)
    await service.run(identifier)


def test_mock_end_to_end_queue_processing_published_url_and_attempt():
    async def scenario():
        service = PublicationService(); service.load()
        clip_id = ready_clip(); job = service.create(request_for(clip_id))[0]
        assert job['status'] == 'QUEUED'
        await run_queued(service, job['id'])
        saved = service.get(job['id'])
        assert saved['status'] == 'PUBLISHED' and saved['progress'] == 100
        assert saved['publication_url'].startswith('https://mock.liveclip.local/youtube/')
        assert [row['status'] for row in service.attempts(job['id'])] == ['PUBLISHED']
        assert {'publication_queued', 'publication_started', 'publication_progress',
                'publication_processing', 'publication_completed'} <= {event['type'] for event in service.events}
    asyncio.run(scenario())


def test_idempotency_blocks_duplicate_unless_republish_is_explicit():
    async def scenario():
        service = PublicationService(); service.load(); clip_id = ready_clip()
        first = service.create(request_for(clip_id))[0]; await run_queued(service, first['id'])
        with pytest.raises(ValueError, match='ya fue publicado'):
            service.create(request_for(clip_id))
        second = service.create(request_for(clip_id, explicit=True))[0]
        assert second['id'] != first['id']
    asyncio.run(scenario())


def test_retriable_failure_creates_attempts_and_other_platform_is_independent():
    class Flaky(MockSocialPublisher):
        calls = 0
        async def publish(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1: raise PublishingError('NETWORK_ERROR', 'temporal', True)
            return await super().publish(*args, **kwargs)
    async def scenario():
        service = PublicationService(); service.load(); service.retry_delays = (0, 0, 0)
        flaky = Flaky('youtube'); service.publisher_factory = lambda platform: flaky if platform == 'youtube' else MockSocialPublisher(platform)
        clip_id = ready_clip(); youtube = service.create(request_for(clip_id))[0]
        tiktok = service.create(request_for(clip_id, 'tiktok'))[0]
        await run_queued(service, youtube['id']); await run_queued(service, tiktok['id'])
        assert service.get(youtube['id'])['status'] == 'PUBLISHED'
        assert len(service.attempts(youtube['id'])) == 2
        assert service.get(tiktok['id'])['status'] == 'PUBLISHED'
    asyncio.run(scenario())


def test_schedule_cancel_and_restart_recovers_missed_job():
    service = PublicationService(); service.load(); clip_id = ready_clip()
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    cancelled = service.create(request_for(clip_id, scheduled_at=future))[0]
    assert cancelled['status'] == 'SCHEDULED'
    assert service.cancel(cancelled['id'])['status'] == 'CANCELLED'
    overdue = service.create(request_for(clip_id, 'tiktok', scheduled_at=future))[0]
    service.update(overdue['id'], scheduled_at=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat())
    restored = PublicationService(); restored.load()
    assert restored.get(overdue['id'])['status'] == 'QUEUED'
    assert restored.queue.qsize() >= 1


def test_validator_rejects_missing_media_metadata_and_wrong_account():
    service = PublicationService(); service.load(); config = PublishingSettings()
    clip_id = ready_clip(with_file=False)
    with pytest.raises(PublishingError) as missing:
        PrePublishValidator().prepare(clip_id, 'youtube', 'mock-youtube', {}, config)
    assert missing.value.code == 'INVALID_MEDIA'
    another = ready_clip(with_metadata=False)
    with pytest.raises(PublishingError) as no_metadata:
        PrePublishValidator().prepare(another, 'youtube', 'mock-youtube', {}, config)
    assert no_metadata.value.code == 'INVALID_METADATA'
    valid = ready_clip()
    with pytest.raises(PublishingError) as wrong_account:
        PrePublishValidator().prepare(valid, 'youtube', 'mock-tiktok', {}, config)
    assert wrong_account.value.code == 'AUTH_ERROR'


def test_safe_mode_capabilities_and_default_review_policy():
    service = PublicationService(); service.load()
    assert service.config.safe_publish_mode is True
    assert service.config.publication_workflow == 'REVIEW' and service.config.auto_publish is False
    capabilities = accounts.capabilities(service.mock_mode)
    assert all(row['configured'] and row['capabilities']['publish_now'] for row in capabilities)
