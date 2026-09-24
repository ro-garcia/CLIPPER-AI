"""Build bounded transcript context while preserving the candidate verbatim."""
from __future__ import annotations

from sqlalchemy import select

from ..database import Session, Stream, Transcript
from ..detection.repository import rules_repository

_CLOSERS = ('.', '?', '!', '…', '。', '？', '！')


class AIContextBuilder:
    def build(self, moment: dict, config) -> dict:
        candidate = moment['transcript_excerpt']
        if len(candidate) > config.max_context_chars:
            raise ValueError('El candidato supera el límite de contexto. Aumenta Maximum Context Chars.')
        # A fragment with an open sentence receives extra context without a language-specific vocabulary.
        appears_incomplete = not candidate.rstrip().endswith(_CLOSERS)
        pre_seconds = config.max_pre_context_seconds if appears_incomplete else config.pre_context_seconds
        with Session() as db:
            rows = db.scalars(select(Transcript).where(
                Transcript.stream_id == moment['stream_id'],
                Transcript.end > moment['start'] - pre_seconds,
                Transcript.start < moment['end'] + config.post_context_seconds,
            ).order_by(Transcript.start)).all()
            stream = db.get(Stream, moment['stream_id'])
        before = ' '.join(row.text for row in rows if row.end <= moment['start'])
        after = ' '.join(row.text for row in rows if row.start >= moment['end'])
        remaining = config.max_context_chars - len(candidate)
        pre_budget = min(len(before), remaining // 2)
        post_budget = min(len(after), remaining - pre_budget)
        pre_budget = min(len(before), remaining - post_budget)
        profile = rules_repository.cache.snapshot
        return {
            'previous_context': before[-pre_budget:] if pre_budget else '',
            'candidate': candidate,
            'following_context': after[:post_budget],
            'moment_id': moment['id'],
            'stream_id': moment['stream_id'],
            'start_time': moment['start'],
            'end_time': moment['end'],
            'duration': round(moment['end'] - moment['start'], 3),
            'moment_type': moment['moment_type'],
            'detection_confidence': moment['detection_confidence'],
            'detection_reasons': moment['detection_reasons'][:20],
            'detection_profile': {'id': profile.profile_id, 'name': profile.profile_name,
                                  'revision': profile.revision},
            'stream_title': stream.title[:300] if stream else '',
            'stream_category': 'unknown',
            'language': moment['language'],
            'following_context_available': bool(after),
            'context_truncated': len(before) + len(after) > remaining,
            'used_pre_context_seconds': pre_seconds,
            'candidate_appears_incomplete': appears_incomplete,
        }
