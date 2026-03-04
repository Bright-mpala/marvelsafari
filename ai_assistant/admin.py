from django.contrib import admin
from django.utils.html import format_html
from .models import (
    SupportThread, 
    AIAssistantInsight, 
    AIUsageRecord, 
    AIRateLimit, 
    AITaskResult,
    ConversationMessage,
)


@admin.register(SupportThread)
class SupportThreadAdmin(admin.ModelAdmin):
    list_display = (
        'customer_email',
        'subject',
        'priority',
        'status',
        'intent_label',
        'last_ai_provider',
        'updated_at',
    )
    list_filter = (
        'status',
        'priority',
        'intent_label',
        'source',
        'channel',
        'auto_reply_sent',
    )
    search_fields = ('customer_email', 'subject', 'latest_customer_message', 'thread_key')
    readonly_fields = (
        'created_at',
        'updated_at',
        'raw_messages',
        'ai_summary',
        'ai_suggested_reply',
        'ai_recommended_actions',
        'deal_recommendations',
        'booking_insights',
        'last_ai_provider',
        'last_ai_latency_ms',
        'last_ai_run_at',
    )
    fieldsets = (
        ('Conversation', {
            'fields': ('source', 'channel', 'status', 'priority', 'thread_key', 'related_booking', 'assigned_to')
        }),
        ('Customer', {
            'fields': ('customer_name', 'customer_email', 'subject', 'latest_customer_message', 'raw_messages')
        }),
        ('AI Insights', {
            'fields': (
                'intent_label',
                'sentiment_score',
                'ai_summary',
                'ai_suggested_reply',
                'ai_recommended_actions',
                'deal_recommendations',
                'booking_insights',
                'tags',
                'last_ai_provider',
                'last_ai_latency_ms',
                'last_ai_run_at',
            )
        }),
        ('Meta', {'fields': ('auto_reply_sent', 'metadata', 'created_at', 'updated_at')}),
    )


@admin.register(AIAssistantInsight)
class AIAssistantInsightAdmin(admin.ModelAdmin):
    list_display = ('title', 'insight_type', 'provider', 'created_at')
    list_filter = ('insight_type', 'provider')
    search_fields = ('title', 'body')
    readonly_fields = ('created_at', )


@admin.register(AIUsageRecord)
class AIUsageRecordAdmin(admin.ModelAdmin):
    """Admin for AI usage tracking and cost monitoring."""
    
    list_display = (
        'operation',
        'user',
        'provider',
        'model',
        'total_tokens',
        'formatted_cost',
        'latency_ms',
        'success',
        'created_at',
    )
    list_filter = (
        'provider',
        'model',
        'operation',
        'success',
        'created_at',
    )
    search_fields = ('user__email', 'operation', 'prompt_name')
    readonly_fields = (
        'id',
        'user',
        'provider',
        'model',
        'operation',
        'prompt_name',
        'prompt_version',
        'prompt_tokens',
        'completion_tokens',
        'total_tokens',
        'prompt_cost_usd',
        'completion_cost_usd',
        'total_cost_usd',
        'latency_ms',
        'success',
        'error_type',
        'request_metadata',
        'created_at',
    )
    date_hierarchy = 'created_at'
    
    def formatted_cost(self, obj):
        return format_html('<span style="color: {};">${:.4f}</span>',
                          'green' if obj.total_cost_usd < 0.01 else 'orange',
                          obj.total_cost_usd)
    formatted_cost.short_description = 'Cost (USD)'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AIRateLimit)
class AIRateLimitAdmin(admin.ModelAdmin):
    """Admin for per-user AI rate limits."""
    
    list_display = (
        'user',
        'tier',
        'daily_request_limit',
        'daily_token_limit',
        'daily_cost_limit_usd',
        'is_blocked',
        'updated_at',
    )
    list_filter = ('tier', 'is_blocked')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('User', {'fields': ('user', 'tier')}),
        ('Daily Limits', {
            'fields': ('daily_request_limit', 'daily_token_limit', 'daily_cost_limit_usd')
        }),
        ('Monthly Limits', {
            'fields': ('monthly_request_limit', 'monthly_token_limit', 'monthly_cost_limit_usd')
        }),
        ('Blocking', {
            'fields': ('is_blocked', 'block_reason', 'blocked_until')
        }),
        ('Meta', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(AITaskResult)
class AITaskResultAdmin(admin.ModelAdmin):
    """Admin for async AI task results."""
    
    list_display = (
        'task_id',
        'task_type',
        'status',
        'user',
        'provider',
        'latency_ms',
        'created_at',
        'completed_at',
    )
    list_filter = ('status', 'task_type', 'provider')
    search_fields = ('task_id', 'user__email', 'task_type')
    readonly_fields = (
        'id',
        'task_id',
        'task_type',
        'status',
        'user',
        'input_data',
        'result_data',
        'error_message',
        'provider',
        'latency_ms',
        'usage',
        'created_at',
        'completed_at',
        'expires_at',
    )
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False


@admin.register(ConversationMessage)
class ConversationMessageAdmin(admin.ModelAdmin):
    """Admin for conversation messages."""
    
    list_display = (
        'thread',
        'role',
        'content_preview',
        'token_count',
        'model_used',
        'created_at',
    )
    list_filter = ('role', 'model_used')
    search_fields = ('content', 'thread__customer_email')
    readonly_fields = (
        'id',
        'thread',
        'role',
        'content',
        'token_count',
        'model_used',
        'prompt_name',
        'latency_ms',
        'confidence_score',
        'attachments',
        'usage_record',
        'metadata',
        'created_at',
    )
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'
    
    def has_add_permission(self, request):
        return False
