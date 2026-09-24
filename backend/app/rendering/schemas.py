"""Validated, persisted local settings for subtitle and vertical rendering."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RenderSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')

    subtitles_enabled: bool = True
    subtitle_style: Literal['STANDARD', 'DYNAMIC'] = 'STANDARD'
    font: str = Field('Arial', min_length=1, max_length=120)
    font_size: int = Field(64, ge=18, le=180)
    font_color: str = Field('#FFFFFF', pattern=r'^#[0-9A-Fa-f]{6}$')
    outline_size: int = Field(4, ge=0, le=16)
    background: bool = False
    subtitle_position: Literal['TOP', 'MIDDLE', 'BOTTOM'] = 'BOTTOM'
    max_lines: int = Field(2, ge=1, le=3)
    max_chars_per_line: int = Field(35, ge=12, le=70)
    min_subtitle_duration: float = Field(.8, ge=.1, le=4)
    max_subtitle_duration: float = Field(4.0, ge=.5, le=10)
    highlight_words: bool = True
    animation_enabled: bool = False
    output_width: int = Field(1080, ge=240, le=2160, multiple_of=2)
    output_height: int = Field(1920, ge=426, le=3840, multiple_of=2)
    video_codec: Literal['libx264'] = 'libx264'
    audio_codec: Literal['aac'] = 'aac'
    crf: int = Field(21, ge=16, le=32)
    fps: int = Field(30, ge=0, le=60)
    reframing_mode: Literal['CENTER_CROP', 'SMART_CROP', 'SUBJECT_TRACKING'] = 'CENTER_CROP'
    background_mode: Literal['CROP', 'BLUR', 'BLACK'] = 'CROP'
    safe_area_top: int = Field(120, ge=0, le=800)
    safe_area_bottom: int = Field(260, ge=0, le=900)
    safe_area_left: int = Field(40, ge=0, le=500)
    safe_area_right: int = Field(40, ge=0, le=500)
    max_concurrent_renders: Literal[1] = 1

    @model_validator(mode='after')
    def validate_composition(self):
        if self.output_height <= self.output_width:
            raise ValueError('La salida debe ser vertical: la altura debe superar al ancho.')
        if self.max_subtitle_duration < self.min_subtitle_duration:
            raise ValueError('La duración máxima del subtítulo no puede ser menor que la mínima.')
        if self.safe_area_top + self.safe_area_bottom >= self.output_height:
            raise ValueError('Las áreas seguras verticales no dejan espacio para el video.')
        if self.safe_area_left + self.safe_area_right >= self.output_width:
            raise ValueError('Las áreas seguras horizontales no dejan espacio para el video.')
        return self
