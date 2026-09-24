import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading
import time

import pytest

from app.detection.runtime import SignalRegistry
from app.services.stream import StreamManager, StreamPool
from app.services.transcription import TranscriptionEngine
from app.services import media
from fastapi.testclient import TestClient
from app import main
from app.database import Base, engine as database_engine
from app.services.buffer import CircularBuffer


def test_two_slots_stop_independently_and_reject_ambiguous_clip(monkeypatch):
    async def start(session, url):
        await asyncio.sleep(0)
        session.stream_id = url
        session.info = {'source_url': url, 'title': url}
        session.state = 'live'
        return session.snapshot()

    async def stop(session):
        session.state = 'idle'

    monkeypatch.setattr(StreamManager, 'start', start)
    monkeypatch.setattr(StreamManager, 'stop', stop)

    async def scenario():
        pool = StreamPool()
        results = await asyncio.gather(*(pool.start(url) for url in ('one', 'two', 'three')),
                                       return_exceptions=True)
        assert sum(isinstance(result, ValueError) for result in results) == 1
        assert len(pool.sessions) == 2
        assert all(s.transcription is pool.transcription for s in pool.sessions)
        with pytest.raises(ValueError, match='Selecciona'):
            pool.get()
        with pytest.raises(ValueError):
            pool.get('missing')
        await pool.stop('one')
        assert pool.get('two').state == 'live'
        assert pool.get('one').state == 'idle'
        with pytest.raises(ValueError, match='ya se está grabando'):
            await pool.start('two')
        await pool.start('three')
        assert {s.stream_id for s in pool.sessions} == {'two', 'three'}
        await pool.stop()
        assert all(s.state == 'idle' for s in pool.sessions)

    asyncio.run(scenario())


def test_signals_do_not_mix_or_reset_other_source():
    registry = SignalRegistry()
    registry.reset('one')
    registry.observe('one', [{'start': 0, 'end': 5, 'text': 'first source'}], 'en')
    registry.reset('two')
    registry.observe('two', [{'start': 10, 'end': 15, 'text': 'segunda fuente'}], 'es')
    assert registry.window('one')[1][0]['text'] == 'first source'
    assert registry.window('two')[1][0]['text'] == 'segunda fuente'
    registry.discard('one')
    registry.observe('one', [{'start': 5, 'end': 10, 'text': 'stale'}], 'en')
    assert registry.window('two')[1][0]['text'] == 'segunda fuente'
    assert not registry.window('one')[1]


def test_transcription_has_bounded_space_for_each_source(tmp_path):
    engine = TranscriptionEngine()
    for i in range(6):
        assert engine.can_enqueue('one')
        engine.enqueue(tmp_path / str(i), 'one', i * 5)
    assert not engine.can_enqueue('one')
    assert engine.can_enqueue('two')
    for i in range(6):
        engine.enqueue(tmp_path / str(i), 'two', i * 5)
    assert engine.queue.qsize() == 12
    assert not engine.can_enqueue('two')


def test_offline_ffmpeg_jobs_are_serialized_and_release_slot(monkeypatch):
    lock = threading.Lock()
    running = 0
    peak = 0

    def run(*args, **kwargs):
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(.02)
        with lock:
            running -= 1
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(media.subprocess, 'run', run)
    monkeypatch.setattr(media, 'ffmpeg', lambda: 'ffmpeg')
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: media.run_ffmpeg(['-version']), range(8)))
    assert peak == 1

    def fail(*args, **kwargs):
        raise RuntimeError('failed')

    monkeypatch.setattr(media.subprocess, 'run', fail)
    with pytest.raises(RuntimeError):
        media.run_ffmpeg([])
    assert media.media_slot.acquire(blocking=False)
    media.media_slot.release()


def test_api_routes_clips_and_stop_to_requested_source(tmp_path, monkeypatch):
    Base.metadata.create_all(database_engine)
    pool = StreamPool()
    for identifier in ('api-one', 'api-two'):
        directory = tmp_path / identifier
        directory.mkdir()
        (directory / 'segment_00000000.ts').write_bytes(identifier.encode())
        (directory / 'segments.csv').write_text('segment_00000000.ts,0,35\n')
        session = StreamManager(pool.transcription)
        session.stream_id = identifier
        session.info = {'title': identifier}
        session.state = 'live'
        session.buffer = CircularBuffer(directory, 60)
        session.buffer.refresh()
        pool.sessions.append(session)

    async def stop(session):
        session.state = 'idle'
        session.clips.fail_pending()

    monkeypatch.setattr(StreamManager, 'stop', stop)
    monkeypatch.setattr(main, 'manager', pool)
    client = TestClient(main.app)
    try:
        assert client.post('/clips/create').status_code == 409
        assert client.post('/clips/create?stream_id=unknown').status_code == 409
        first = client.post('/clips/create?stream_id=api-one')
        second = client.post('/clips/create?stream_id=api-two')
        assert first.status_code == second.status_code == 202
        assert first.json()['stream_id'] == 'api-one'
        assert second.json()['stream_id'] == 'api-two'
        assert client.post('/clips/create?stream_id=api-one').status_code == 202
        assert client.post('/clips/create?stream_id=api-two').status_code == 409
        assert client.post('/streams/stop?stream_id=unknown').status_code == 404
        assert client.post('/streams/stop?stream_id=api-one').status_code == 200
        assert pool.get('api-two').state == 'live'
        assert len(client.get('/streams/active').json()) == 2
        assert client.post('/streams/stop').status_code == 200
        assert all(s.state == 'idle' for s in pool.sessions)
    finally:
        for session in pool.sessions:
            session.clips.fail_pending()
        client.close()
