from __future__ import annotations

from sqlalchemy import select

from ..ai.models import AIEvaluation
from ..database import Clip, Session, Stream, Transcript, serialize
from ..moments.models import Moment


class MetadataContextBuilder:
    def build(self, clip_id: str, config) -> dict:
        with Session() as db:
            clip = db.get(Clip, clip_id)
            if not clip:
                raise ValueError('Clip no encontrado.')
            start = float(clip.source_start or 0)
            end = float(clip.source_end if clip.source_end is not None else start + clip.duration)
            stream = db.get(Stream, clip.stream_id)
            moment = db.scalar(select(Moment).where(Moment.clip_id == clip_id))
            if not moment:
                moment = db.scalar(select(Moment).where(
                    Moment.stream_id == clip.stream_id, Moment.end >= start, Moment.start <= end
                ).order_by(Moment.detection_confidence.desc()))
            evaluation = None
            if moment:
                evaluation = db.scalar(select(AIEvaluation).where(
                    AIEvaluation.moment_id == moment.id, AIEvaluation.status == 'EVALUATED'
                ).order_by(AIEvaluation.created_at.desc()))
            rows = list(db.scalars(select(Transcript).where(
                Transcript.stream_id == clip.stream_id,
                Transcript.end >= max(0, start - config.context_before_seconds),
                Transcript.start <= end + config.context_after_seconds,
            ).order_by(Transcript.start)))
        clip_text = ' '.join(row.text.strip() for row in rows if row.end >= start and row.start <= end).strip()
        before = ' '.join(row.text.strip() for row in rows if row.end < start).strip()
        after = ' '.join(row.text.strip() for row in rows if row.start > end).strip()
        if not clip_text and moment:
            clip_text = moment.transcript_excerpt.strip()
        if not clip_text:
            raise ValueError('El clip no tiene una transcripción disponible.')
        context = {
            'streamer_name': config.streamer_name or None,
            'stream_title': stream.title if stream else clip.title,
            'clip_id': clip.id,
            'clip_duration': clip.duration,
            'language': moment.language if moment else 'es',
            'transcript': clip_text,
            'context_before': before,
            'context_after': after,
            'moment_type': moment.moment_type if moment else None,
            'detection_reasons': moment.detection_reasons if moment else [],
            'streamer_profile': {
                'main_topics': config.streamer_main_topics,
                'metadata_style': config.streamer_metadata_style,
            },
        }
        if evaluation:
            context['ai_evaluation'] = {
                key: getattr(evaluation, key) for key in (
                    'detected_topic', 'emotional_tone', 'moment_summary', 'overall_score',
                    'virality_score', 'interest_score', 'clarity_score', 'standalone_score',
                    'hook_score', 'information_value_score')
            }
            context['moment_type'] = evaluation.content_type or context['moment_type']
        return self._bounded(context, config.max_context_chars)

    @staticmethod
    def _bounded(context: dict, limit: int) -> dict:
        # Preserve the actual clip transcript first; trim optional context before metadata.
        context['context_before'] = context['context_before'][-1500:]
        context['context_after'] = context['context_after'][:1500]
        context['transcript'] = context['transcript'][:max(1000, limit - 3500)]
        return context
