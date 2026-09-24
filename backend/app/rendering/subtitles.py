"""Create readable SRT and ASS captions from persisted Whisper transcript timing."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from sqlalchemy import select

from ..config import settings
from ..database import Clip, Session, Transcript
from ..moments.models import Moment


@dataclass(frozen=True)
class SubtitleSegment:
    start: float
    end: float
    text: str


def _source_range(clip_id: str) -> tuple[dict, float, float, list[dict]]:
    with Session() as db:
        clip = db.get(Clip, clip_id)
        if not clip:
            raise ValueError('Clip no encontrado.')
        moment = db.scalar(select(Moment).where(Moment.clip_id == clip_id))
        start = clip.source_start if clip.source_start is not None else (moment.start if moment else None)
        end = clip.source_end if clip.source_end is not None else (moment.end if moment else None)
        if start is None or end is None or end <= start:
            raise ValueError('Este clip no conserva un rango de transcripción para generar subtítulos.')
        rows = db.scalars(select(Transcript).where(
            Transcript.stream_id == clip.stream_id, Transcript.end > start, Transcript.start < end,
        ).order_by(Transcript.start)).all()
        return ({'id': clip.id, 'stream_id': clip.stream_id, 'duration': clip.duration}, start, end,
                [{'start': row.start, 'end': row.end, 'text': row.text} for row in rows])


def _chunks(text: str, limit: int) -> list[str]:
    words = re.findall(r'\S+', text.replace('\n', ' '))
    result: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        next_length = length + (1 if current else 0) + len(word)
        if current and next_length > limit:
            result.append(' '.join(current))
            current, length = [word], len(word)
        else:
            current.append(word)
            length = next_length
    if current:
        result.append(' '.join(current))
    return result


def _line_break(text: str, max_chars_per_line: int) -> str:
    if len(text) <= max_chars_per_line:
        return text
    words = text.split()
    left: list[str] = []
    length = 0
    target = len(text) / 2
    for word in words:
        next_length = length + (1 if left else 0) + len(word)
        if left and abs(next_length - target) > abs(length - target):
            break
        left.append(word)
        length = next_length
    return ' '.join(left) + '\n' + ' '.join(words[len(left):])


def subtitle_segments(clip_id: str, config) -> list[SubtitleSegment]:
    """Rebase existing transcript rows to clip time and split only on whole words."""
    _, source_start, source_end, rows = _source_range(clip_id)
    limit = config.max_chars_per_line * config.max_lines
    result: list[SubtitleSegment] = []
    for row in rows:
        start = max(row['start'], source_start) - source_start
        end = min(row['end'], source_end) - source_start
        if end <= start or not row['text'].strip():
            continue
        chunks = _chunks(row['text'], limit)
        if not chunks:
            continue
        span = (end - start) / len(chunks)
        for index, chunk in enumerate(chunks):
            segment_start = start + index * span
            segment_end = start + (index + 1) * span
            # Never extend beyond Whisper's timing. A short source utterance stays short.
            if segment_end - segment_start > config.max_subtitle_duration:
                segment_end = min(segment_start + config.max_subtitle_duration, end)
            result.append(SubtitleSegment(round(segment_start, 3), round(segment_end, 3),
                                          _line_break(chunk, config.max_chars_per_line)))
    if not result:
        raise ValueError('No hay transcripción con tiempos dentro de este clip.')
    return result


def _srt_time(value: float) -> str:
    milliseconds = max(0, round(value * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}'


def _ass_time(value: float) -> str:
    centiseconds = max(0, round(value * 100))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    seconds, centiseconds = divmod(remainder, 100)
    return f'{hours}:{minutes:02}:{seconds:02}.{centiseconds:02}'


def _ass_color(value: str, opacity: str = '00') -> str:
    value = value.lstrip('#')
    return f'&H{opacity}{value[4:6]}{value[2:4]}{value[0:2]}'


def render_srt(segments: list[SubtitleSegment]) -> str:
    blocks = []
    for index, segment in enumerate(segments, 1):
        blocks.append(f'{index}\n{_srt_time(segment.start)} --> {_srt_time(segment.end)}\n{segment.text}\n')
    return '\n'.join(blocks)


def render_ass(segments: list[SubtitleSegment], config) -> str:
    alignment = {'TOP': 8, 'MIDDLE': 5, 'BOTTOM': 2}[config.subtitle_position]
    margin_v = config.safe_area_top if config.subtitle_position == 'TOP' else config.safe_area_bottom
    bold = -1 if config.subtitle_style == 'DYNAMIC' else 0
    back = _ass_color('#000000', '70') if config.background else '&H00000000'
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {config.output_width}
PlayResY: {config.output_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: LiveClip,{config.font},{config.font_size},{_ass_color(config.font_color)},&H000000FF,&H00101010,{back},{bold},0,0,0,100,100,0,0,1,{config.outline_size},1,{alignment},{config.safe_area_left},{config.safe_area_right},{margin_v},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
'''
    events = []
    for segment in segments:
        text = segment.text.replace('\\', r'\\').replace('{', r'\{').replace('}', r'\}').replace('\n', r'\N')
        events.append(f'Dialogue: 0,{_ass_time(segment.start)},{_ass_time(segment.end)},LiveClip,,0,0,0,,{text}')
    return header + '\n'.join(events) + '\n'


def create_subtitle_files(clip_id: str, config) -> tuple[Path, Path, int]:
    segments = subtitle_segments(clip_id, config)
    directory = settings.storage_dir / 'clips' / clip_id
    directory.mkdir(parents=True, exist_ok=True)
    srt = directory / 'subtitles.srt'
    ass = directory / 'subtitles.ass'
    srt.write_text(render_srt(segments), encoding='utf-8')
    ass.write_text(render_ass(segments, config), encoding='utf-8')
    return srt, ass, len(segments)
