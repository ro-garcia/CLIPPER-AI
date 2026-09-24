from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base
from ..detection.models import now

class Moment(Base):
    __tablename__ = 'moments'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(index=True)
    start: Mapped[float]
    end: Mapped[float]
    transcript_excerpt: Mapped[str] = mapped_column(Text)
    language: Mapped[str]
    moment_type: Mapped[str]
    detection_confidence: Mapped[float]
    detection_reasons: Mapped[list] = mapped_column(JSON)
    rule_revision: Mapped[int]
    status: Mapped[str] = mapped_column(default='CANDIDATE')
    media_status: Mapped[str] = mapped_column(default='PROCESSING')
    media_error: Mapped[str] = mapped_column(default='')
    clip_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(default=now)

class MomentFeedback(Base):
    __tablename__ = 'moment_feedback'
    id: Mapped[int] = mapped_column(primary_key=True)
    moment_id: Mapped[str] = mapped_column(index=True)
    evaluation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=now)
