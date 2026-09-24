from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

ContentType = Literal['REACTION', 'FUNNY', 'RAGE', 'FAIL', 'WIN', 'CONTROVERSY',
                      'ARGUMENT', 'CONFESSION', 'REVEAL', 'STORY', 'OPINION',
                      'PREDICTION', 'INFORMATION', 'EMOTIONAL', 'CELEBRATION',
                      'TENSION', 'SHOCK', 'GAMEPLAY', 'MEMORABLE_QUOTE',
                      'UNEXPECTED', 'OTHER']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


def _hashtags(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        tag = ''.join(str(value).strip().split())
        if tag:
            tag = tag if tag.startswith('#') else '#' + tag
            if tag not in result:
                result.append(tag[:80])
    return result


class GeneralMetadata(StrictModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=2, max_length=1000)
    caption: str = Field(min_length=2, max_length=500)
    cover_text: str = Field(min_length=2, max_length=80)
    hashtags: list[str] = Field(min_length=3, max_length=8)
    keywords: list[str] = Field(min_length=1, max_length=20)
    category: str = Field(min_length=2, max_length=100)
    content_type: ContentType
    topic: str = Field(min_length=2, max_length=200)
    language: str = Field(default='es', min_length=2, max_length=20)
    title_variants: list[str] = Field(min_length=3, max_length=3)
    caption_variants: list[str] = Field(min_length=3, max_length=3)
    cover_text_variants: list[str] = Field(min_length=3, max_length=3)

    @field_validator('hashtags', mode='before')
    @classmethod
    def normalize_hashtags(cls, value):
        return _hashtags(value if isinstance(value, list) else [])


class CaptionPlatform(StrictModel):
    caption: str = Field(min_length=2, max_length=700)
    hashtags: list[str] = Field(min_length=3, max_length=8)

    @field_validator('hashtags', mode='before')
    @classmethod
    def normalize_hashtags(cls, value):
        return _hashtags(value if isinstance(value, list) else [])


class YouTubeShortsMetadata(StrictModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=2, max_length=1200)
    hashtags: list[str] = Field(min_length=3, max_length=8)

    @field_validator('hashtags', mode='before')
    @classmethod
    def normalize_hashtags(cls, value):
        return _hashtags(value if isinstance(value, list) else [])


class PlatformMetadata(StrictModel):
    tiktok: CaptionPlatform
    youtube_shorts: YouTubeShortsMetadata
    instagram_reels: CaptionPlatform
    facebook_reels: CaptionPlatform


class ContentMetadata(StrictModel):
    general: GeneralMetadata
    platforms: PlatformMetadata


class MetadataSettings(StrictModel):
    auto_generate_metadata: bool = True
    style: Literal['BALANCED', 'VIRAL', 'CLEAN', 'AGGRESSIVE'] = 'BALANCED'
    hashtag_count: int = Field(6, ge=3, le=8)
    context_before_seconds: int = Field(10, ge=0, le=30)
    context_after_seconds: int = Field(10, ge=0, le=30)
    max_context_chars: int = Field(10000, ge=2000, le=20000)
    streamer_name: str = Field('', max_length=120)
    streamer_main_topics: list[str] = Field(default_factory=list, max_length=20)
    streamer_metadata_style: str = Field('', max_length=300)


class RegenerateRequest(StrictModel):
    scope: Literal['TODO', 'TITLE', 'CAPTION', 'HASHTAGS', 'COVER_TEXT'] = 'TODO'
