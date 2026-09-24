"""Additive tables: existing streams, transcripts and clips are untouched."""
from datetime import datetime, timezone
from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

class RuleGroup(Base):
    __tablename__ = 'moment_rule_groups'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)

class DetectionRule(Base):
    __tablename__ = 'moment_detection_rules'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    pattern: Mapped[str] = mapped_column(Text)
    rule_type: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(default='')
    weight: Mapped[float]
    language: Mapped[str] = mapped_column(default='*')
    match_type: Mapped[str] = mapped_column(String)
    case_sensitive: Mapped[bool] = mapped_column(default=False)
    enabled: Mapped[bool] = mapped_column(default=True)
    group_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)

class DetectionProfile(Base):
    __tablename__ = 'moment_detection_profiles'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    group_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    rule_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)

class DetectionState(Base):
    __tablename__ = 'moment_detection_state'
    id: Mapped[int] = mapped_column(primary_key=True)
    active_profile_id: Mapped[str | None] = mapped_column(String, nullable=True)
