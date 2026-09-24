import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.buffer import CircularBuffer
from app.services.media import validate_url
from app.database import Session, Stream

def test_buffer_prunes_only_completed_old_segments(tmp_path):
    for name in ('segment_00000000.ts', 'segment_00000001.ts', 'segment_00000002.ts', 'in_progress.ts'):
        (tmp_path / name).write_bytes(b'video')
    (tmp_path / 'segments.csv').write_text('segment_00000000.ts,0,5\nsegment_00000001.ts,5,10\nsegment_00000002.ts,10,15\npartial,15')
    buffer = CircularBuffer(tmp_path, 10)
    assert len(buffer.refresh()) == 3
    assert len(buffer.refresh()) == 0
    assert len(buffer.select(6, 12)) == 2
    buffer.prune()
    assert not (tmp_path / 'segment_00000000.ts').exists()
    assert (tmp_path / 'in_progress.ts').exists()
    assert buffer.duration == 10

@pytest.mark.parametrize('url', ['file:///C:/secret', 'ftp://example.com', 'https://u:p@example.com', 'https://x.com\nHeader:bad'])
def test_reject_invalid_urls(url):
    with pytest.raises(ValueError):
        validate_url(url)

def test_api_database_and_origin():
    with TestClient(app) as client:
        assert client.get('/health').json()['database'] == 'connected'
        assert client.post('/clips/create').status_code == 409
        assert client.get('/clips/no-such-clip').status_code == 404
        assert client.post('/streams/start', json={'url': 'file:///bad'}).status_code == 400
        assert client.post('/streams/stop', headers={'Origin': 'https://evil.example'}).status_code == 403
        with Session.begin() as db:
            db.add(Stream(id='test', title='Persistent stream', url='https://example.com'))
        assert client.get('/streams').json()[0]['title'] == 'Persistent stream'
        with client.websocket_connect('/ws/live', headers={'Origin': 'http://127.0.0.1:5173'}) as websocket:
            assert websocket.receive_json()['stream']['state'] == 'idle'
