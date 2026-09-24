from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine
from app.services.clip_settings import ClipTiming, get_timing, save_timing
from app.config import settings


def test_clip_timing_persistence_and_validation(monkeypatch):
    Base.metadata.create_all(engine)
    previous = get_timing()
    client = TestClient(app)
    try:
        response = client.put('/settings/clips', json={'before_seconds': 40, 'after_seconds': 20})
        assert response.status_code == 200
        # A new database session reads the saved value.
        assert get_timing() == {'before_seconds': 40, 'after_seconds': 20}
        assert client.get('/settings/clips').json() == get_timing()
        for before, after in [(0, 20), (40, -1), (300, 1), (1.5, 20), (True, 20)]:
            assert client.put('/settings/clips', json={'before_seconds': before, 'after_seconds': after}).status_code == 422
        monkeypatch.setattr(settings, 'buffer_minutes', 1)
        assert client.put('/settings/clips', json={'before_seconds': 61, 'after_seconds': 0}).status_code == 422
        assert client.put('/settings/clips', json={'before_seconds': 60, 'after_seconds': 0}).status_code == 200
    finally:
        save_timing(ClipTiming(**previous))
        client.close()
