"""Real FFmpeg capture and isolated clips from two synthetic HTTP streams (~60s)."""
import asyncio
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

import av

from app.config import settings
from app.database import Base, Clip, Session, engine
from app.services import stream
from app.services.media import run_ffmpeg
from app.services.clip_settings import ClipTiming, save_timing, get_timing


def test_real_dual_capture_and_clips(tmp_path, monkeypatch):
    Base.metadata.create_all(engine)
    for color in ('red', 'blue'):
        run_ffmpeg(['-f', 'lavfi', '-i', f'color=c={color}:s=320x180:r=25',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000',
                    '-t', '85', '-c:v', 'libx264', '-threads', '2', '-preset', 'ultrafast',
                    '-g', '50', '-c:a', 'aac', '-movflags', '+faststart', str(tmp_path / f'{color}.mp4')])

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def copyfile(self, source, outputfile):
            try:
                super().copyfile(source, outputfile)
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(tmp_path)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(stream, 'analyze', lambda url: {
        'title': url.rsplit('/', 1)[-1], 'media_url': url, 'source_url': url, 'headers': {}})
    monkeypatch.setattr(settings, 'capture_mode', 'copy')

    async def scenario():
        pool = stream.StreamPool()
        previous = get_timing()
        try:
            for color in ('red', 'blue'):
                await pool.start(f'http://127.0.0.1:{server.server_port}/{color}.mp4')
            first, second = pool.sessions
            deadline = time.monotonic() + 95
            while min(s.buffer.duration for s in pool.sessions) < 32:
                assert all(s.state != 'error' for s in pool.sessions), pool.snapshots()
                assert time.monotonic() < deadline, pool.snapshots()
                await asyncio.sleep(.25)
            clips = []
            for s, before, after in ((first, 20, 10), (second, 30, 15)):
                save_timing(ClipTiming(before_seconds=before, after_seconds=after))
                clips.append(s.clips.create(s.stream_id, s.info['title'], s.buffer, s.media_time))
            # Subsequent settings changes must not alter already-pending jobs.
            save_timing(ClipTiming(before_seconds=10, after_seconds=0))
            while True:
                with Session() as db:
                    statuses = [db.get(Clip, c['id']).status for c in clips]
                assert 'error' not in statuses
                if statuses == ['ready', 'ready']:
                    break
                assert time.monotonic() < deadline, statuses
                await asyncio.sleep(.25)
            await pool.stop(first.stream_id)
            assert first.state == 'idle'
            assert second.state == 'live'
            assert pool.transcription.queue.qsize() <= 12
            for index, clip in enumerate(clips):
                with Session() as db:
                    assert db.get(Clip, clip['id']).stream_id == pool.sessions[index].stream_id
                with av.open(str(settings.storage_dir / 'clips' / clip['id'] / 'original.mp4')) as video:
                    expected = 30 if index == 0 else 45
                    assert expected - .5 < video.duration / av.time_base < expected + .5
                    assert len(video.streams.audio) == 1
                    pixels = next(video.decode(video=0)).to_ndarray(format='rgb24')
                    red, _, blue = pixels[90, 160]
                    assert (int(red) > int(blue) + 100) if index == 0 else (int(blue) > int(red) + 100)
        finally:
            save_timing(ClipTiming(**previous))
            await pool.stop()
            await pool.finish_clips()
            while not pool.transcription.queue.empty():
                path, _, _ = pool.transcription.queue.get_nowait()
                path.unlink(missing_ok=True)
                pool.transcription.queue.task_done()

    try:
        asyncio.run(scenario())
    finally:
        server.shutdown()
        server.server_close()
