"""Database models for AI-driven workflows."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class AIUsageRecord(models.Model):
    """
    Persistent record of AI API usage for cost tracking and auditing.
    
    Enables:
    - Per-user and per-endpoint cost analysis
    - Daily/monthly budget enforcement
    - Usage auditing and reporting
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_usage_records'
    )
    
    provider = models.CharField(max_length=50)  # openai, anthropic, etc.
    model = models.CharField(max_length=100)
    operation = models.CharField(max_length=100)  # support_chat, itinerary, etc.
    prompt_name = models.CharField(max_length=100, blank=True)
    prompt_version = models.CharField(max_length=20, blank=True)
    
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    
    prompt_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal('0'))
    completion_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal('0'))
    total_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal('0'))
    
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    success = models.BooleanField(default=True)
    error_type = models.CharField(max_length=100, blank=True)
    
    request_metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['operation', 'created_at']),
            models.Index(fields=['provider', 'model']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self) -> str:
        return f"AIUsage({self.operation}, {self.total_tokens} tokens, ${self.total_cost_usd})"
    
    @classmethod
    def get_user_daily_usage(cls, user_id: int, date: Optional[timezone.datetime] = None) -> Dict[str, Any]:
        """Get aggregated daily usage for a user."""
        if date is None:
            date = timezone.now()
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timezone.timedelta(days=1)
        
        aggregates = cls.objects.filter(
            user_id=user_id,
            created_at__gte=start,
            created_at__lt=end,
            success=True
        ).aggregate(
            total_tokens=Sum('total_tokens'),
            total_cost=Sum('total_cost_usd'),
            request_count=models.Count('id')
        )
        
        return {
            'tokens': aggregates['total_tokens'] or 0,
            'cost_usd': float(aggregates['total_cost'] or 0),
            'requests': aggregates['request_count'] or 0,
            'date': start.date().isoformat(),
        }
    
    @classmethod
    def get_daily_totals(cls, date: Optional[timezone.datetime] = None) -> Dict[str, Any]:
        """Get aggregated daily usage across all users."""
        if date is None:
            date = timezone.now()
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timezone.timedelta(days=1)
        
        aggregates = cls.objects.filter(
            created_at__gte=start,
            created_at__lt=end,
            success=True
        ).aggregate(
            total_tokens=Sum('total_tokens'),
            total_cost=Sum('total_cost_usd'),
            request_count=models.Count('id')
        )
        
        return {
            'tokens': aggregates['total_tokens'] or 0,
            'cost_usd': float(aggregates['total_cost'] or 0),
            'requests': aggregates['request_count'] or 0,
            'date': start.date().isoformat(),
        }


class AIRateLimit(models.Model):
    """
    Per-user rate limiting and budget controls.
    
    Allows tiered access:
    - Free users: 10 requests/day, 5000 tokens
    - Premium users: 100 requests/day, 50000 tokens
    - Enterprise: Custom limits
    """
    
    TIER_CHOICES = (
        ('free', 'Free'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
        ('unlimited', 'Unlimited'),
    )
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_rate_limit'
    )
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='free')
    
    daily_request_limit = models.PositiveIntegerField(default=10)
    daily_token_limit = models.PositiveIntegerField(default=5000)
    daily_cost_limit_usd = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.50'))
    
    monthly_request_limit = models.PositiveIntegerField(default=200)
    monthly_token_limit = models.PositiveIntegerField(default=100000)
    monthly_cost_limit_usd = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('10.00'))
    
    is_blocked = models.BooleanField(default=False)
    block_reason = models.CharField(max_length=255, blank=True)
    blocked_until = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'AI Rate Limit'
        verbose_name_plural = 'AI Rate Limits'
    
    def __str__(self) -> str:
        return f"AIRateLimit({self.user}, {self.tier})"
    
    @classmethod
    def get_or_create_for_user(cls, user) -> 'AIRateLimit':
        """Get or create rate limit settings for a user."""
        limit, created = cls.objects.get_or_create(user=user)
        if created:
            # Set defaults based on user attributes
            if hasattr(user, 'is_premium') and user.is_premium:
                limit.tier = 'premium'
                limit.daily_request_limit = 100
                limit.daily_token_limit = 50000
                limit.daily_cost_limit_usd = Decimal('5.00')
                limit.save()
        return limit
    
    def check_daily_limit(self, estimated_tokens: int = 0) -> tuple[bool, str]:
        """
        Check if user can make another request.
        Returns (allowed, reason).
        """
        if self.is_blocked:
            if self.blocked_until and timezone.now() > self.blocked_until:
                self.is_blocked = False
                self.block_reason = ''
                self.blocked_until = None
                self.save(update_fields=['is_blocked', 'block_reason', 'blocked_until'])
            else:
                return False, self.block_reason or "Account temporarily blocked"
        
        usage = AIUsageRecord.get_user_daily_usage(self.user_id)
        
        if usage['requests'] >= self.daily_request_limit:
            return False, "Daily request limit reached"
        
        if usage['tokens'] + estimated_tokens > self.daily_token_limit:
            return False, "Daily token limit reached"
        
        if Decimal(str(usage['cost_usd'])) >= self.daily_cost_limit_usd:
            return False, "Daily cost limit reached"
        
        return True, ""
    
    def get_remaining_quota(self) -> Dict[str, Any]:
        """Get remaining daily quota."""
        usage = AIUsageRecord.get_user_daily_usage(self.user_id)
        return {
            'requests_remaining': max(0, self.daily_request_limit - usage['requests']),
            'tokens_remaining': max(0, self.daily_token_limit - usage['tokens']),
            'cost_remaining_usd': max(0, float(self.daily_cost_limit_usd) - usage['cost_usd']),
            'tier': self.tier,
        }


class ConversationMessage(models.Model):
    """
    Structured storage for conversation messages with token tracking.
    
    Enables:
    - Proper context window management
    - Message-level analytics
    - Efficient retrieval for AI context
    """
    
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        'SupportThread',
        on_delete=models.CASCADE,
        related_name='messages'
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    token_count = models.PositiveIntegerField(default=0)
    
    # AI metadata
    model_used = models.CharField(max_length=100, blank=True)
    prompt_name = models.CharField(max_length=100, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)
    
    # For user messages
    attachments = models.JSONField(default=list, blank=True)
    
    # For assistant messages
    usage_record = models.ForeignKey(
        AIUsageRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversation_messages'
    )
    
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['thread', 'created_at']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"Message({self.role}: {preview})"
    
    @classmethod
    def get_context_window(
        cls,
        thread_id: str,
        max_tokens: int = 4000,
        max_messages: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get recent messages that fit within token budget for AI context.
        Returns messages in chronological order.
        """
        messages = cls.objects.filter(
            thread_id=thread_id
        ).order_by('-created_at')[:max_messages * 2]  # Fetch extra to filter
        
        result = []
        total_tokens = 0
        
        for msg in reversed(list(messages)):
            if total_tokens + msg.token_count > max_tokens:
                break
            result.append({
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.created_at.isoformat(),
            })
            total_tokens += msg.token_count
        
        return result


class AITaskResult(models.Model):
    """
    Stores async AI task results for polling endpoints.
    
    Allows views to return immediately with a task_id,
    and clients poll for results.
    """
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ai_task_results'
    )
    
    task_id = models.CharField(max_length=255, unique=True)
    task_type = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    input_data = models.JSONField(default=dict)
    result_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    provider = models.CharField(max_length=50, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self) -> str:
        return f"AITask({self.task_type}, {self.status})"
    
    def mark_completed(self, result: Dict[str, Any], provider: str = '', latency_ms: int = 0, usage: Dict[str, Any] = None) -> None:
        """Mark task as completed with results."""
        self.status = 'completed'
        self.result_data = result
        self.provider = provider
        self.latency_ms = latency_ms
        self.usage = usage or {}
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self, error: str) -> None:
        """Mark task as failed with error message."""
        self.status = 'failed'
        self.error_message = error
        self.completed_at = timezone.now()
        self.save()
    
    @classmethod
    def cleanup_expired(cls) -> int:
        """Delete expired task results. Returns count deleted."""
        count, _ = cls.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()
        return count


class SupportThread(models.Model):
    """Represents a customer conversation that can be triaged by AI."""

    SOURCE_CHOICES = (
        ("contact_form", "Contact Form"),
        ("email", "Inbound Email"),
        ("booking", "Booking Flow"),
        ("deal", "Deal Lead"),
        ("chat", "Live Chat"),
    )

    CHANNEL_CHOICES = (
        ("email", "Email"),
        ("in_app", "In-App"),
        ("sms", "SMS"),
        ("web", "Web Form"),
    )

    PRIORITY_CHOICES = (
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    )

    STATUS_CHOICES = (
        ("new", "New"),
        ("triaged", "Triaged"),
        ("waiting", "Waiting On Customer"),
        ("in_progress", "In Progress"),
        ("auto_replied", "Auto Replied"),
        ("closed", "Closed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default="contact_form")
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="email")
    thread_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="External thread identifier or message-id"
    )

    customer_name = models.CharField(max_length=255, blank=True)
    customer_email = models.EmailField(blank=True)
    subject = models.CharField(max_length=255, blank=True)
    latest_customer_message = models.TextField(blank=True)
    raw_messages = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    intent_label = models.CharField(max_length=50, blank=True)
    sentiment_score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="normal")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    tags = models.JSONField(default=list, blank=True)

    ai_summary = models.TextField(blank=True)
    ai_suggested_reply = models.TextField(blank=True)
    ai_recommended_actions = models.JSONField(default=list, blank=True)
    deal_recommendations = models.JSONField(default=list, blank=True)
    booking_insights = models.JSONField(default=dict, blank=True)

    last_ai_provider = models.CharField(max_length=50, blank=True)
    last_ai_latency_ms = models.PositiveIntegerField(null=True, blank=True)
    last_ai_run_at = models.DateTimeField(null=True, blank=True)
    auto_reply_sent = models.BooleanField(default=False)

    related_booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_threads'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_support_threads'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['source', 'channel']),
            models.Index(fields=['customer_email']),
        ]

    def __str__(self) -> str:
        return f"SupportThread({self.customer_email or 'unknown'} - {self.subject or 'no-subject'})"

    # Convenience helpers -------------------------------------------------
    def add_message(self, sender: str, body: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Append a structured message to the conversation log."""

        payload = {
            'sender': sender,
            'body': body,
            'metadata': metadata or {},
            'timestamp': timezone.now().isoformat(),
        }
        messages = list(self.raw_messages or [])
        messages.append(payload)
        self.raw_messages = messages
        self.latest_customer_message = body

    def apply_triage_result(
        self,
        triage: Dict[str, Any],
        provider: Optional[str] = None,
        latency_ms: Optional[int] = None,
    ) -> None:
        """Persist AI triage insights onto the thread."""

        if not triage:
            return
        summary = triage.get('summary')
        suggested_reply = triage.get('suggested_reply') or triage.get('auto_reply')
        recommended_actions = triage.get('recommended_actions') or triage.get('actions')
        tags = triage.get('tags') or triage.get('labels')
        booking = triage.get('booking_context') or {}

        if summary:
            self.ai_summary = summary.strip()
        if suggested_reply:
            self.ai_suggested_reply = suggested_reply.strip()
        sequence_types = (list, tuple, set)
        if isinstance(recommended_actions, sequence_types):
            cleaned_actions = [str(action).strip() for action in recommended_actions if str(action).strip()]
            if cleaned_actions:
                self.ai_recommended_actions = cleaned_actions
        if isinstance(tags, sequence_types):
            self.tags = [str(tag).strip() for tag in tags if str(tag).strip()]
        if isinstance(booking, dict) and booking:
            self.booking_insights = booking

        self.intent_label = triage.get('intent', self.intent_label)
        self.priority = triage.get('priority', self.priority)
        sentiment = triage.get('sentiment_score') or triage.get('sentiment')
        if isinstance(sentiment, dict):
            self.sentiment_score = sentiment.get('score')
        elif isinstance(sentiment, (int, float, str)):
            try:
                self.sentiment_score = float(sentiment)
            except (TypeError, ValueError):
                pass

        if triage.get('status'):
            self.status = triage['status']
        elif self.status == 'new':
            self.status = 'triaged'

        if triage.get('deal_recommendations'):
            self.deal_recommendations = triage['deal_recommendations']

        if provider:
            self.last_ai_provider = provider
        if latency_ms is not None:
            self.last_ai_latency_ms = int(latency_ms)
            self.last_ai_run_at = timezone.now()

    def requires_follow_up(self) -> bool:
        return self.priority in {'high', 'urgent'} or self.status not in {'closed', 'auto_replied'}


class AIAssistantInsight(models.Model):
    """Stores AI generated insights for any object."""

    INSIGHT_TYPES = (
        ('support_triage', 'Support Triage'),
        ('booking_summary', 'Booking Summary'),
        ('deal_recommendation', 'Deal Recommendation'),
        ('automation', 'Automation'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        SupportThread,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='insights'
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    insight_type = models.CharField(max_length=40, choices=INSIGHT_TYPES)
    provider = models.CharField(max_length=50, blank=True)
    tokens_consumed = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_assistant_insights'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['insight_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self) -> str:
        label = self.title or self.get_insight_type_display()
        return f"AI Insight: {label}"
