from pathlib import Path
import shutil
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

ROOT = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT.parent / '.env', extra='ignore')
    buffer_minutes: int = Field(10, ge=1, le=30)
    whisper_model: str = 'base'
    whisper_device: str = 'cpu'
    whisper_threads: int = Field(2, ge=1, le=8)
    capture_mode: str = Field('copy', pattern='^(copy|encode)$')
    capture_max_height: int = Field(720, ge=240, le=1080)
    ffmpeg_path: str = ''
    storage_dir: Path = ROOT / 'storage'
    detection_threshold: float = Field(.65,ge=0,le=1)
    moment_preview_budget_mb: int = Field(256,ge=32,le=2048)
    youtube_client_id: str = ''
    youtube_client_secret: str = Field('', repr=False)
    tiktok_client_key: str = ''
    tiktok_client_secret: str = Field('', repr=False)
    oauth_callback_base: str = 'http://127.0.0.1:8000'

settings = Settings()
for folder in ('buffer', 'clips', 'audio', 'logs', 'models'):
    (settings.storage_dir / folder).mkdir(parents=True, exist_ok=True)

def ffmpeg() -> str:
    if settings.ffmpeg_path:
        return settings.ffmpeg_path
    executable = shutil.which('ffmpeg')
    if executable:
        return executable
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()
