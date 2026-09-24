"""Provider boundary. Ollama remains local and Mock only exists for tests."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol

import httpx

from .prompts.moment_evaluator import SYSTEM_PROMPT
from .schemas import MomentAIEvaluation


@dataclass(frozen=True)
class ProviderResult:
    evaluation: MomentAIEvaluation
    input_tokens: int | None = None
    output_tokens: int | None = None


class AIProvider(Protocol):
    async def evaluate_moment(self, context: dict) -> ProviderResult: ...


def prompt_payload(context: dict) -> str:
    """Delimit each data role without letting transcript text become prompt text."""
    metadata = {key: value for key, value in context.items()
                if key not in ('previous_context', 'candidate', 'following_context')}
    return '\n'.join((
        '<PREVIOUS_CONTEXT>', json.dumps(context['previous_context'], ensure_ascii=False), '</PREVIOUS_CONTEXT>',
        '<CANDIDATE_MOMENT>', json.dumps(context['candidate'], ensure_ascii=False), '</CANDIDATE_MOMENT>',
        '<FOLLOWING_CONTEXT>', json.dumps(context['following_context'], ensure_ascii=False), '</FOLLOWING_CONTEXT>',
        '<CANDIDATE_METADATA>', json.dumps(metadata, ensure_ascii=False), '</CANDIDATE_METADATA>',
    ))


class OllamaProvider:
    def __init__(self, config):
        self.config = config

    async def models(self):
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            response = await client.get(self.config.endpoint.rstrip('/') + '/api/tags')
            response.raise_for_status()
            return response.json().get('models', [])

    async def structured(self, system_prompt: str, user_payload: str, schema: dict,
                         *, num_predict: int = 1800) -> tuple[dict, int | None, int | None]:
        """Shared local structured-output transport for all Ollama features."""
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds, trust_env=False) as client:
            response = await client.post(self.config.endpoint.rstrip('/') + '/api/chat', json={
                'model': self.config.model,
                'stream': False,
                'think': False,
                'keep_alive': '2m',
                'format': schema,
                'options': {'temperature': self.config.temperature, 'num_ctx': 8192,
                            'num_predict': num_predict},
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_payload},
                ],
            })
            response.raise_for_status()
            payload = response.json()
        return (json.loads(payload['message']['content']), payload.get('prompt_eval_count'),
                payload.get('eval_count'))

    async def evaluate_moment(self, context: dict) -> ProviderResult:
        data, input_tokens, output_tokens = await self.structured(
            SYSTEM_PROMPT, prompt_payload(context), MomentAIEvaluation.model_json_schema(), num_predict=1400)
        return ProviderResult(
            evaluation=MomentAIEvaluation.model_validate(data),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class MockAIProvider:
    """Deterministic test provider; it is never selectable in product Settings."""
    def __init__(self, result: dict | MomentAIEvaluation, input_tokens: int = 23, output_tokens: int = 17):
        self.result = result
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    async def evaluate_moment(self, context: dict) -> ProviderResult:
        evaluation = self.result if isinstance(self.result, MomentAIEvaluation) else MomentAIEvaluation.model_validate(self.result)
        return ProviderResult(evaluation, self.input_tokens, self.output_tokens)
