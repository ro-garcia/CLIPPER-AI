from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

Platform = Literal['youtube', 'tiktok', 'instagram', 'facebook']
Workflow = Literal['MANUAL', 'REVIEW', 'AUTOMATIC']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PublishingSettings(StrictModel):
    social_publishing_enabled: bool = True
    publishing_mode: Literal['mock', 'real'] = 'mock'
    safe_publish_mode: bool = True
    publication_workflow: Workflow = 'REVIEW'
    max_concurrent_publications: int = Field(2, ge=1, le=4)
    max_retry_attempts: int = Field(3, ge=1, le=5)
    missed_schedule_policy: Literal['PUBLISH_WHEN_AVAILABLE', 'ASK_USER', 'CANCEL'] = 'PUBLISH_WHEN_AVAILABLE'
    youtube_enabled: bool = True
    tiktok_enabled: bool = True
    instagram_enabled: bool = True
    facebook_enabled: bool = True
    youtube_privacy_status: Literal['private', 'unlisted', 'public'] = 'private'
    auto_publish: bool = False
    minimum_score: float = Field(9.0, ge=0, le=10)
    auto_publish_platforms: list[Platform] = Field(default_factory=list)
    allowed_content_types: list[str] = Field(default_factory=list)
    blocked_content_types: list[str] = Field(default_factory=lambda: ['CONTROVERSY'])


class PlatformSelection(StrictModel):
    platform: Platform
    account_id: str = Field(min_length=1, max_length=100)
    overrides: dict[str, str | list[str]] = Field(default_factory=dict)


class CreatePublications(StrictModel):
    clip_id: str = Field(min_length=1, max_length=100)
    platforms: list[PlatformSelection] = Field(min_length=1, max_length=4)
    scheduled_at: datetime | None = None
    explicit_republish: bool = False

    @field_validator('scheduled_at')
    @classmethod
    def timezone_required(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError('La fecha programada debe incluir zona horaria.')
        return value
