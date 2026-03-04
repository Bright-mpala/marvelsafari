"""Views that expose MarvelSafari AI capabilities via JSON endpoints.

Architecture:
- All AI operations can run asynchronously via Celery tasks
- Views return task IDs for polling (async mode) or block for results (sync mode)
- Rate limiting is enforced at both view and per-user level
- Token usage is tracked for cost monitoring
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

from django.conf import settings
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AIRateLimit, AITaskResult
from .tasks import process_ai_request

logger = logging.getLogger(__name__)

RATE_LIMIT = getattr(settings, 'AI_RATE_LIMIT_REQUESTS_PER_MIN', 20)
RATE_RULE = f"{max(1, RATE_LIMIT)}/m"

# How long to keep task results (in seconds)
TASK_RESULT_TTL = int(getattr(settings, 'AI_TASK_RESULT_TTL', 3600))


def _ratelimit(view: type[APIView]) -> type[APIView]:
    return method_decorator(ratelimit(key='user_or_ip', rate=RATE_RULE, block=True), name='dispatch')(view)


class AIBaseAPIView(APIView):
    """
    Base class for AI endpoints with rate limiting and async support.
    
    Subclasses can use either:
    - _execute_async() for non-blocking task dispatch (returns task_id)
    - _execute_sync() for blocking execution (backward compatible)
    """
    
    permission_classes = [IsAuthenticatedOrReadOnly]
    operation_name: str = 'generic'
    
    def _check_user_rate_limit(self, request, estimated_tokens: int = 1000) -> tuple[bool, str]:
        """Check per-user rate limits in addition to endpoint rate limits."""
        if not request.user.is_authenticated:
            return True, ""  # Anonymous users handled by endpoint rate limit
        
        try:
            rate_limit = AIRateLimit.get_or_create_for_user(request.user)
            return rate_limit.check_daily_limit(estimated_tokens)
        except Exception as exc:
            logger.warning('Rate limit check failed: %s', exc)
            return True, ""  # Fail open
    
    def _execute_async(
        self,
        request,
        input_data: Dict[str, Any],
    ) -> Response:
        """
        Dispatch AI request to Celery task and return task ID for polling.
        
        Client should poll GET /api/ai/tasks/{task_id}/ for results.
        """
        # Check per-user rate limits
        allowed, reason = self._check_user_rate_limit(request)
        if not allowed:
            return Response({'detail': reason}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Create task tracking record
        task_id = str(uuid.uuid4())
        user_id = request.user.pk if request.user.is_authenticated else None
        
        task_result = AITaskResult.objects.create(
            task_id=task_id,
            task_type=self.operation_name,
            user_id=user_id,
            input_data=input_data,
            expires_at=timezone.now() + timezone.timedelta(seconds=TASK_RESULT_TTL),
        )
        
        # Dispatch to Celery
        try:
            process_ai_request.delay(
                task_id=task_id,
                operation=self.operation_name,
                input_data=input_data,
                user_id=user_id,
            )
        except Exception as exc:
            logger.error('Failed to dispatch AI task: %s', exc)
            task_result.mark_failed(str(exc))
            return Response(
                {'detail': 'Service temporarily unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        return Response({
            'task_id': task_id,
            'status': 'pending',
            'poll_url': f'/api/ai/tasks/{task_id}/',
        }, status=status.HTTP_202_ACCEPTED)
    
    def _execute_sync(
        self,
        request,
        operation_callable: Callable,
    ) -> Response:
        """
        Execute AI request synchronously (blocking).
        
        Use this only for backward compatibility or when immediate results are required.
        Prefer _execute_async() for better scalability.
        """
        from .ai_service import AIServiceError, OpenAIAIService, TokenBudgetExceeded
        
        # Check per-user rate limits
        allowed, reason = self._check_user_rate_limit(request)
        if not allowed:
            return Response({'detail': reason}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        try:
            service = OpenAIAIService()
            result = operation_callable(service)
            return result
        except TokenBudgetExceeded as exc:
            logger.warning('AI token budget reached: %s', exc)
            return Response({'detail': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        except AIServiceError as exc:
            logger.exception('AI provider unavailable: %s', exc)
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@_ratelimit
class AITaskStatusView(APIView):
    """Poll for AI task results."""
    
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get(self, request, task_id: str):
        """Get the status and results of an AI task."""
        try:
            task = AITaskResult.objects.get(task_id=task_id)
        except AITaskResult.DoesNotExist:
            return Response({'detail': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Security: only allow users to see their own tasks
        if request.user.is_authenticated:
            if task.user_id and task.user_id != request.user.pk and not request.user.is_staff:
                return Response({'detail': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)
        
        response_data = {
            'task_id': task.task_id,
            'task_type': task.task_type,
            'status': task.status,
            'created_at': task.created_at.isoformat(),
        }
        
        if task.status == 'completed':
            response_data.update({
                'data': task.result_data,
                'provider': task.provider,
                'latency_ms': task.latency_ms,
                'usage': task.usage,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            })
        elif task.status == 'failed':
            response_data['error'] = task.error_message
        
        return Response(response_data)


@_ratelimit
class SupportChatbotView(AIBaseAPIView):
    """AI concierge for booking, cancellation, visa, and policy questions."""
    
    operation_name = 'support_chat'

    def post(self, request, *args, **kwargs):
        payload = request.data or {}
        question = (payload.get('question') or '').strip()
        if not question:
            return Response({'detail': 'question is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if async mode is requested
        async_mode = payload.get('async', False)
        
        context = {
            'booking_reference': (payload.get('booking_reference') or '').strip() or None,
            'preferred_channel': payload.get('preferred_channel', 'web'),
            'customer_id': request.user.pk if request.user.is_authenticated else None,
            'recent_messages': payload.get('recent_messages') or request.session.get('support_thread', []),
            'policy_cache': request.session.get('policy_cache', {}),
        }
        
        input_data = {
            'question': question,
            'context': context,
        }
        
        if async_mode:
            return self._execute_async(request, input_data)
        
        # Sync mode - backward compatible
        from .ai_service import OpenAIAIService
        
        def op(service: OpenAIAIService) -> Response:
            result = service.support_chat(question=question, customer_context=context)
            return Response(result.as_dict())
        
        return self._execute_sync(request, op)


class SupportChatbotPageView(TemplateView):
    """Renders the concierge chat interface and hydrates it with API metadata."""

    template_name = 'ai_assistant/support_chatbot.html'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'api_url': reverse_lazy('ai:support_chatbot'),
                'task_status_url': '/api/ai/tasks/',
                'prefill_question': (self.request.GET.get('q') or '').strip(),
                'prefill_booking': (self.request.GET.get('booking') or '').strip(),
                'async_mode': True,  # Enable async by default in UI
            }
        )
        return context


@_ratelimit
class ItineraryGeneratorView(AIBaseAPIView):
    """Turns destination + budget + days into a structured itinerary."""
    
    operation_name = 'itinerary'

    def post(self, request, *args, **kwargs):
        payload = request.data or {}
        destination = (payload.get('destination') or '').strip()
        budget = (payload.get('budget') or '').strip()
        try:
            days = int(payload.get('days') or 0)
        except (TypeError, ValueError):
            days = 0
        travel_style = (payload.get('travel_style') or 'balanced').strip()
        interests = payload.get('interests') or []
        async_mode = payload.get('async', False)

        if not destination or not budget or days <= 0:
            return Response(
                {'detail': 'destination, budget, and a positive day count are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(interests, list):
            interests = [interests]
        
        input_data = {
            'destination': destination,
            'budget': budget,
            'days': days,
            'travel_style': travel_style,
            'interests': [str(item).strip() for item in interests if str(item).strip()],
        }
        
        if async_mode:
            return self._execute_async(request, input_data)
        
        # Sync mode
        from .ai_service import OpenAIAIService
        
        def op(service: OpenAIAIService) -> Response:
            result = service.generate_itinerary(**input_data)
            return Response(result.as_dict())

        return self._execute_sync(request, op)


@_ratelimit
class DestinationRecommendationView(AIBaseAPIView):
    """Suggests destinations based on user history and stated preferences."""
    
    operation_name = 'recommendations'

    def post(self, request, *args, **kwargs):
        payload = request.data or {}
        preferences = payload.get('preferences') or {}
        history = payload.get('history') or request.session.get('search_history', [])
        async_mode = payload.get('async', False)

        if not isinstance(preferences, dict):
            return Response({'detail': 'preferences must be an object'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(history, list):
            history = []

        if request.user.is_authenticated:
            preferences.setdefault('loyalty_tier', getattr(request.user, 'tier', 'standard'))
            preferences.setdefault('email', request.user.email)
        
        input_data = {
            'preferences': preferences,
            'history': history,
        }
        
        if async_mode:
            return self._execute_async(request, input_data)
        
        # Sync mode
        from .ai_service import OpenAIAIService
        
        def op(service: OpenAIAIService) -> Response:
            result = service.recommend_destinations(**input_data)
            return Response(result.as_dict())

        return self._execute_sync(request, op)


@_ratelimit
class SEOContentGeneratorView(AIBaseAPIView):
    """Produces SEO-ready JSON blocks for destination landing pages."""
    
    operation_name = 'seo_content'

    def post(self, request, *args, **kwargs):
        payload = request.data or {}
        destination = (payload.get('destination') or '').strip()
        keywords = payload.get('keywords') or []
        tone = (payload.get('tone') or 'inspirational').strip()
        async_mode = payload.get('async', False)

        if not destination:
            return Response({'detail': 'destination is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(keywords, list):
            keywords = [keywords]
        
        input_data = {
            'destination': destination,
            'keywords': [str(keyword).strip() for keyword in keywords if str(keyword).strip()],
            'tone': tone,
        }
        
        if async_mode:
            return self._execute_async(request, input_data)
        
        # Sync mode
        from .ai_service import OpenAIAIService
        
        def op(service: OpenAIAIService) -> Response:
            result = service.generate_seo_content(**input_data)
            return Response(result.as_dict())

        return self._execute_sync(request, op)


@_ratelimit
class AIUsageStatsView(APIView):
    """Get AI usage statistics for the current user."""
    
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get(self, request):
        """Get usage stats and remaining quota."""
        if not request.user.is_authenticated:
            return Response({
                'detail': 'Authentication required for usage stats'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        from .models import AIUsageRecord
        
        # Get daily usage
        daily_usage = AIUsageRecord.get_user_daily_usage(request.user.pk)
        
        # Get rate limit info
        try:
            rate_limit = AIRateLimit.get_or_create_for_user(request.user)
            quota = rate_limit.get_remaining_quota()
        except Exception:
            quota = {'tier': 'unknown'}
        
        return Response({
            'daily_usage': daily_usage,
            'remaining_quota': quota,
        })

