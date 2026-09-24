from __future__ import annotations

from pathlib import Path
from sqlalchemy import select

from ..config import settings
from ..database import Clip, Session, serialize
from ..metadata.models import ClipMetadata
from .models import SocialAccount
from .publishers import PublishingError


class PrePublishValidator:
    def prepare(self, clip_id: str, platform: str, account_id: str,
                overrides: dict, config) -> tuple[Path, dict, dict]:
        with Session() as db:
            clip = db.get(Clip, clip_id)
            account = db.get(SocialAccount, account_id)
            metadata = db.scalar(select(ClipMetadata).where(ClipMetadata.clip_id == clip_id))
            if not clip:
                raise PublishingError('INVALID_MEDIA', 'Clip no encontrado.')
            if clip.status != 'ready' or clip.render_status != 'READY' or clip.metadata_status != 'METADATA_READY':
                raise PublishingError('INVALID_MEDIA', 'El clip todavía no está READY TO PUBLISH.')
            if not metadata:
                raise PublishingError('INVALID_METADATA', 'El clip no tiene metadata de Fase 6.')
            if not account or account.platform != platform:
                raise PublishingError('AUTH_ERROR', 'La cuenta no corresponde a la plataforma.')
            if account.status != 'CONNECTED':
                raise PublishingError('AUTH_ERROR', 'La cuenta no está conectada.')
            account_data = serialize(account)
            general, platforms = metadata.general_metadata, metadata.platform_metadata
        if not getattr(config, f'{platform}_enabled'):
            raise PublishingError('PLATFORM_ERROR', 'La plataforma está desactivada en Settings.')
        if config.safe_publish_mode and account_data['provider_mode'] != 'mock':
            raise PublishingError('AUTH_ERROR', 'Safe Mode solo permite cuentas de prueba.')
        if not config.safe_publish_mode and config.publishing_mode == 'real' and account_data['provider_mode'] != 'real':
            raise PublishingError('AUTH_ERROR', 'Selecciona una cuenta OAuth real.')
        path = settings.storage_dir / 'clips' / clip_id / 'vertical.mp4'
        if not path.is_file() or path.stat().st_size <= 0:
            raise PublishingError('INVALID_MEDIA', 'No se encontró el MP4 vertical final.')
        platform_key = {'youtube': 'youtube_shorts', 'tiktok': 'tiktok',
                        'instagram': 'instagram_reels', 'facebook': 'facebook_reels'}[platform]
        payload = dict(platforms.get(platform_key, {}))
        if platform == 'youtube':
            payload.setdefault('title', general.get('title', ''))
            payload.setdefault('description', general.get('description', ''))
            payload['privacy_status'] = config.youtube_privacy_status
        else:
            payload.setdefault('caption', general.get('caption', ''))
        payload.setdefault('hashtags', general.get('hashtags', []))
        allowed = {'title', 'description', 'caption', 'hashtags', 'privacy_status'}
        for key, value in overrides.items():
            if key in allowed:
                payload[key] = value
        self._metadata(platform, payload)
        return path, payload, account_data

    @staticmethod
    def _metadata(platform: str, payload: dict):
        if platform == 'youtube':
            if not str(payload.get('title', '')).strip() or len(str(payload['title'])) > 100:
                raise PublishingError('INVALID_METADATA', 'YouTube requiere un título de hasta 100 caracteres.')
            if len(str(payload.get('description', ''))) > 5000:
                raise PublishingError('INVALID_METADATA', 'La descripción de YouTube supera 5000 caracteres.')
        else:
            caption = str(payload.get('caption', '')) + ' ' + ' '.join(payload.get('hashtags', []))
            limit = 2200 if platform in ('tiktok', 'instagram') else 5000
            if not caption.strip() or len(caption) > limit:
                raise PublishingError('INVALID_METADATA', f'El caption de {platform.title()} no es válido.')
