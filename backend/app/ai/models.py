"""Additive Phase 3 tables. Moments and prior clips are never replaced."""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base, engine
from ..detection.models import now


class AIConfiguration(Base):
    __tablename__ = 'ai_configuration'
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class AIEvaluation(Base):
    __tablename__ = 'moment_ai_evaluations'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    moment_id: Mapped[str] = mapped_column(ForeignKey('moments.id'), index=True)
    status: Mapped[str] = mapped_column(String, default='QUEUED', index=True)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    evaluation_version: Mapped[str] = mapped_column(String, default='v2')
    cache_key: Mapped[str] = mapped_column(String, default='', index=True)
    interest_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    clarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    virality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    standalone_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hook_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ending_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    information_value_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_dependency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completeness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    quality_level: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    detected_topic: Mapped[str | None] = mapped_column(String, nullable=True)
    emotional_tone: Mapped[str | None] = mapped_column(String, nullable=True)
    requires_context: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    moment_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Kept for preview data and backwards-compatible rows; direct columns are authoritative.
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    settings_snapshot: Mapped[dict] = mapped_column(JSON)
    context_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int] = mapped_column(default=0)
    attempts: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str] = mapped_column(Text, default='')
    error_code: Mapped[str] = mapped_column(String, default='')
    auto_clip_status: Mapped[str] = mapped_column(String, default='DISABLED')
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)


_ADDITIVE_COLUMNS = {
    'cache_key': "TEXT NOT NULL DEFAULT ''",
    'interest_score': 'REAL', 'clarity_score': 'REAL', 'virality_score': 'REAL',
    'standalone_score': 'REAL', 'hook_score': 'REAL', 'ending_score': 'REAL',
    'information_value_score': 'REAL', 'context_dependency_score': 'REAL',
    'completeness_score': 'REAL', 'overall_score': 'REAL', 'quality_level': 'TEXT',
    'content_type': 'TEXT', 'detected_topic': 'TEXT', 'emotional_tone': 'TEXT',
    'requires_context': 'BOOLEAN', 'moment_summary': 'TEXT', 'evaluation_reason': 'TEXT',
    'recommended_action': 'TEXT', 'input_tokens': 'INTEGER', 'output_tokens': 'INTEGER',
}


def upgrade_ai_schema() -> None:
    """Apply only additive SQLite columns to installations created before Phase 3."""
    with engine.begin() as connection:
        exists = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='moment_ai_evaluations'"))
        if exists.scalar() is None:
            return
        names = {row[1] for row in connection.execute(text('PRAGMA table_info(moment_ai_evaluations)'))}
        for name, definition in _ADDITIVE_COLUMNS.items():
            if name not in names:
                connection.execute(text(f'ALTER TABLE moment_ai_evaluations ADD COLUMN {name} {definition}'))
        connection.execute(text('CREATE INDEX IF NOT EXISTS ix_moment_ai_evaluations_cache_key ON moment_ai_evaluations (cache_key)'))
