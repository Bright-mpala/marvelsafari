"""AI orchestration layer for MarvelSafari."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None

from properties.models import Property

logger = logging.getLogger(__name__)


class AIAssistantError(Exception):
    """Base class for AI assistant exceptions."""


class ProviderNotConfigured(AIAssistantError):
    """Raised when a provider is not available."""


class ProviderResponseError(AIAssistantError):
    """Raised when a provider returns an unexpected payload."""


class AIAssistantUnavailable(AIAssistantError):
    """Raised when no providers can service the request."""


@dataclass
class AIResult:
    data: Dict[str, Any]
    provider: str
    latency_ms: int
    usage: Dict[str, Any]


class BaseProvider:
    name = 'base'

    def generate(self, system_prompt: str, user_prompt: str, expect_json: bool = True):
        raise NotImplementedError


class OpenAIProvider(BaseProvider):
    name = 'openai'

    def __init__(self) -> None:
        api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not api_key or OpenAI is None:
            raise ProviderNotConfigured('OpenAI is not configured')
        self.client = OpenAI(api_key=api_key)
        config = getattr(settings, 'AI_ASSISTANT', {})
        self.model = config.get('OPENAI_MODEL', 'gpt-4o-mini')
        self.temperature = config.get('TEMPERATURE', 0.2)
        self.max_tokens = config.get('MAX_OUTPUT_TOKENS', 900)

    def generate(self, system_prompt: str, user_prompt: str, expect_json: bool = True):
        params = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
        }
        if expect_json:
            params['response_format'] = {'type': 'json_object'}

        response = self.client.chat.completions.create(**params)
        message = response.choices[0].message
        content = ''
        if isinstance(message.content, list):
            content = ''.join(part.get('text', '') for part in message.content)
        else:
            content = message.content or ''

        usage = getattr(response, 'usage', None)
        usage_payload = {}
        if usage:
            usage_payload = {
                'prompt_tokens': getattr(usage, 'prompt_tokens', None),
                'completion_tokens': getattr(usage, 'completion_tokens', None),
                'total_tokens': getattr(usage, 'total_tokens', None),
            }
        return content.strip(), usage_payload


class AnthropicProvider(BaseProvider):
    name = 'anthropic'

    def __init__(self) -> None:
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        if not api_key or anthropic is None:
            raise ProviderNotConfigured('Anthropic is not configured')
        self.client = anthropic.Anthropic(api_key=api_key)
        config = getattr(settings, 'AI_ASSISTANT', {})
        self.model = config.get('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')
        self.temperature = config.get('TEMPERATURE', 0.2)
        self.max_tokens = config.get('MAX_OUTPUT_TOKENS', 900)

    def generate(self, system_prompt: str, user_prompt: str, expect_json: bool = True):
        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{'role': 'user', 'content': user_prompt}],
        )
        text_parts = []
        for block in response.content:
            text = getattr(block, 'text', '')
            if text:
                text_parts.append(text)
        content = ''.join(text_parts)
        usage_payload = {
            'input_tokens': getattr(response.usage, 'input_tokens', None),
            'output_tokens': getattr(response.usage, 'output_tokens', None),
        }
        return content.strip(), usage_payload


class LocalRulesProvider(BaseProvider):
    """Heuristic fallback when APIs are unavailable."""

    name = 'local_rules'

    def generate(self, system_prompt: str, user_prompt: str, expect_json: bool = True):  # noqa: ARG002
        system_lower = system_prompt.lower()
        lowered = user_prompt.lower()

        if 'deals engine' in system_lower:
            payload = {
                'deals': [
                    {
                        'title': 'Featured stay in Nairobi',
                        'reason': 'Popular pick when customers mention deals',
                        'urgency': 'medium',
                    }
                ],
                'summary': 'Share curated deals manually until premium models are enabled.',
            }
            return json.dumps(payload), {}

        if 'booking records' in system_lower:
            payload = {
                'summary': user_prompt[:400],
                'priority': 'normal',
                'tags': ['booking_intel'],
                'recommended_actions': ['Verify availability manually', 'Follow up with customer'],
                'structured': {
                    'needs': 'Manual review',
                    'risk_flags': [],
                },
            }
            return json.dumps(payload), {}

        priority = 'normal'
        intent = 'general_support'
        tags: List[str] = []
        if 'refund' in lowered or 'cancel' in lowered:
            intent = 'cancellation'
            priority = 'high'
            tags.append('refund')
        elif 'book' in lowered or 'availability' in lowered:
            intent = 'booking_question'
            tags.append('booking')
        elif 'deal' in lowered or 'discount' in lowered:
            intent = 'deal_request'
            tags.append('deals')
        if 'urgent' in lowered or 'asap' in lowered:
            priority = 'urgent'

        payload = {
            'summary': user_prompt[:400],
            'intent': intent,
            'priority': priority,
            'sentiment_score': 0.1,
            'tags': tags,
            'recommended_actions': [
                'Acknowledge the request',
                'Route to a human agent if unsure',
            ],
            'suggested_reply': 'Thanks for reaching out! Our team will review and follow up shortly.',
            'status': 'triaged',
            'deal_recommendations': [],
        }
        return json.dumps(payload), {}


class AIAssistantOrchestrator:
    """Coordinates prompts across providers."""

    def __init__(self, preferred_provider: Optional[str] = None) -> None:
        self.preferred_provider = preferred_provider
        self.config = getattr(settings, 'AI_ASSISTANT', {})
        self.providers = self._build_providers()

    # Provider orchestration -------------------------------------------------
    def _build_providers(self):
        provider_order = []
        env_order = self.config.get('PROVIDER_ORDER', [])
        env_order = [provider.strip().lower() for provider in env_order if provider]
        if self.preferred_provider:
            provider_order.append(self.preferred_provider.lower())
        default_provider = self.config.get('DEFAULT_PROVIDER', 'openai').lower()
        provider_order.append(default_provider)
        provider_order.extend(env_order)
        # Always ensure OpenAI is considered as a fallback since it is supported by default.
        provider_order.append('openai')

        built = []
        seen = set()
        for provider_key in provider_order:
            if provider_key in seen:
                continue
            seen.add(provider_key)
            try:
                if provider_key == 'openai':
                    built.append(OpenAIProvider())
                elif provider_key == 'anthropic':
                    built.append(AnthropicProvider())
            except ProviderNotConfigured:
                continue

        built.append(LocalRulesProvider())
        return built

    def _ensure_json(self, raw: str) -> Dict[str, Any]:
        raw = raw.strip()
        if not raw:
            raise ProviderResponseError('Empty AI response')
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            start = raw.find('{')
            end = raw.rfind('}')
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(raw[start:end + 1])
                except json.JSONDecodeError:
                    pass
            raise ProviderResponseError(f'Failed to parse AI response: {exc}')

    def _run_prompt(self, system_prompt: str, user_prompt: str, expect_json: bool = True) -> AIResult:
        last_error: Optional[Exception] = None
        for provider in self.providers:
            started = time.perf_counter()
            try:
                raw_content, usage = provider.generate(system_prompt, user_prompt, expect_json=expect_json)
                latency_ms = int((time.perf_counter() - started) * 1000)
                data = self._ensure_json(raw_content) if expect_json else {'text': raw_content}
                return AIResult(data=data, provider=provider.name, latency_ms=latency_ms, usage=usage or {})
            except ProviderResponseError as exc:
                last_error = exc
                logger.warning('Provider %s returned invalid payload: %s', provider.name, exc)
                continue
            except ProviderNotConfigured as exc:
                last_error = exc
                continue
        raise AIAssistantUnavailable(str(last_error) if last_error else 'No provider available')

    # Public playbooks ------------------------------------------------------
    def triage_support_thread(self, thread_payload: Dict[str, Any], recent_messages: Optional[List[Dict[str, Any]]] = None) -> AIResult:
        system_prompt = (
            'You are MarvelSafari\'s concierge AI. Summarize travel support conversations, '
            'detect intent, urgency, and craft a respectful reply. Always respond with valid JSON.'
        )
        prompt = json.dumps(
            {
                'thread': thread_payload,
                'recent_messages': recent_messages or [],
                'required_fields': [
                    'summary',
                    'intent',
                    'priority',
                    'sentiment_score',
                    'recommended_actions',
                    'suggested_reply',
                    'status',
                    'tags',
                    'deal_recommendations',
                    'booking_context',
                ],
            },
            ensure_ascii=False,
        )
        return self._run_prompt(system_prompt, prompt, expect_json=True)

    def analyze_booking_inquiry(self, booking_payload: Dict[str, Any]) -> AIResult:
        system_prompt = (
            'You review MarvelSafari booking records. Extract structured insights, unmet needs, '
            'risk flags, and upsell opportunities. Respond using JSON.'
        )
        prompt = json.dumps(
            {
                'booking': booking_payload,
                'required_fields': [
                    'summary',
                    'priority',
                    'tags',
                    'recommended_actions',
                    'structured',
                ],
            },
            ensure_ascii=False,
        )
        return self._run_prompt(system_prompt, prompt, expect_json=True)

    def generate_deal_recommendations(self, customer_profile: Dict[str, Any], limit: int = 4) -> AIResult:
        inventory = self._inventory_snapshot(limit)
        system_prompt = (
            'You are the MarvelSafari deals engine. Match customers with available properties or tours '
            'and explain why each option fits. Output JSON with `deals` (array) and `summary`.'
        )
        prompt = json.dumps(
            {
                'customer': customer_profile,
                'inventory': inventory,
                'required_fields': ['deals', 'summary'],
            },
            ensure_ascii=False,
        )
        return self._run_prompt(system_prompt, prompt, expect_json=True)

    # Helpers ----------------------------------------------------------------
    def _inventory_snapshot(self, limit: int) -> List[Dict[str, Any]]:
        qs = Property.objects.filter(status='active').order_by('-is_featured', '-star_rating')[:limit]
        snapshot: List[Dict[str, Any]] = []
        for prop in qs:
            snapshot.append(
                {
                    'id': str(prop.id),
                    'name': prop.name,
                    'city': prop.city,
                    'country': prop.country.code,
                    'star_rating': prop.star_rating,
                    'minimum_price': self._safe_decimal(prop.minimum_price),
                    'amenities_count': prop.amenities.count(),
                    'is_featured': prop.is_featured,
                }
            )
        return snapshot

    @staticmethod
    def _safe_decimal(value: Optional[Decimal]) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
