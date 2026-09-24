"""Real 60-second capture, Whisper and MP4 smoke test against the running API."""
import time
from pathlib import Path
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import httpx
import av
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.services.media import run_ffmpeg

root = settings.storage_dir
run_ffmpeg(['-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=25',
            '-stream_loop', '-1', '-i', str(root / 'test-speech.flac'), '-t', '75',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '2', '-c:a', 'aac',
            '-movflags', '+faststart', str(root / 'test-source.mp4')])
class FixtureHandler(SimpleHTTPRequestHandler):
    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (ConnectionResetError, BrokenPipeError):
            pass  # yt-dlp closes its metadata probe before downloading the video.

server = ThreadingHTTPServer(('127.0.0.1', 8877), partial(FixtureHandler, directory=str(root)))
threading.Thread(target=server.serve_forever, daemon=True).start()
client = httpx.Client(base_url='http://127.0.0.1:8000', timeout=60)
try:
    response = client.post('/streams/analyze', json={'url':'http://127.0.0.1:8877/test-source.mp4'})
    response.raise_for_status()
    print('ANALYZED', response.json(), flush=True)
    response = client.post('/streams/start', json={'url':'http://127.0.0.1:8877/test-source.mp4'})
    response.raise_for_status()
    deadline = time.monotonic() + 110
    while time.monotonic() < deadline:
        state = client.get('/streams/status').json()
        if state['state'] == 'error':
            raise RuntimeError(state)
        if state['buffer_seconds'] >= 31:
            break
        time.sleep(1)
    assert state['buffer_seconds'] >= 31, state
    playlist = client.get('/preview/live.m3u8')
    assert playlist.status_code == 200 and '#EXTINF' in playlist.text
    print('BUFFER_AND_PREVIEW_OK', state['buffer_seconds'], flush=True)
    response = client.post('/clips/create')
    response.raise_for_status()
    clip_id = response.json()['id']
    print('CLIP_CAPTURING', clip_id, flush=True)
    while time.monotonic() < deadline:
        clip = client.get(f'/clips/{clip_id}').json()
        if clip['status'] in ('ready','error'):
            break
        time.sleep(1)
    assert clip['status'] == 'ready', clip
    with av.open(str(root / 'clips' / clip_id / 'original.mp4')) as container:
        duration = container.duration / av.time_base
        assert 44.5 < duration < 45.5, duration
        assert len(container.streams.video) == 1
        assert len(container.streams.audio) == 1
    video = client.get(f'/clips/{clip_id}/video', headers={'Range':'bytes=0-1023'})
    assert video.status_code == 206 and len(video.content) == 1024
    while time.monotonic() < deadline:
        transcripts = client.get('/transcriptions').json()
        if transcripts:
            break
        time.sleep(1)
    assert transcripts, client.get('/streams/status').json()
    print('TRANSCRIPTION_OK', transcripts[0]['text'], flush=True)
    print('CLIP_READY duration=', duration, 'range playback=OK', flush=True)
finally:
    client.post('/streams/stop')
    client.close()
    server.shutdown()
