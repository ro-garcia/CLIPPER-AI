import subprocess
from threading import BoundedSemaphore
from urllib.parse import urlparse
import yt_dlp
from ..config import ffmpeg, settings

CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
media_slot = BoundedSemaphore(1)

def run_ffmpeg(arguments: list[str], timeout=180):
    # Capture has its own lightweight process; offline media jobs share one slot.
    with media_slot:
        result = subprocess.run([ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y',
                                 '-threads', '2', '-filter_threads', '1', *arguments],
                                capture_output=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-1500:])

def validate_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Utiliza una URL HTTP o HTTPS sin credenciales.')
    if any(c in url for c in '\r\n\x00'):
        raise ValueError('URL inválida.')
    return url

def analyze(url: str):
    validate_url(url)
    options = {'quiet': True, 'no_warnings': True, 'skip_download': True,
               'noplaylist': True, 'socket_timeout': 20,
               'format': f'best[height<={settings.capture_max_height}][vcodec!=none][acodec!=none]/best[height<={settings.capture_max_height}]/best'}
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=False)
    if not info or not info.get('url'):
        raise ValueError('No se encontró una fuente audiovisual compatible.')
    validate_url(info['url'])
    if info.get('has_drm'):
        raise ValueError('Las fuentes con DRM no son compatibles.')
    return {'title': info.get('title', 'Transmisión'), 'platform': info.get('extractor_key', 'HTTP'),
            'thumbnail': info.get('thumbnail'), 'width': info.get('width'), 'height': info.get('height'),
            'fps': info.get('fps'), 'is_live': bool(info.get('is_live')), 'source_url': url,
            'media_url': info['url'], 'headers': info.get('http_headers', {})}
