import subprocess
from uuid import uuid4

import pytest

from app.config import ffmpeg, settings
from app.database import Base, Clip, Session, Stream, Transcript, engine
from app.moments.models import Moment
from app.rendering.reframing import strategy_for
from app.rendering.schemas import RenderSettings
from app.rendering.service import FinalRenderService
from app.rendering.subtitles import create_subtitle_files, render_ass, render_srt, subtitle_segments
from app.services.media import run_ffmpeg


def stored_clip(with_transcript=True):
    Base.metadata.create_all(engine)
    identifier = uuid4().hex
    stream_id = uuid4().hex
    with Session.begin() as db:
        db.add(Stream(id=stream_id, title='Render fixture', url='https://example.com'))
        db.add(Clip(id=identifier, stream_id=stream_id, title='Clip fixture', status='ready', duration=3,
                    source_start=10, source_end=13))
        db.add(Moment(id=uuid4().hex, stream_id=stream_id, start=10, end=13,
                      transcript_excerpt='Texto de prueba completo.', language='es', moment_type='OPINION',
                      detection_confidence=.9, detection_reasons=[], rule_revision=1, clip_id=identifier))
        if with_transcript:
            db.add_all([
                Transcript(stream_id=stream_id, start=10, end=11.5,
                           text='Esta es una frase con palabras suficientes para dividirla con comodidad.'),
                Transcript(stream_id=stream_id, start=11.5, end=13,
                           text='La segunda idea mantiene la sincronización con el audio.'),
            ])
    return identifier


def compact_config(**changes):
    return RenderSettings(output_width=360, output_height=640, font_size=32, safe_area_top=30,
                          safe_area_bottom=70, safe_area_left=12, safe_area_right=12,
                          max_chars_per_line=18, **changes)


def test_subtitles_split_on_words_and_generate_srt_ass():
    clip_id = stored_clip()
    config = compact_config()
    segments = subtitle_segments(clip_id, config)
    assert segments[0].start == 0
    assert segments[-1].end == 3
    assert all(len(line) <= config.max_chars_per_line for segment in segments for line in segment.text.splitlines())
    assert '-->' in render_srt(segments)
    ass = render_ass(segments, config)
    assert '[V4+ Styles]' in ass and 'Dialogue:' in ass
    srt_path, ass_path, count = create_subtitle_files(clip_id, config)
    assert count == len(segments) and srt_path.exists() and ass_path.exists()


def test_subtitle_requires_timed_transcript():
    with pytest.raises(ValueError, match='transcripción'):
        subtitle_segments(stored_clip(with_transcript=False), compact_config())


def test_reframing_preserves_aspect_ratio_and_has_fallbacks(tmp_path):
    captions = tmp_path / 'captions.ass'
    captions.write_text('x', encoding='utf-8')
    crop = strategy_for(compact_config()).video_filter(compact_config(), captions)
    blur = strategy_for(compact_config(background_mode='BLUR', reframing_mode='SMART_CROP')).video_filter(
        compact_config(background_mode='BLUR', reframing_mode='SMART_CROP'), captions)
    tracking = strategy_for(compact_config(reframing_mode='SUBJECT_TRACKING'))
    assert 'force_original_aspect_ratio=increase' in crop and 'crop=360:640' in crop and 'ass=filename=' in crop
    assert 'boxblur' in blur and tracking.name == 'SUBJECT_TRACKING'


def test_crop_without_subtitles_has_exactly_one_output_label():
    graph = strategy_for(compact_config(subtitles_enabled=False)).video_filter(
        compact_config(subtitles_enabled=False), None)
    assert graph.endswith('[v]')
    assert '[base]' not in graph
    assert '[base][v]' not in graph
    # Validate the exact graph with FFmpeg, not only its string representation.
    run_ffmpeg(['-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=10', '-t', '0.2',
                '-filter_complex', graph, '-map', '[v]', '-f', 'null', '-'])


def test_final_render_generates_vertical_mp4_with_audio_and_subtitles():
    clip_id = stored_clip()
    directory = settings.storage_dir / 'clips' / clip_id
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / 'original.mp4'
    run_ffmpeg(['-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=25', '-f', 'lavfi', '-i',
                'sine=frequency=440:sample_rate=44100', '-t', '3', '-shortest', '-c:v', 'libx264', '-c:a', 'aac',
                str(source)])
    service = FinalRenderService()
    service.render_blocking(clip_id, compact_config())
    final = directory / 'vertical.mp4'
    assert final.exists() and final.stat().st_size > 10_000
    probe = subprocess.run([ffmpeg(), '-hide_banner', '-i', str(final)], capture_output=True, text=True)
    report = probe.stderr
    assert '360x640' in report and 'Audio: aac' in report
