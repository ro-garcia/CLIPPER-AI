from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from ..detection.models import now


class ClipMetadata(Base):
    __tablename__ = 'clip_metadata'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clip_id: Mapped[str] = mapped_column(ForeignKey('clips.id'), unique=True, index=True)
    general_metadata: Mapped[dict] = mapped_column(JSON)
    platform_metadata: Mapped[dict] = mapped_column(JSON)
    ai_model: Mapped[str] = mapped_column(String, default='')
    prompt_version: Mapped[str] = mapped_column(String, default='metadata-v1')
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)


class MetadataConfiguration(Base):
    __tablename__ = 'metadata_configuration'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
