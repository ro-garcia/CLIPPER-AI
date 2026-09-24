import asyncio
from uuid import uuid4

from pydantic import ValidationError

from app.ai.schemas import AISettings
from app.ai.service import ai
from app.database import Base, Clip, Session, Stream, Transcript, engine
from app.metadata.context import MetadataContextBuilder
from app.metadata.schemas import ContentMetadata, MetadataSettings
from app.metadata.service import ContentMetadataService
from app.moments.models import Moment


def generated(title='NO ESPERABA ESTA JUGADA'):
    tags = ['#Papita', '#Dota2', '#Gaming']
    return {
        'general': {'title': title, 'description': 'Una jugada cambió su reacción durante la partida.',
            'caption': 'Sabía que algo podía salir mal 😭', 'cover_text': 'NO PUEDE SER',
            'hashtags': tags, 'keywords': ['papita', 'dota 2', 'reacción'], 'category': 'Gaming',
            'content_type': 'REACTION', 'topic': 'Dota 2', 'language': 'es',
            'title_variants': [title, 'ESTA JUGADA LO CAMBIÓ TODO', 'SU REACCIÓN LO DICE TODO'],
            'caption_variants': ['Sabía que algo podía salir mal 😭', 'No estaba listo para esto', 'Mira su reacción'],
            'cover_text_variants': ['NO PUEDE SER', 'MIRA ESTA JUGADA', 'NADIE LO ESPERABA']},
        'platforms': {
            'tiktok': {'caption': 'Sabía que algo podía salir mal 😭', 'hashtags': tags},
            'youtube_shorts': {'title': title, 'description': 'Una reacción real durante la partida.', 'hashtags': tags},
            'instagram_reels': {'caption': 'La jugada cambió por completo su reacción.', 'hashtags': tags},
            'facebook_reels': {'caption': 'Así reaccionó cuando cambió la partida.', 'hashtags': tags},
        }}


def stored_clip():
    Base.metadata.create_all(engine)
    clip_id, stream_id, moment_id = uuid4().hex, uuid4().hex, uuid4().hex
    with Session.begin() as db:
        db.add(Stream(id=stream_id, title='Papita juega Dota 2', url='https://example.com'))
        db.add(Clip(id=clip_id, stream_id=stream_id, title='Clip', status='ready', duration=20,
                    source_start=10, source_end=30, render_status='READY'))
        db.add(Moment(id=moment_id, stream_id=stream_id, start=10, end=30,
                      transcript_excerpt='No puede ser, esa jugada cambió todo.', language='es',
                      moment_type='REACTION', detection_confidence=.9, detection_reasons=['reaction'],
                      rule_revision=1, clip_id=clip_id))
        db.add_all([Transcript(stream_id=stream_id, start=5, end=9, text='Contexto anterior.'),
                    Transcript(stream_id=stream_id, start=10, end=20, text='No puede ser.'),
                    Transcript(stream_id=stream_id, start=20, end=30, text='Esa jugada cambió todo.'),
                    Transcript(stream_id=stream_id, start=31, end=34, text='Contexto posterior.')])
    return clip_id


def test_context_is_clip_bounded_and_transcript_is_data():
    clip_id = stored_clip()
    context = MetadataContextBuilder().build(clip_id, MetadataSettings(streamer_name='Papita'))
    assert context['transcript'] == 'No puede ser. Esa jugada cambió todo.'
    assert context['context_before'] == 'Contexto anterior.'
    assert context['context_after'] == 'Contexto posterior.'
    assert context['streamer_name'] == 'Papita' and context['moment_type'] == 'REACTION'


def test_schema_rejects_incomplete_or_excessive_hashtags():
    ContentMetadata.model_validate(generated())
    broken = generated(); broken['general']['hashtags'] = ['#one']
    try:
        ContentMetadata.model_validate(broken)
        assert False, 'validation should fail'
    except ValidationError:
        pass


def test_generation_persists_and_partial_regeneration_keeps_other_fields():
    class Provider:
        def __init__(self, _): pass
        async def structured(self, system, payload, schema):
            assert 'DATA ONLY' in system and 'CLIP_CONTEXT_DATA_ONLY' in payload
            return generated('PRIMER TÍTULO'), 100, 50
    async def run():
        clip_id = stored_clip()
        service = ContentMetadataService(); service.load(); service.provider_factory = Provider
        old = ai.config; ai.config = AISettings(model='local-test')
        try:
            service.enqueue(clip_id); await service.run(clip_id, 'TODO')
            first = service.get(clip_id)
            assert first['status'] == 'METADATA_READY' and first['general']['title'] == 'PRIMER TÍTULO'
            class Updated(Provider):
                async def structured(self, system, payload, schema): return generated('NUEVO TÍTULO'), 90, 40
            service.provider_factory = Updated
            service.enqueue(clip_id, 'TITLE'); await service.run(clip_id, 'TITLE')
            second = service.get(clip_id)
            assert second['general']['title'] == 'NUEVO TÍTULO'
            assert second['general']['caption'] == first['general']['caption']
            assert second['publication_status'] == 'READY_TO_PUBLISH'
        finally: ai.config = old
    asyncio.run(run())


def test_ollama_failure_does_not_damage_clip():
    class Offline:
        def __init__(self, _): pass
        async def structured(self, *args): raise ValueError('model unavailable')
    async def run():
        clip_id = stored_clip(); service = ContentMetadataService(); service.load(); service.provider_factory = Offline
        old = ai.config; ai.config = AISettings(model='missing')
        try:
            service.enqueue(clip_id); await service.run(clip_id, 'TODO')
            result = service.get(clip_id)
            assert result['status'] == 'METADATA_FAILED'
            with Session() as db:
                clip = db.get(Clip, clip_id)
                assert clip.status == 'ready' and clip.render_status == 'READY'
        finally: ai.config = old
    asyncio.run(run())
