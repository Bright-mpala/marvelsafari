"""Admin configuration for core app"""

from django.contrib import admin
from .models import AuditLogEntry


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    """Admin interface for audit log entries"""
    
    list_display = ['created_at', 'action', 'user', 'content_type', 'object_repr']
    list_filter = ['action', 'content_type', 'created_at']
    search_fields = ['object_repr', 'object_id', 'user__email']
    readonly_fields = ['created_at', 'updated_at', 'id']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Action', {
            'fields': ('action', 'user', 'created_at', 'updated_at')
        }),
        ('Target', {
            'fields': ('content_type', 'object_id', 'object_repr')
        }),
        ('Changes', {
            'fields': ('changes',),
            'classes': ('collapse',)
        }),
        ('Request Info', {
            'fields': ('ip_address', 'user_agent', 'request_id'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
