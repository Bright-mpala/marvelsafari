"""Core models for sharing across services"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from taggit.models import TaggedItemBase
import uuid


class BaseModel(models.Model):
    """Abstract base model that adds timestamps and activation flag."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    is_active = models.BooleanField(_('active'), default=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class SoftDeletableModel(BaseModel):
    """
    Abstract model with soft delete capability.
    
    Items are never permanently deleted, only marked as deleted.
    This is important for:
    - Audit trails
    - Referential integrity
    - Historical queries
    """
    
    is_deleted = models.BooleanField(_('deleted'), default=False, db_index=True)
    deleted_at = models.DateTimeField(_('deleted at'), null=True, blank=True)
    deleted_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_soft_deleted'
    )
    
    class Meta:
        abstract = True
    
    def soft_delete(self, user=None):
        """Mark as deleted without actually removing from database"""
        from django.utils import timezone
        self.is_deleted = True
        self.is_active = False
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save()
    
    def restore(self):
        """Restore a soft-deleted item"""
        self.is_deleted = False
        self.is_active = True
        self.deleted_at = None
        self.deleted_by = None
        self.save()


class AuditLogEntry(BaseModel):
    """Audit trail for all significant operations"""
    
    ACTION_CHOICES = (
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('restore', 'Restore'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('cancel', 'Cancel'),
        ('complete', 'Complete'),
        ('other', 'Other'),
    )
    
    user = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    content_type = models.CharField(_('content type'), max_length=255)
    object_id = models.UUIDField(_('object ID'))
    object_repr = models.CharField(_('object representation'), max_length=500)
    action = models.CharField(_('action'), max_length=20, choices=ACTION_CHOICES)
    changes = models.JSONField(_('changes'), default=dict)
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.TextField(_('user agent'), blank=True)
    request_id = models.CharField(_('request ID'), max_length=36, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['object_id', 'action']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['content_type', 'created_at']),
        ]
        verbose_name = _('audit log entry')
        verbose_name_plural = _('audit log entries')
    
    def __str__(self):
        return f"{self.action} {self.object_repr} by {self.user} at {self.created_at}"


class UUIDTaggedItem(TaggedItemBase):
    """Taggit through model that stores UUID primary keys."""

    object_id = models.UUIDField(db_index=True)

    class Meta:
        verbose_name = _('tagged item')
        verbose_name_plural = _('tagged items')
