"""Evaluate recent speech with a cached rule snapshot; never create clips."""
from threading import RLock
from .repository import rules_repository
from .extractor import evaluate_text

class DetectionSignals:
    def __init__(self):
        self.lock = RLock()
        self.stream_id = None
        self.parts: list[dict] = []
        self.language = '*'
        self.result = None
        self.revision = -1

    def reset(self, stream_id: str):
        with self.lock:
            self.stream_id, self.parts, self.result = stream_id, [], None
            self.revision = -1

    def observe(self, stream_id: str, parts: list[dict], language: str):
        with self.lock:
            if self.stream_id != stream_id:
                return  # Ignore queued transcription belonging to an older session.
            self.parts.extend(parts)
            if self.parts:
                cutoff = self.parts[-1]['end'] - 60
                self.parts = [part for part in self.parts if part['end'] > cutoff][-100:]
            self.language, self.revision = language, -1

    def status(self) -> dict:
        with self.lock:
            snapshot = rules_repository.cache.snapshot
            if self.revision != snapshot.revision:
                text = ' '.join(part['text'] for part in self.parts)[-20000:]
                self.result = evaluate_text(text, self.language, snapshot)
                self.result.update(stream_id=self.stream_id,
                                   window_seconds=round(self.parts[-1]['end'] - self.parts[0]['start'], 2) if self.parts else 0,
                                   word_count=len(text.split()), has_audio=bool(self.parts))
                self.revision = snapshot.revision
            return dict(self.result)

    def window(self) -> tuple:
        with self.lock:
            return self.stream_id, [dict(part) for part in self.parts], self.language

class SignalRegistry:
    def __init__(self):
        self.lock = RLock()
        self.sessions = {}
        self.empty = DetectionSignals()
        self.latest = None

    def reset(self, stream_id):
        with self.lock:
            signal = DetectionSignals()
            signal.reset(stream_id)
            self.sessions[stream_id] = signal
            self.latest = stream_id

    def discard(self, stream_id):
        with self.lock:
            self.sessions.pop(stream_id, None)

    def get(self, stream_id=None):
        with self.lock:
            return self.sessions.get(stream_id or self.latest, self.empty)

    def observe(self, stream_id, parts, language):
        self.get(stream_id).observe(stream_id, parts, language)

    def status(self, stream_id=None):
        return self.get(stream_id).status()

    def window(self, stream_id=None):
        return self.get(stream_id).window()


signals = SignalRegistry()
