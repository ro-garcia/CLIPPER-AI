"""The strict boundary between an untrusted model response and LiveClip data."""
from __future__ import annotations

from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

Score = Annotated[float, Field(ge=0, le=10, allow_inf_nan=False)]

CONTENT_TYPES = ('QUESTION_ANSWER', 'STRONG_STATEMENT', 'REACTION', 'STORY',
                 'EXPLANATION', 'ANNOUNCEMENT', 'CONTROVERSY', 'HUMOR',
                 'EDUCATIONAL', 'OPINION', 'NEWS', 'OTHER')
EMOTIONAL_TONES = ('NEUTRAL', 'EXCITED', 'ANGRY', 'FUNNY', 'SURPRISED',
                   'CONTROVERSIAL', 'INSPIRING', 'SERIOUS', 'CURIOUS',
                   'INFORMATIVE', 'THOUGHT_PROVOKING', 'OTHER')


class MomentAIEvaluation(BaseModel):
    """Only fields which the local model is allowed to decide."""
    model_config = ConfigDict(extra='forbid', strict=True)

    interest_score: Score
    clarity_score: Score
    virality_score: Score
    standalone_score: Score
    hook_score: Score
    ending_score: Score
    information_value_score: Score
    context_dependency_score: Score
    completeness_score: Score
    content_type: Literal[*CONTENT_TYPES]
    detected_topic: str = Field(min_length=1, max_length=300)
    emotional_tone: Literal[*EMOTIONAL_TONES]
    requires_context: bool
    moment_summary: str = Field(min_length=1, max_length=1500)
    evaluation_reason: str = Field(min_length=1, max_length=2500)
    language: str = Field(min_length=2, max_length=30)


class AISettings(BaseModel):
    """Persisted local-only evaluator settings. No provider secret is accepted."""
    model_config = ConfigDict(extra='forbid')

    enabled: bool = False
    provider: Literal['ollama'] = 'ollama'
    model: str = Field('', max_length=150)
    endpoint: str = 'http://127.0.0.1:11434'
    evaluation_mode: Literal['MANUAL', 'AUTOMATIC'] = 'MANUAL'
    pre_context_seconds: int = Field(20, ge=0, le=120)
    max_pre_context_seconds: int = Field(45, ge=0, le=180)
    post_context_seconds: int = Field(10, ge=0, le=60)
    max_context_chars: int = Field(12000, ge=1000, le=30000)
    temperature: float = Field(.1, ge=0, le=1)
    max_concurrent: int = Field(1, ge=1, le=1)
    max_retries: int = Field(2, ge=0, le=3)
    timeout_seconds: int = Field(30, ge=5, le=300)
    per_stream_limit: int = Field(100, ge=1, le=1000)
    create_clip_threshold: Score = 8.5
    review_threshold: Score = 7.0
    high_potential_threshold: Score = 8.5
    good_threshold: Score = 7.0
    medium_threshold: Score = 5.0
    weights: dict[str, float] = Field(default_factory=lambda: {
        'interest_score': .25, 'clarity_score': .20, 'virality_score': .20,
        'standalone_score': .15, 'hook_score': .10, 'ending_score': .05,
        'information_value_score': .05,
    })

    @model_validator(mode='before')
    @classmethod
    def migrate_phase_three_preview(cls, data):
        """Read previously saved preview settings without preserving auto clips."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        data.pop('automatic', None)
        if 'evaluation_mode' not in data:
            data['evaluation_mode'] = 'AUTOMATIC' if data.pop('auto_evaluate', False) else 'MANUAL'
        data.pop('auto_create_clips', None)
        data.pop('auto_clip_threshold', None)
        weights = data.get('weights')
        if isinstance(weights, dict) and 'hook_quality' in weights:
            data['weights'] = {
                'interest_score': .25, 'clarity_score': .20, 'virality_score': .20,
                'standalone_score': .15, 'hook_score': .10, 'ending_score': .05,
                'information_value_score': .05,
            }
        return data

    @model_validator(mode='after')
    def valid(self):
        url = urlparse(self.endpoint)
        if (url.scheme != 'http' or url.hostname not in ('localhost', '127.0.0.1', '::1')
                or url.username or url.password or url.query or url.fragment or url.path not in ('', '/')):
            raise ValueError('Ollama debe usar un endpoint HTTP local sin credenciales ni ruta.')
        if self.max_pre_context_seconds < self.pre_context_seconds:
            raise ValueError('El contexto anterior máximo no puede ser menor que el contexto anterior inicial.')
        if not (self.medium_threshold <= self.good_threshold <= self.high_potential_threshold):
            raise ValueError('Los umbrales LOW, MEDIUM, GOOD y HIGH deben estar ordenados.')
        if self.review_threshold > self.create_clip_threshold:
            raise ValueError('El umbral de revisión no puede superar el de recomendar clip.')
        expected = {'interest_score', 'clarity_score', 'virality_score', 'standalone_score',
                    'hook_score', 'ending_score', 'information_value_score'}
        if (set(self.weights) != expected or any(not 0 <= value <= 1 for value in self.weights.values())
                or abs(sum(self.weights.values()) - 1) > .00001):
            raise ValueError('Los siete pesos deben estar entre 0 y 1 y sumar 1.')
        if self.enabled and not self.model.strip():
            raise ValueError('Selecciona un modelo antes de activar la IA.')
        return self


def overall(evaluation: MomentAIEvaluation, config: AISettings) -> float:
    return round(sum(getattr(evaluation, field) * weight for field, weight in config.weights.items()), 1)


def quality_level(value: float, config: AISettings) -> str:
    if value >= config.high_potential_threshold:
        return 'HIGH_POTENTIAL'
    if value >= config.good_threshold:
        return 'GOOD'
    if value >= config.medium_threshold:
        return 'MEDIUM'
    return 'LOW'


def recommendation(value: float, config: AISettings) -> str:
    if value >= config.create_clip_threshold:
        return 'CREATE_CLIP'
    if value >= config.review_threshold:
        return 'REVIEW'
    return 'DISCARD'
