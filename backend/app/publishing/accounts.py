from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from sqlalchemy import select

from ..config import settings
from ..database import Session, serialize
from ..detection.models import now
from .models import OAuthSession, SocialAccount
from .publishers import (FacebookPublisher, InstagramPublisher, MockSocialPublisher,
                         TikTokPublisher, YouTubePublisher, PublishingError)
from .secrets import SecureTokenStore

PLATFORMS = ('youtube', 'tiktok', 'instagram', 'facebook')


def account_dict(row: SocialAccount) -> dict:
    data = serialize(row)
    data.pop('token_reference', None)
    data['has_secure_token'] = bool(row.token_reference)
    return data


class SocialAccountService:
    def __init__(self):
        self.tokens = SecureTokenStore()

    def load(self, mock_enabled: bool):
        if mock_enabled:
            for platform in PLATFORMS:
                self.ensure_mock(platform)

    def ensure_mock(self, platform: str) -> dict:
        if platform not in PLATFORMS:
            raise ValueError('Plataforma no soportada.')
        identifier = f'mock-{platform}'
        with Session.begin() as db:
            row = db.get(SocialAccount, identifier)
            if not row:
                row = SocialAccount(id=identifier, platform=platform,
                                    display_name=f'{platform.title()} · Safe Mode',
                                    external_account_id=identifier, status='CONNECTED',
                                    scopes=['mock.publish'], permissions=['publish', 'schedule'],
                                    provider_mode='mock', last_validation=now())
                db.add(row)
            elif row.status != 'CONNECTED':
                row.status, row.updated_at = 'CONNECTED', now()
            db.flush()
            return account_dict(row)

    def list(self) -> list[dict]:
        with Session() as db:
            return [account_dict(row) for row in db.scalars(
                select(SocialAccount).order_by(SocialAccount.platform, SocialAccount.created_at))]

    def get(self, identifier: str) -> dict:
        with Session() as db:
            row = db.get(SocialAccount, identifier)
            if not row:
                raise ValueError('Cuenta social no encontrada.')
            return account_dict(row)

    def publisher(self, platform: str, mock_mode: bool):
        if platform not in PLATFORMS:
            raise ValueError('Plataforma no soportada.')
        if mock_mode:
            return MockSocialPublisher(platform)
        return {'youtube': YouTubePublisher(), 'tiktok': TikTokPublisher(),
                'instagram': InstagramPublisher(), 'facebook': FacebookPublisher()}[platform]

    def capabilities(self, mock_mode: bool) -> list[dict]:
        result = []
        for platform in PLATFORMS:
            publisher = self.publisher(platform, mock_mode)
            configured = mock_mode or self._client_id(platform) != ''
            result.append({'platform': platform, 'support': publisher.support,
                           'configured': configured, 'capabilities': publisher.capabilities,
                           'configuration_required': self._requirement(platform, mock_mode)})
        return result

    def _client_id(self, platform: str) -> str:
        return settings.youtube_client_id if platform == 'youtube' else settings.tiktok_client_key if platform == 'tiktok' else ''

    @staticmethod
    def _requirement(platform: str, mock: bool) -> str:
        if mock:
            return ''
        return {
            'youtube': 'Configura YOUTUBE_CLIENT_ID y habilita YouTube Data API v3.',
            'tiktok': 'Configura TIKTOK_CLIENT_KEY y obtén aprobación para video.publish.',
            'instagram': 'Pendiente: app de Meta aprobada y cuenta profesional elegible.',
            'facebook': 'Pendiente: app de Meta aprobada, Página y permisos para Reels.',
        }[platform]

    def oauth_start(self, platform: str) -> dict:
        if platform not in ('youtube', 'tiktok'):
            raise ValueError(self._requirement(platform, False))
        client_id = self._client_id(platform)
        if not client_id:
            raise ValueError(self._requirement(platform, False))
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        redirect = f"{settings.oauth_callback_base.rstrip('/')}/publishing/oauth/{platform}/callback"
        with Session.begin() as db:
            db.add(OAuthSession(state=state, platform=platform, code_verifier=verifier, redirect_uri=redirect))
        if platform == 'youtube':
            query = {'client_id': client_id, 'redirect_uri': redirect, 'response_type': 'code',
                     'scope': 'https://www.googleapis.com/auth/youtube.upload openid profile',
                     'access_type': 'offline', 'prompt': 'consent', 'state': state,
                     'code_challenge': challenge, 'code_challenge_method': 'S256'}
            url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(query)
        else:
            query = {'client_key': client_id, 'redirect_uri': redirect, 'response_type': 'code',
                     'scope': 'user.info.basic,video.publish', 'state': state,
                     'code_challenge': challenge, 'code_challenge_method': 'S256'}
            url = 'https://www.tiktok.com/v2/auth/authorize/?' + urlencode(query)
        return {'platform': platform, 'authorization_url': url, 'state': state}

    async def oauth_callback(self, platform: str, state: str, code: str) -> dict:
        with Session.begin() as db:
            session = db.get(OAuthSession, state)
            if not session or session.platform != platform:
                raise ValueError('Estado OAuth inválido o expirado.')
            if datetime.fromisoformat(session.created_at) < datetime.now(timezone.utc) - timedelta(minutes=10):
                db.delete(session)
                raise ValueError('La autorización OAuth expiró; inicia la conexión nuevamente.')
            verifier, redirect = session.code_verifier, session.redirect_uri
            db.delete(session)
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            if platform == 'youtube':
                response = await client.post('https://oauth2.googleapis.com/token', data={
                    'client_id': settings.youtube_client_id, 'client_secret': settings.youtube_client_secret,
                    'code': code, 'code_verifier': verifier, 'grant_type': 'authorization_code',
                    'redirect_uri': redirect})
                self._oauth_response(response)
                token = response.json()
                profile_response = await client.get('https://openidconnect.googleapis.com/v1/userinfo',
                                                    headers={'Authorization': f"Bearer {token['access_token']}"})
                self._oauth_response(profile_response); profile = profile_response.json()
                external_id, display_name = profile.get('sub', ''), profile.get('name', 'YouTube')
            elif platform == 'tiktok':
                response = await client.post('https://open.tiktokapis.com/v2/oauth/token/', data={
                    'client_key': settings.tiktok_client_key, 'client_secret': settings.tiktok_client_secret,
                    'code': code, 'code_verifier': verifier, 'grant_type': 'authorization_code',
                    'redirect_uri': redirect})
                self._oauth_response(response); token = response.json()
                profile_response = await client.get('https://open.tiktokapis.com/v2/user/info/',
                    params={'fields': 'open_id,display_name'},
                    headers={'Authorization': f"Bearer {token['access_token']}"})
                self._oauth_response(profile_response); profile = profile_response.json().get('data', {}).get('user', {})
                external_id, display_name = profile.get('open_id', token.get('open_id', '')), profile.get('display_name', 'TikTok')
            else:
                raise ValueError('Proveedor OAuth no implementado.')
        expires = datetime.now(timezone.utc) + timedelta(seconds=int(token.get('expires_in', 3600)))
        reference = self.tokens.save(token)
        identifier = uuid4().hex
        with Session.begin() as db:
            row = db.scalar(select(SocialAccount).where(SocialAccount.platform == platform,
                                                         SocialAccount.external_account_id == external_id))
            if row:
                self.tokens.delete(row.token_reference)
                row.token_reference = reference
            else:
                row = SocialAccount(id=identifier, platform=platform, display_name=display_name,
                                    external_account_id=external_id, token_reference=reference)
                db.add(row)
            row.status, row.provider_mode = 'CONNECTED', 'real'
            row.scopes = str(token.get('scope', '')).replace(',', ' ').split()
            row.permissions, row.expires_at = row.scopes, expires.isoformat()
            row.last_validation, row.updated_at = now(), now()
            db.flush()
            return account_dict(row)

    async def credentials(self, identifier: str) -> dict:
        with Session() as db:
            row = db.get(SocialAccount, identifier)
            if not row:
                raise PublishingError('AUTH_ERROR', 'Cuenta no encontrada.')
            if row.provider_mode == 'mock':
                return {}
            reference, platform, expires_at = row.token_reference, row.platform, row.expires_at
        try:
            token = self.tokens.load(reference)
        except Exception as exc:
            raise PublishingError('AUTH_ERROR', 'No se pudo recuperar la credencial protegida.') from exc
        if expires_at and datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc) + timedelta(seconds=60):
            token = await self._refresh(platform, token)
            self.tokens.save(token, reference)
            expires = datetime.now(timezone.utc) + timedelta(seconds=int(token.get('expires_in', 3600)))
            with Session.begin() as db:
                row = db.get(SocialAccount, identifier); row.expires_at, row.updated_at = expires.isoformat(), now()
        return token

    async def _refresh(self, platform: str, token: dict) -> dict:
        refresh = token.get('refresh_token')
        if not refresh:
            raise PublishingError('AUTH_ERROR', 'La sesión expiró y requiere autorización nuevamente.')
        if platform == 'youtube':
            url = 'https://oauth2.googleapis.com/token'; data = {'client_id': settings.youtube_client_id,
                'client_secret': settings.youtube_client_secret, 'refresh_token': refresh, 'grant_type': 'refresh_token'}
        elif platform == 'tiktok':
            url = 'https://open.tiktokapis.com/v2/oauth/token/'; data = {'client_key': settings.tiktok_client_key,
                'client_secret': settings.tiktok_client_secret, 'refresh_token': refresh, 'grant_type': 'refresh_token'}
        else:
            raise PublishingError('AUTH_ERROR', 'Esta plataforma requiere reconexión.')
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.post(url, data=data); self._oauth_response(response)
        updated = response.json(); updated.setdefault('refresh_token', refresh)
        return updated

    def disconnect(self, identifier: str) -> dict:
        with Session.begin() as db:
            row = db.get(SocialAccount, identifier)
            if not row:
                raise ValueError('Cuenta no encontrada.')
            if row.provider_mode == 'mock':
                row.status = 'DISCONNECTED'
            else:
                self.tokens.delete(row.token_reference)
                row.token_reference, row.status, row.expires_at = '', 'DISCONNECTED', ''
            row.updated_at = now(); db.flush(); return account_dict(row)

    @staticmethod
    def _oauth_response(response: httpx.Response):
        if response.is_error:
            raise ValueError(f'El proveedor OAuth rechazó la solicitud ({response.status_code}).')


accounts = SocialAccountService()
