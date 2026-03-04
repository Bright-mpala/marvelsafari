"""Celery tasks for running AI workflows asynchronously.

All AI operations should go through these tasks to avoid blocking
the request/response cycle. Views return task IDs for polling.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# Cost rates per 1K tokens (configurable via settings)
COST_RATES = {
    'openai': {
        'prompt': float(getattr(settings, 'AI_PROMPT_COST_PER_1K', 0.005)),
        'completion': float(getattr(settings, 'AI_COMPLETION_COST_PER_1K', 0.015)),
    },
    'anthropic': {
        'prompt': float(getattr(settings, 'AI_ANTHROPIC_PROMPT_COST_PER_1K', 0.003)),
        'completion': float(getattr(settings, 'AI_ANTHROPIC_COMPLETION_COST_PER_1K', 0.015)),
    },
}


def _get_model(app_label: str, model_name: str):
    """Lazy model loading to avoid circular imports."""
    return apps.get_model(app_label, model_name)


def _get_support_thread(thread_id):
    SupportThread = _get_model('ai_assistant', 'SupportThread')
    try:
        return SupportThread.objects.get(pk=thread_id)
    except SupportThread.DoesNotExist:
        logger.warning('SupportThread %s not found for AI processing', thread_id)
        return None


def _get_task_result(task_id: str):
    """Get or create AITaskResult for tracking."""
    AITaskResult = _get_model('ai_assistant', 'AITaskResult')
    try:
        return AITaskResult.objects.get(task_id=task_id)
    except AITaskResult.DoesNotExist:
        return None


def _record_usage(
    user_id: Optional[int],
    provider: str,
    model: str,
    operation: str,
    usage: Dict[str, Any],
    latency_ms: int,
    success: bool = True,
    error_type: str = '',
    prompt_name: str = '',
    prompt_version: str = '',
    metadata: Dict[str, Any] = None
) -> None:
    """Record AI usage for cost tracking."""
    AIUsageRecord = _get_model('ai_assistant', 'AIUsageRecord')
    
    prompt_tokens = usage.get('prompt_tokens') or usage.get('input_tokens') or 0
    completion_tokens = usage.get('completion_tokens') or usage.get('output_tokens') or 0
    total_tokens = prompt_tokens + completion_tokens
    
    rates = COST_RATES.get(provider, COST_RATES['openai'])
    prompt_cost = Decimal(str((prompt_tokens / 1000) * rates['prompt']))
    completion_cost = Decimal(str((completion_tokens / 1000) * rates['completion']))
    total_cost = prompt_cost + completion_cost
    
    AIUsageRecord.objects.create(
        user_id=user_id,
        provider=provider,
        model=model,
        operation=operation,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        prompt_cost_usd=prompt_cost,
        completion_cost_usd=completion_cost,
        total_cost_usd=total_cost,
        latency_ms=latency_ms,
        success=success,
        error_type=error_type,
        request_metadata=metadata or {},
    )


def _check_rate_limit(user_id: Optional[int], estimated_tokens: int = 1000) -> tuple[bool, str]:
    """Check if user can make an AI request."""
    if not user_id:
        # Anonymous users get limited quota from cache
        from django.core.cache import cache
        key = f"ai_anon_requests:{timezone.now().strftime('%Y%m%d')}"
        count = cache.get(key, 0)
        limit = int(getattr(settings, 'AI_ANONYMOUS_DAILY_LIMIT', 50))
        if count >= limit:
            return False, "Anonymous daily limit reached"
        cache.set(key, count + 1, 86400)
        return True, ""
    
    AIRateLimit = _get_model('ai_assistant', 'AIRateLimit')
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(pk=user_id)
        rate_limit = AIRateLimit.get_or_create_for_user(user)
        return rate_limit.check_daily_limit(estimated_tokens)
    except Exception as exc:
        logger.warning('Rate limit check failed: %s', exc)
        return True, ""  # Fail open on errors


@shared_task(bind=True, max_retries=2, time_limit=120)
def process_ai_request(
    self,
    task_id: str,
    operation: str,
    input_data: Dict[str, Any],
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Generic AI request processor.
    
    Handles all AI operations through a unified interface:
    - Rate limit checking
    - Provider selection and fallback
    - Usage recording
    - Result storage
    """
    from .services import AIAssistantOrchestrator, AIAssistantUnavailable
    from .prompts import get_prompt, render_prompt
    
    task_result = _get_task_result(task_id)
    if task_result:
        task_result.status = 'processing'
        task_result.save(update_fields=['status'])
    
    # Check rate limits
    allowed, reason = _check_rate_limit(user_id, estimated_tokens=1000)
    if not allowed:
        error = f"Rate limit exceeded: {reason}"
        if task_result:
            task_result.mark_failed(error)
        return {'error': error, 'rate_limited': True}
    
    orchestrator = AIAssistantOrchestrator()
    
    try:
        # Route to appropriate operation
        if operation == 'support_chat':
            result = _execute_support_chat(orchestrator, input_data)
        elif operation == 'itinerary':
            result = _execute_itinerary(orchestrator, input_data)
        elif operation == 'recommendations':
            result = _execute_recommendations(orchestrator, input_data)
        elif operation == 'seo_content':
            result = _execute_seo_content(orchestrator, input_data)
        elif operation == 'triage':
            result = _execute_triage(orchestrator, input_data)
        elif operation == 'booking_analysis':
            result = _execute_booking_analysis(orchestrator, input_data)
        elif operation == 'deal_recommendations':
            result = _execute_deal_recommendations(orchestrator, input_data)
        else:
            raise ValueError(f"Unknown operation: {operation}")
        
        # Record usage
        _record_usage(
            user_id=user_id,
            provider=result.provider,
            model=getattr(settings, 'AI_ASSISTANT', {}).get('OPENAI_MODEL', 'gpt-4o-mini'),
            operation=operation,
            usage=result.usage,
            latency_ms=result.latency_ms,
            prompt_name=operation,
        )
        
        # Update task result
        if task_result:
            task_result.mark_completed(
                result=result.data,
                provider=result.provider,
                latency_ms=result.latency_ms,
                usage=result.usage,
            )
        
        return {
            'success': True,
            'data': result.data,
            'provider': result.provider,
            'latency_ms': result.latency_ms,
        }
        
    except AIAssistantUnavailable as exc:
        logger.error('AI service unavailable for %s: %s', operation, exc)
        if task_result:
            task_result.mark_failed(str(exc))
        raise self.retry(exc=exc, countdown=90)
    
    except Exception as exc:
        logger.exception('AI task failed for %s: %s', operation, exc)
        _record_usage(
            user_id=user_id,
            provider='unknown',
            model='unknown',
            operation=operation,
            usage={},
            latency_ms=0,
            success=False,
            error_type=type(exc).__name__,
        )
        if task_result:
            task_result.mark_failed(str(exc))
        raise


def _execute_support_chat(orchestrator, input_data: Dict[str, Any]):
    """Execute support chat operation."""
    from .prompts import render_prompt
    
    system_prompt, user_prompt, template = render_prompt('support_chat', {
        'customer_question': input_data.get('question', ''),
        'context': input_data.get('context', {}),
    })
    
    return orchestrator._run_prompt(system_prompt, user_prompt, expect_json=True)


def _execute_itinerary(orchestrator, input_data: Dict[str, Any]):
    """Execute itinerary generation."""
    from .prompts import render_prompt
    
    system_prompt, user_prompt, template = render_prompt('itinerary_generator', {
        'destination': input_data.get('destination', ''),
        'budget': input_data.get('budget', ''),
        'days': input_data.get('days', 1),
        'travel_style': input_data.get('travel_style', 'balanced'),
        'interests': input_data.get('interests', []),
    })
    
    return orchestrator._run_prompt(system_prompt, user_prompt, expect_json=True)


def _execute_recommendations(orchestrator, input_data: Dict[str, Any]):
    """Execute destination recommendations."""
    from .prompts import render_prompt
    
    system_prompt, user_prompt, template = render_prompt('destination_recommendations', {
        'preferences': input_data.get('preferences', {}),
        'history': input_data.get('history', []),
    })
    
    return orchestrator._run_prompt(system_prompt, user_prompt, expect_json=True)


def _execute_seo_content(orchestrator, input_data: Dict[str, Any]):
    """Execute SEO content generation."""
    from .prompts import render_prompt
    
    system_prompt, user_prompt, template = render_prompt('seo_content', {
        'destination': input_data.get('destination', ''),
        'keywords': input_data.get('keywords', []),
        'tone': input_data.get('tone', 'inspirational'),
    })
    
    return orchestrator._run_prompt(system_prompt, user_prompt, expect_json=True)


def _execute_triage(orchestrator, input_data: Dict[str, Any]):
    """Execute support thread triage."""
    return orchestrator.triage_support_thread(
        thread_payload=input_data.get('thread', {}),
        recent_messages=input_data.get('recent_messages', []),
    )


def _execute_booking_analysis(orchestrator, input_data: Dict[str, Any]):
    """Execute booking analysis."""
    return orchestrator.analyze_booking_inquiry(
        booking_payload=input_data.get('booking', {}),
    )


def _execute_deal_recommendations(orchestrator, input_data: Dict[str, Any]):
    """Execute deal recommendations."""
    return orchestrator.generate_deal_recommendations(
        customer_profile=input_data.get('customer', {}),
        limit=input_data.get('limit', 4),
    )


@shared_task(bind=True, max_retries=2, time_limit=120)
def triage_support_thread_task(self, thread_id):
    """Re-run AI triage for a support thread."""
    from .services import AIAssistantOrchestrator, AIAssistantUnavailable

    thread = _get_support_thread(thread_id)
    if not thread:
        return

    orchestrator = AIAssistantOrchestrator()
    try:
        result = orchestrator.triage_support_thread(
            thread_payload={
                'subject': thread.subject,
                'message': thread.latest_customer_message,
                'customer_name': thread.customer_name,
                'customer_email': thread.customer_email,
            },
            recent_messages=thread.raw_messages,
        )
    except AIAssistantUnavailable as exc:
        logger.error('AI triage unavailable: %s', exc)
        raise self.retry(exc=exc, countdown=90)

    thread.apply_triage_result(result.data, result.provider, result.latency_ms)
    thread.save()
    
    # Record usage
    _record_usage(
        user_id=None,
        provider=result.provider,
        model=getattr(settings, 'AI_ASSISTANT', {}).get('OPENAI_MODEL', 'gpt-4o-mini'),
        operation='triage_support_thread',
        usage=result.usage,
        latency_ms=result.latency_ms,
        prompt_name='support_triage',
    )


@shared_task(bind=True, max_retries=2, time_limit=120)
def refresh_deal_recommendations_task(self, thread_id):
    """Refresh deal recommendations for a support thread."""
    from .services import AIAssistantOrchestrator, AIAssistantUnavailable

    thread = _get_support_thread(thread_id)
    if not thread:
        return

    orchestrator = AIAssistantOrchestrator()
    try:
        result = orchestrator.generate_deal_recommendations(
            customer_profile={
                'intent': thread.intent_label,
                'priority': thread.priority,
                'customer_email': thread.customer_email,
                'tags': thread.tags,
            },
        )
    except AIAssistantUnavailable as exc:
        logger.warning('Deal recommendation refresh failed: %s', exc)
        raise self.retry(exc=exc, countdown=120)

    thread.deal_recommendations = result.data.get('deals', [])
    if result.data.get('summary'):
        actions = list(thread.ai_recommended_actions or [])
        actions.append(result.data['summary'])
        thread.ai_recommended_actions = actions
    thread.last_ai_provider = result.provider
    thread.last_ai_latency_ms = result.latency_ms
    thread.save(update_fields=['deal_recommendations', 'ai_recommended_actions', 'last_ai_provider', 'last_ai_latency_ms'])
    
    # Record usage
    _record_usage(
        user_id=None,
        provider=result.provider,
        model=getattr(settings, 'AI_ASSISTANT', {}).get('OPENAI_MODEL', 'gpt-4o-mini'),
        operation='deal_recommendations',
        usage=result.usage,
        latency_ms=result.latency_ms,
        prompt_name='deal_recommendations',
    )


@shared_task(bind=True, max_retries=2, time_limit=120)
def analyze_booking_async(self, booking_id: int, user_id: Optional[int] = None):
    """
    Async booking analysis - used by signals to avoid blocking.
    """
    from .services import AIAssistantOrchestrator, AIAssistantUnavailable
    from .models import AIAssistantInsight, SupportThread
    from bookings.models import Booking
    
    try:
        booking = Booking.objects.select_related('property', 'user').get(pk=booking_id)
    except Booking.DoesNotExist:
        logger.warning('Booking %s not found for AI analysis', booking_id)
        return
    
    orchestrator = AIAssistantOrchestrator()
    payload = {
        'booking_id': str(booking.pk),
        'property_name': booking.property.name,
        'property_city': booking.property.city,
        'guests': booking.guests,
        'check_in': booking.check_in_date.isoformat(),
        'check_out': booking.check_out_date.isoformat(),
        'special_requests': booking.special_requests or '',
        'status': booking.status,
        'customer_email': booking.user.email,
    }
    
    try:
        result = orchestrator.analyze_booking_inquiry(payload)
    except AIAssistantUnavailable as exc:
        logger.debug('Booking AI analysis deferred: %s', exc)
        raise self.retry(exc=exc, countdown=120)
    
    # Create insight
    insight = AIAssistantInsight.objects.create(
        content_object=booking,
        insight_type='booking_summary',
        title=f"Booking {booking.pk} insight",
        body=result.data.get('summary', ''),
        payload=result.data,
        provider=result.provider,
        latency_ms=result.latency_ms,
    )
    
    # Create/update support thread
    thread, _ = SupportThread.objects.get_or_create(
        related_booking=booking,
        defaults={
            'source': 'booking',
            'channel': 'in_app',
            'customer_email': booking.user.email,
            'customer_name': booking.user.get_full_name() or booking.user.email,
            'subject': f"Booking {booking.pk} follow-up",
            'latest_customer_message': booking.special_requests or '',
        }
    )
    
    if booking.special_requests:
        thread.add_message('customer', booking.special_requests, {'origin': 'booking_special_requests'})
    
    thread.apply_triage_result({
        'summary': result.data.get('summary'),
        'priority': result.data.get('priority', thread.priority),
        'booking_context': result.data.get('structured', {}),
        'recommended_actions': result.data.get('recommended_actions'),
        'tags': result.data.get('tags'),
    }, provider=result.provider, latency_ms=result.latency_ms)
    thread.save()
    
    # Record usage
    _record_usage(
        user_id=user_id,
        provider=result.provider,
        model=getattr(settings, 'AI_ASSISTANT', {}).get('OPENAI_MODEL', 'gpt-4o-mini'),
        operation='booking_analysis',
        usage=result.usage,
        latency_ms=result.latency_ms,
        prompt_name='booking_analysis',
    )
    
    logger.debug('Stored AI insight %s for booking %s', insight.pk, booking.pk)


@shared_task
def cleanup_expired_task_results():
    """Periodic task to clean up expired AI task results."""
    AITaskResult = _get_model('ai_assistant', 'AITaskResult')
    count = AITaskResult.cleanup_expired()
    if count:
        logger.info('Cleaned up %d expired AI task results', count)
    return count

