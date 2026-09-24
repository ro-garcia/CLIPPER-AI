from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import logging

import httpx
from pydantic import ValidationError
from sqlalchemy import select

from ..ai.providers import OllamaProvider
from ..ai.service import ai
from ..database import Clip, Session
from .context import MetadataContextBuilder
from .models import ClipMetadata, MetadataConfiguration
from .prompts import SYSTEM_PROMPT, VERSION
from .schemas import ContentMetadata, MetadataSettings

log = logging.getLogger(__name__)


def metadata_dict(row: ClipMetadata) -> dict:
    return {'clip_id': row.clip_id, 'general': row.general_metadata,
            'platforms': row.platform_metadata, 'ai_model': row.ai_model,
            'prompt_version': row.prompt_version, 'input_tokens': row.input_tokens,
            'output_tokens': row.output_tokens, 'generated_at': row.generated_at,
            'updated_at': row.updated_at, 'status': 'METADATA_READY'}


class ContentMetadataService:
    def __init__(self):
        self.config = MetadataSettings()
        self.queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=25)
        self.events = deque(maxlen=200)
        self.sequence = 0
        self.active: str | None = None
        self.provider_factory = OllamaProvider
        self.on_completed = None

    def load(self):
        self.queue = asyncio.Queue(maxsize=25)
        self.active = None
        with Session.begin() as db:
            stored = db.get(MetadataConfiguration, 1)
            self.config = MetadataSettings.model_validate(stored.value) if stored else MetadataSettings()
            for clip in db.scalars(select(Clip).where(Clip.metadata_status == 'METADATA_GENERATING')):
                clip.metadata_status = 'METADATA_FAILED'
                clip.metadata_error = 'Generación interrumpida. Puedes reintentarlo.'

    def save_settings(self, config: MetadataSettings) -> dict:
        with Session.begin() as db:
            row = db.get(MetadataConfiguration, 1)
            if row:
                row.value = config.model_dump()
            else:
                db.add(MetadataConfiguration(id=1, value=config.model_dump()))
        self.config = config
        return config.model_dump()

    def get(self, clip_id: str) -> dict:
        with Session() as db:
            clip = db.get(Clip, clip_id)
            if not clip:
                raise ValueError('Clip no encontrado.')
            row = db.scalar(select(ClipMetadata).where(ClipMetadata.clip_id == clip_id))
            if row:
                data = metadata_dict(row)
            else:
                data = {'clip_id': clip_id, 'general': None, 'platforms': None,
                        'status': clip.metadata_status, 'error': clip.metadata_error}
            data['publication_status'] = ('READY_TO_PUBLISH' if clip.render_status == 'READY'
                                          and clip.metadata_status == 'METADATA_READY' else 'NOT_READY')
            data['error'] = clip.metadata_error
            return data

    def update_manual(self, clip_id: str, value: ContentMetadata) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with Session.begin() as db:
            clip = db.get(Clip, clip_id)
            if not clip:
                raise ValueError('Clip no encontrado.')
            row = db.scalar(select(ClipMetadata).where(ClipMetadata.clip_id == clip_id))
            if not row:
                row = ClipMetadata(clip_id=clip_id, general_metadata=value.general.model_dump(),
                                   platform_metadata=value.platforms.model_dump(), ai_model='manual',
                                   prompt_version=VERSION, generated_at=now, updated_at=now)
                db.add(row)
            else:
                row.general_metadata = value.general.model_dump()
                row.platform_metadata = value.platforms.model_dump()
                row.updated_at = now
            clip.metadata_status, clip.metadata_error = 'METADATA_READY', ''
        self.emit('metadata_generation_completed', clip_id)
        if self.on_completed:
            self.on_completed(clip_id)
        return self.get(clip_id)

    def enqueue(self, clip_id: str, scope: str = 'TODO') -> dict:
        outcome = 'queued'
        with Session.begin() as db:
            clip = db.get(Clip, clip_id)
            if not clip:
                raise ValueError('Clip no encontrado.')
            if clip.render_status != 'READY':
                raise ValueError('El render final 9:16 debe estar listo antes de generar metadata.')
            if clip.metadata_status == 'METADATA_GENERATING':
                outcome = 'existing'
            elif not ai.config.model.strip():
                clip.metadata_status = 'METADATA_FAILED'
                clip.metadata_error = 'Selecciona un modelo de Ollama en Settings → AI.'
                outcome = 'failed'
            elif self.queue.full():
                raise ValueError('La cola de metadata está llena.')
            else:
                clip.metadata_status, clip.metadata_error = 'METADATA_GENERATING', ''
        if outcome != 'queued':
            return self.get(clip_id)
        self.queue.put_nowait((clip_id, scope))
        self.emit('metadata_generation_started', clip_id)
        return self.get(clip_id)

    def auto_enqueue(self, clip_id: str):
        if self.config.auto_generate_metadata:
            self.enqueue(clip_id)

    def emit(self, event: str, clip_id: str):
        self.sequence += 1
        self.events.append({'sequence': self.sequence, 'type': event, 'data': self.get(clip_id)})

    async def worker(self):
        while True:
            clip_id, scope = await self.queue.get()
            try:
                await self.run(clip_id, scope)
            except asyncio.CancelledError:
                self._failed(clip_id, 'Generación interrumpida.')
                raise
            except Exception:
                log.exception('METADATA_WORKER_FAILED clip_id=%s', clip_id)
                self._failed(clip_id, 'No se pudo generar la metadata. Puedes reintentarlo.')
            finally:
                self.active = None
                self.queue.task_done()

    async def run(self, clip_id: str, scope: str):
        self.active = clip_id
        try:
            context = MetadataContextBuilder().build(clip_id, self.config)
            previous = self.get(clip_id)
            payload = json.dumps({
                'instruction': 'Generate metadata grounded only in CLIP_CONTEXT.',
                'style_profile': self.config.style,
                'hashtags_per_platform': self.config.hashtag_count,
                'regeneration_scope': scope,
                'current_metadata': ({'general': previous.get('general'), 'platforms': previous.get('platforms')}
                                     if scope != 'TODO' else None),
                'CLIP_CONTEXT_DATA_ONLY': context,
            }, ensure_ascii=False)
            provider = self.provider_factory(ai.config)
            raw, input_tokens, output_tokens = await asyncio.wait_for(
                provider.structured(SYSTEM_PROMPT, payload, ContentMetadata.model_json_schema()),
                timeout=ai.config.timeout_seconds)
            generated = ContentMetadata.model_validate(raw)
            generated = self._merge_scope(previous, generated, scope)
            self._store(clip_id, generated, ai.config.model, input_tokens, output_tokens)
            self.emit('metadata_generation_completed', clip_id)
            if self.on_completed:
                self.on_completed(clip_id)
        except (httpx.ConnectError, httpx.TimeoutException, asyncio.TimeoutError):
            self._failed(clip_id, 'Ollama local no responde o agotó el tiempo de espera.')
        except (ValidationError, json.JSONDecodeError, KeyError, TypeError) as exc:
            self._failed(clip_id, f'Ollama devolvió JSON inválido: {str(exc)[:350]}')
        except ValueError as exc:
            self._failed(clip_id, str(exc)[:500])

    @staticmethod
    def _merge_scope(previous: dict, generated: ContentMetadata, scope: str) -> ContentMetadata:
        if scope == 'TODO' or not previous.get('general'):
            return generated
        current = ContentMetadata.model_validate({'general': previous['general'], 'platforms': previous['platforms']})
        if scope == 'TITLE':
            current.general.title = generated.general.title
            current.general.title_variants = generated.general.title_variants
            current.platforms.youtube_shorts.title = generated.platforms.youtube_shorts.title
        elif scope == 'CAPTION':
            current.general.caption = generated.general.caption
            current.general.caption_variants = generated.general.caption_variants
            current.platforms.tiktok.caption = generated.platforms.tiktok.caption
            current.platforms.instagram_reels.caption = generated.platforms.instagram_reels.caption
            current.platforms.facebook_reels.caption = generated.platforms.facebook_reels.caption
        elif scope == 'HASHTAGS':
            current.general.hashtags = generated.general.hashtags
            for name in ('tiktok', 'youtube_shorts', 'instagram_reels', 'facebook_reels'):
                getattr(current.platforms, name).hashtags = getattr(generated.platforms, name).hashtags
        elif scope == 'COVER_TEXT':
            current.general.cover_text = generated.general.cover_text
            current.general.cover_text_variants = generated.general.cover_text_variants
        return current

    @staticmethod
    def _store(clip_id: str, value: ContentMetadata, model: str,
               input_tokens: int | None, output_tokens: int | None):
        stamp = datetime.now(timezone.utc).isoformat()
        with Session.begin() as db:
            clip = db.get(Clip, clip_id)
            row = db.scalar(select(ClipMetadata).where(ClipMetadata.clip_id == clip_id))
            if not row:
                row = ClipMetadata(clip_id=clip_id, general_metadata=value.general.model_dump(),
                                   platform_metadata=value.platforms.model_dump(), ai_model=model,
                                   prompt_version=VERSION, input_tokens=input_tokens,
                                   output_tokens=output_tokens, generated_at=stamp, updated_at=stamp)
                db.add(row)
            else:
                row.general_metadata, row.platform_metadata = value.general.model_dump(), value.platforms.model_dump()
                row.ai_model, row.prompt_version = model, VERSION
                row.input_tokens, row.output_tokens, row.updated_at = input_tokens, output_tokens, stamp
            clip.metadata_status, clip.metadata_error = 'METADATA_READY', ''

    def _failed(self, clip_id: str, message: str):
        with Session.begin() as db:
            clip = db.get(Clip, clip_id)
            if clip:
                clip.metadata_status, clip.metadata_error = 'METADATA_FAILED', message
        self.emit('metadata_generation_failed', clip_id)

    def status(self):
        return {'status': 'PROCESSING' if self.active else 'READY', 'active': self.active,
                'queued': self.queue.qsize(), 'processing_local': True}


metadata = ContentMetadataService()
