from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable
from uuid import uuid4

import httpx

Progress = Callable[[str, int | None], Awaitable[None]]


@dataclass(frozen=True)
class PublishResult:
    platform_media_id: str
    publication_url: str
    status: str = 'PUBLISHED'


class PublishingError(Exception):
    def __init__(self, code: str, message: str, retriable: bool = False):
        super().__init__(message)
        self.code, self.retriable = code, retriable


class SocialPublisher(ABC):
    platform = ''
    support = 'SUPPORTED'
    capabilities = {'publish_now': True, 'schedule': True, 'delete': False,
                    'status_check': False, 'analytics': False, 'cancel_upload': False}

    async def connect(self):
        raise PublishingError('AUTH_ERROR', 'Utiliza OAuth oficial desde Social Accounts.')

    async def disconnect(self):
        return None

    def validate_connection(self, account: dict, credentials: dict):
        if account.get('status') != 'CONNECTED' or not credentials.get('access_token'):
            raise PublishingError('AUTH_ERROR', 'La cuenta requiere autorización.')

    def validate_media(self, path: Path):
        if not path.is_file() or path.stat().st_size <= 0:
            raise PublishingError('INVALID_MEDIA', 'El video final no existe o está vacío.')
        if path.suffix.lower() != '.mp4':
            raise PublishingError('INVALID_MEDIA', 'La plataforma requiere un MP4 compatible.')

    def validate_metadata(self, metadata: dict):
        if not metadata:
            raise PublishingError('INVALID_METADATA', 'Falta metadata para esta plataforma.')

    @abstractmethod
    async def publish(self, job_id: str, path: Path, metadata: dict, account: dict,
                      credentials: dict, progress: Progress) -> PublishResult: ...

    async def schedule(self, *args, **kwargs):
        raise PublishingError('PLATFORM_ERROR', 'La programación se administra localmente.')

    async def get_status(self, *args, **kwargs):
        return {'status': 'UNKNOWN'}

    async def cancel_if_supported(self, *args, **kwargs):
        return False


class MockSocialPublisher(SocialPublisher):
    def __init__(self, platform: str, fail_code: str = ''):
        self.platform, self.fail_code = platform, fail_code

    def validate_connection(self, account: dict, credentials: dict):
        if account.get('status') != 'CONNECTED' or account.get('provider_mode') != 'mock':
            raise PublishingError('AUTH_ERROR', 'Selecciona una cuenta de prueba conectada.')

    async def publish(self, job_id, path, metadata, account, credentials, progress):
        self.validate_connection(account, credentials); self.validate_media(path); self.validate_metadata(metadata)
        await progress('UPLOADING', 15); await asyncio.sleep(.02)
        if self.fail_code:
            raise PublishingError(self.fail_code, 'Fallo simulado del publisher.',
                                  self.fail_code in ('NETWORK_ERROR', 'RATE_LIMIT'))
        await progress('UPLOADING', 70); await asyncio.sleep(.02)
        await progress('PROCESSING', None); await asyncio.sleep(.02)
        media_id = f'mock-{self.platform}-{uuid4().hex[:12]}'
        return PublishResult(media_id, f'https://mock.liveclip.local/{self.platform}/{media_id}')


class YouTubePublisher(SocialPublisher):
    platform = 'youtube'
    capabilities = SocialPublisher.capabilities | {'status_check': True}

    async def publish(self, job_id, path, metadata, account, credentials, progress):
        self.validate_connection(account, credentials); self.validate_media(path); self.validate_metadata(metadata)
        await progress('UPLOADING', None)
        return await asyncio.to_thread(self._upload, path, metadata, credentials)

    @staticmethod
    def _upload(path: Path, metadata: dict, credentials: dict) -> PublishResult:
        headers = {'Authorization': f"Bearer {credentials['access_token']}", 'Content-Type': 'application/json',
                   'X-Upload-Content-Type': 'video/mp4', 'X-Upload-Content-Length': str(path.stat().st_size)}
        body = {'snippet': {'title': metadata['title'], 'description': metadata.get('description', ''),
                            'tags': [tag.lstrip('#') for tag in metadata.get('hashtags', [])], 'categoryId': '22'},
                'status': {'privacyStatus': metadata.get('privacy_status', 'private')}}
        with httpx.Client(timeout=60, trust_env=False) as client:
            init = client.post('https://www.googleapis.com/upload/youtube/v3/videos',
                               params={'uploadType': 'resumable', 'part': 'snippet,status'}, headers=headers, json=body)
            _raise_http(init)
            location = init.headers.get('location')
            if not location:
                raise PublishingError('PLATFORM_ERROR', 'YouTube no devolvió una URL de upload.')
            with path.open('rb') as video:
                result = client.put(location, headers={'Content-Type': 'video/mp4'}, content=video)
            _raise_http(result)
        identifier = result.json().get('id', '')
        if not identifier:
            raise PublishingError('PROCESSING_ERROR', 'YouTube no confirmó el identificador del video.')
        return PublishResult(identifier, f'https://youtu.be/{identifier}')


class TikTokPublisher(SocialPublisher):
    platform = 'tiktok'
    capabilities = SocialPublisher.capabilities | {'status_check': True}

    async def publish(self, job_id, path, metadata, account, credentials, progress):
        self.validate_connection(account, credentials); self.validate_media(path); self.validate_metadata(metadata)
        await progress('UPLOADING', None)
        return await asyncio.to_thread(self._upload, path, metadata, credentials)

    @staticmethod
    def _upload(path: Path, metadata: dict, credentials: dict) -> PublishResult:
        size = path.stat().st_size
        auth = {'Authorization': f"Bearer {credentials['access_token']}", 'Content-Type': 'application/json; charset=UTF-8'}
        caption = metadata.get('caption', '') + ' ' + ' '.join(metadata.get('hashtags', []))
        payload = {'post_info': {'title': caption.strip()[:2200], 'privacy_level': 'SELF_ONLY',
                                 'disable_duet': False, 'disable_comment': False, 'disable_stitch': False},
                   'source_info': {'source': 'FILE_UPLOAD', 'video_size': size,
                                   'chunk_size': size, 'total_chunk_count': 1}}
        with httpx.Client(timeout=90, trust_env=False) as client:
            init = client.post('https://open.tiktokapis.com/v2/post/publish/video/init/', headers=auth, json=payload)
            _raise_http(init)
            content = init.json(); error = content.get('error', {})
            if error.get('code') not in (None, '', 'ok'):
                raise PublishingError('PLATFORM_ERROR', error.get('message', 'TikTok rechazó la publicación.'))
            data = content.get('data', {}); upload_url, publish_id = data.get('upload_url'), data.get('publish_id')
            if not upload_url or not publish_id:
                raise PublishingError('PLATFORM_ERROR', 'TikTok no devolvió datos de upload.')
            with path.open('rb') as video:
                upload = client.put(upload_url, headers={'Content-Type': 'video/mp4', 'Content-Length': str(size),
                                    'Content-Range': f'bytes 0-{size - 1}/{size}'}, content=video)
            _raise_http(upload)
        return PublishResult(publish_id, '', 'PROCESSING')

    async def get_status(self, publish_id: str, credentials: dict):
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.post('https://open.tiktokapis.com/v2/post/publish/status/fetch/',
                headers={'Authorization': f"Bearer {credentials['access_token']}",
                         'Content-Type': 'application/json; charset=UTF-8'},
                json={'publish_id': publish_id})
        _raise_http(response)
        payload = response.json()
        if payload.get('error', {}).get('code') not in (None, '', 'ok'):
            raise PublishingError('PROCESSING_ERROR', payload['error'].get('message', 'TikTok no pudo consultar el estado.'))
        data = payload.get('data', {})
        status = data.get('status', 'PROCESSING')
        if status == 'PUBLISH_COMPLETE':
            identifiers = data.get('publicaly_available_post_id') or []
            return {'status': 'PUBLISHED', 'platform_media_id': str(identifiers[0]) if identifiers else publish_id,
                    'publication_url': ''}
        if status == 'FAILED':
            return {'status': 'FAILED', 'error': data.get('fail_reason', 'TikTok no pudo procesar el video.')}
        return {'status': 'PROCESSING'}


class InstagramPublisher(SocialPublisher):
    platform = 'instagram'; support = 'PARTIALLY_SUPPORTED'
    capabilities = {'publish_now': False, 'schedule': False, 'delete': False,
                    'status_check': False, 'analytics': False, 'cancel_upload': False}
    async def publish(self, *args, **kwargs):
        raise PublishingError('PERMISSION_ERROR', 'Instagram requiere una cuenta profesional elegible y configuración oficial de Meta.')


class FacebookPublisher(SocialPublisher):
    platform = 'facebook'; support = 'PARTIALLY_SUPPORTED'
    capabilities = InstagramPublisher.capabilities.copy()
    async def publish(self, *args, **kwargs):
        raise PublishingError('PERMISSION_ERROR', 'Facebook Reels requiere una Página y permisos oficiales de Meta configurados.')


def _raise_http(response: httpx.Response):
    if response.status_code == 401:
        raise PublishingError('AUTH_ERROR', 'La autorización expiró o fue revocada.')
    if response.status_code == 403:
        raise PublishingError('PERMISSION_ERROR', 'La cuenta no concedió los permisos requeridos.')
    if response.status_code == 429:
        raise PublishingError('RATE_LIMIT', 'La plataforma alcanzó su límite de solicitudes.', True)
    if response.status_code >= 500:
        raise PublishingError('PLATFORM_ERROR', 'La plataforma no está disponible temporalmente.', True)
    if response.is_error:
        raise PublishingError('PLATFORM_ERROR', f'La plataforma rechazó la solicitud ({response.status_code}).')
