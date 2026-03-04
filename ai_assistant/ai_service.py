"""Centralized OpenAI integration for MarvelSafari's AI layer.

This module provides a unified interface to OpenAI with:
- Token budget enforcement
- Cost tracking
- Prompt management integration
- Rate limit handling
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

try:  # pragma: no cover - imported at runtime
    from openai import OpenAI, APIError, RateLimitError, APITimeoutError
except Exception:  # pragma: no cover - allows unit tests without SDK
    OpenAI = None  # type: ignore[assignment]
    APIError = Exception  # type: ignore[assignment]
    RateLimitError = Exception  # type: ignore[assignment]
    APITimeoutError = Exception  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency for accurate token math
    import tiktoken
except Exception:  # pragma: no cover - fall back to naive token approximation
    tiktoken = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class TokenBudgetExceeded(Exception):
    """Raised when daily token or spend limits are exceeded."""


class AIServiceError(Exception):
    """Raised when the AI layer cannot complete a request."""


@dataclass
class AIServiceResult:
    data: Dict[str, Any]
    provider: str
    latency_ms: int
    usage: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            'data': self.data,
            'provider': self.provider,
            'latency_ms': self.latency_ms,
            'usage': self.usage,
        }


class AIUsageTracker:
    """Tracks token spend and prevents runaway OpenAI costs."""

    def __init__(self) -> None:
        self.daily_token_cap = int(getattr(settings, 'AI_MAX_DAILY_TOKENS', 200000))
        self.daily_cost_cap = float(getattr(settings, 'AI_MAX_DAILY_COST_USD', 75.0))
        self.prompt_cost = float(getattr(settings, 'AI_PROMPT_COST_PER_1K', 0.005))
        self.completion_cost = float(getattr(settings, 'AI_COMPLETION_COST_PER_1K', 0.015))
        logger_name = getattr(settings, 'AI_USAGE_LOGGER_NAME', 'ai_assistant.usage')
        self.logger = logging.getLogger(logger_name)

    def guard_capacity(self, estimated_tokens: int) -> None:
        tokens_key, cost_key = self._cache_keys()
        current_tokens = int(cache.get(tokens_key, 0))
        current_cost = float(cache.get(cost_key, 0.0))
        estimated_cost = self._estimate_cost(estimated_tokens, 0)
        if current_tokens + estimated_tokens > self.daily_token_cap or current_cost + estimated_cost > self.daily_cost_cap:
            raise TokenBudgetExceeded('Daily AI allowance reached. Please retry later today.')

    def register(self, provider: str, usage: Optional[Any]) -> Dict[str, Any]:
        usage_dict = usage if isinstance(usage, dict) else {}

        def _extract(*keys: str) -> int:
            for key in keys:
                if isinstance(usage_dict, dict) and key in usage_dict:
                    return int(usage_dict.get(key) or 0)
                if hasattr(usage, key):
                    return int(getattr(usage, key) or 0)
            return 0

        prompt_tokens = _extract('prompt_tokens', 'input_tokens')
        completion_tokens = _extract('completion_tokens', 'output_tokens')
        total_tokens = prompt_tokens + completion_tokens
        cost = self._estimate_cost(prompt_tokens, completion_tokens)
        tokens_key, cost_key = self._cache_keys()
        current_tokens = int(cache.get(tokens_key, 0))
        current_cost = float(cache.get(cost_key, 0.0))
        if current_tokens + total_tokens > self.daily_token_cap or current_cost + cost > self.daily_cost_cap:
            raise TokenBudgetExceeded('Daily AI allowance reached. Please retry later today.')
        ttl = 60 * 60 * 36  # 36 hours keeps one full day of history
        cache.set(tokens_key, current_tokens + total_tokens, ttl)
        cache.set(cost_key, round(current_cost + cost, 6), ttl)
        payload = {
            'provider': provider,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens,
            'usd_cost': round(cost, 4),
            'daily_tokens_used': current_tokens + total_tokens,
            'daily_cost_used': round(current_cost + cost, 4),
            'daily_token_cap': self.daily_token_cap,
            'daily_cost_cap': self.daily_cost_cap,
        }
        self.logger.info('ai_usage_event', extra={'ai_usage': payload})
        return payload

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        prompt_cost = (prompt_tokens / 1000) * self.prompt_cost
        completion_cost = (completion_tokens / 1000) * self.completion_cost
        return prompt_cost + completion_cost

    def _cache_keys(self) -> tuple[str, str]:
        stamp = timezone.now().strftime('%Y%m%d')
        return (f'ai_usage_tokens:{stamp}', f'ai_usage_cost:{stamp}')


class OpenAIAIService:
    """Reusable façade around the OpenAI Chat Completions API."""

    provider_name = 'openai'

    def __init__(self) -> None:
        if OpenAI is None:  # pragma: no cover - enforced at runtime
            raise AIServiceError('OpenAI SDK is not installed. Run `pip install --upgrade openai`.')
        api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not api_key:
            raise ImproperlyConfigured('OPENAI_API_KEY is not set. Add it to your .env file.')
        config = getattr(settings, 'AI_ASSISTANT', {})
        self.model = config.get('OPENAI_MODEL', 'gpt-4o-mini')
        self.temperature = config.get('TEMPERATURE', 0.2)
        self.max_output_tokens = config.get('MAX_OUTPUT_TOKENS', 900)
        self.timeout = getattr(settings, 'AI_OPENAI_TIMEOUT', 30)
        self.usage_tracker = AIUsageTracker()
        self.client = OpenAI(
            api_key=api_key,
            organization=getattr(settings, 'OPENAI_ORG_ID', None) or None,
            timeout=self.timeout,
            max_retries=getattr(settings, 'AI_OPENAI_MAX_RETRIES', 2),
        )
        
        # Load prompt registry
        from .prompts import PromptRegistry
        self.prompt_registry = PromptRegistry()

    # Public playbooks -----------------------------------------------------

    def support_chat(self, *, question: str, customer_context: Optional[Dict[str, Any]] = None) -> AIServiceResult:
        """Support chat using prompt registry."""
        from .prompts import render_prompt
        
        system_prompt, user_prompt, template = render_prompt('support_chat', {
            'customer_question': question,
            'context': customer_context or {},
        })
        return self._request(
            system_prompt, 
            user_prompt, 
            expect_json=template.expect_json,
            prompt_name=template.name,
        )

    def generate_itinerary(
        self,
        *,
        destination: str,
        budget: str,
        days: int,
        travel_style: str,
        interests: Optional[List[str]] = None,
    ) -> AIServiceResult:
        """Generate itinerary using prompt registry."""
        from .prompts import render_prompt
        
        system_prompt, user_prompt, template = render_prompt('itinerary_generator', {
            'destination': destination,
            'budget': budget,
            'days': days,
            'travel_style': travel_style,
            'interests': interests or [],
        })
        return self._request(
            system_prompt, 
            user_prompt, 
            expect_json=template.expect_json,
            prompt_name=template.name,
        )

    def recommend_destinations(
        self,
        *,
        preferences: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> AIServiceResult:
        """Recommend destinations using prompt registry."""
        from .prompts import render_prompt
        
        system_prompt, user_prompt, template = render_prompt('destination_recommendations', {
            'preferences': preferences,
            'history': history or [],
        })
        return self._request(
            system_prompt, 
            user_prompt, 
            expect_json=template.expect_json,
            prompt_name=template.name,
        )
    def generate_seo_content(
        self,
        *,
        destination: str,
        keywords: Optional[List[str]] = None,
        tone: str = 'inspirational',
    ) -> AIServiceResult:
        """Generate SEO content using prompt registry."""
        from .prompts import render_prompt
        
        system_prompt, user_prompt, template = render_prompt('seo_content', {
            'destination': destination,
            'keywords': keywords or [],
            'tone': tone,
        })
        return self._request(
            system_prompt, 
            user_prompt, 
            expect_json=template.expect_json,
            prompt_name=template.name,
        )

    def verify_car_listing(
        self,
        *,
        car_payload: Dict[str, Any],
    ) -> AIServiceResult:
        """Verify car listing using prompt registry."""
        from .prompts import render_prompt
        
        system_prompt, user_prompt, template = render_prompt('car_verification', {
            'car': car_payload,
        })
        return self._request(
            system_prompt, 
            user_prompt, 
            expect_json=template.expect_json,
            prompt_name=template.name,
        )

    # Internal helpers -----------------------------------------------------

    def _request(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        *, 
        expect_json: bool,
        prompt_name: str = '',
    ) -> AIServiceResult:
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ]
        estimated_tokens = self._estimate_tokens(messages) + self.max_output_tokens
        self.usage_tracker.guard_capacity(estimated_tokens)

        params: Dict[str, Any] = {
            'model': self.model,
            'messages': messages,
            'temperature': self.temperature,
            'max_tokens': self.max_output_tokens,
        }
        if expect_json:
            params['response_format'] = {'type': 'json_object'}

        started = time.perf_counter()
        try:
            response = self.client.chat.completions.create(**params)
        except RateLimitError as exc:  # type: ignore[misc]
            logger.warning('OpenAI rate limit: %s', exc)
            raise AIServiceError('OpenAI rate limit reached. Please try again in a moment.') from exc
        except (APITimeoutError, TimeoutError) as exc:  # type: ignore[name-defined]
            logger.error('OpenAI timeout: %s', exc)
            raise AIServiceError('OpenAI timeout. Please retry.') from exc
        except APIError as exc:  # type: ignore[misc]
            logger.exception('OpenAI API error: %s', exc)
            raise AIServiceError('OpenAI request failed.') from exc
        except Exception as exc:  # pragma: no cover
            logger.exception('Unexpected OpenAI failure: %s', exc)
            raise AIServiceError('Unexpected AI failure.') from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        message = response.choices[0].message
        content: str
        if isinstance(message.content, list):
            content = ''.join(part.get('text', '') for part in message.content if isinstance(part, dict))
        else:
            content = message.content or ''

        payload = self._parse_response(content, expect_json)
        usage_payload = self.usage_tracker.register(self.provider_name, getattr(response, 'usage', None))
        return AIServiceResult(
            data=payload,
            provider=self.provider_name,
            latency_ms=latency_ms,
            usage=usage_payload,
        )

    def _parse_response(self, raw: str, expect_json: bool) -> Dict[str, Any]:
        raw = (raw or '').strip()
        if not expect_json:
            return {'text': raw}
        if not raw:
            raise AIServiceError('AI response was empty.')
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIServiceError('AI returned invalid JSON.') from exc

    def _estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        if not tiktoken:
            joined = ' '.join(msg.get('content', '') for msg in messages)
            return len(joined.split()) * 2
        try:
            encoding = tiktoken.encoding_for_model(self.model)
        except Exception:
            encoding = tiktoken.get_encoding('cl100k_base')
        tokens = 0
        for message in messages:
            tokens += 4  # per-message overhead
            tokens += len(encoding.encode(message.get('content', '')))
        return tokens + 2
