from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class NotificationType(models.Model):
    """Notification type templates."""
    
    NOTIFICATION_CHANNELS = (
        ('email', _('Email')),
        ('sms', _('SMS')),
        ('push', _('Push Notification')),
        ('in_app', _('In-App Notification')),
        ('webhook', _('Webhook')),
    )
    
    name = models.CharField(_('notification type'), max_length=100)
    code = models.CharField(_('code'), max_length=50, unique=True)
    description = models.TextField(_('description'), blank=True)
    
    # Channels
    channels = models.JSONField(
        _('channels'),
        default=list,
        help_text=_('List of channels for this notification type')
    )
    
    # Templates
    email_subject = models.CharField(_('email subject'), max_length=255, blank=True)
    email_template = models.TextField(_('email template'), blank=True)
    sms_template = models.TextField(_('SMS template'), blank=True)
    push_template = models.TextField(_('push template'), blank=True)
    in_app_template = models.TextField(_('in-app template'), blank=True)
    
    # Settings
    is_active = models.BooleanField(_('active'), default=True)
    is_required = models.BooleanField(
        _('required'),
        default=False,
        help_text=_('Cannot be disabled by user')
    )
    
    # Priority
    priority = models.PositiveSmallIntegerField(
        _('priority'),
        default=1,
        help_text=_('Higher number = higher priority')
    )
    
    # User preferences default
    default_enabled = models.BooleanField(_('enabled by default'), default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    class Meta:
        verbose_name = _('notification type')
        verbose_name_plural = _('notification types')
        ordering = ['priority', 'code']


class Notification(models.Model):
    """Sent notifications."""
    
    NOTIFICATION_STATUS = (
        ('pending', _('Pending')),
        ('sending', _('Sending')),
        ('sent', _('Sent')),
        ('delivered', _('Delivered')),
        ('read', _('Read')),
        ('failed', _('Failed')),
        ('bounced', _('Bounced')),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Recipient
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Notification details
    notification_type = models.ForeignKey(
        NotificationType,
        on_delete=models.PROTECT,
        related_name='notifications'
    )
    channel = models.CharField(
        _('channel'),
        max_length=20,
        choices=NotificationType.NOTIFICATION_CHANNELS
    )
    
    # Content
    subject = models.CharField(_('subject'), max_length=255, blank=True)
    message = models.TextField(_('message'))
    
    # Context
    context = models.JSONField(
        _('context'),
        default=dict,
        blank=True,
        help_text=_('Context data used to render the notification')
    )
    
    # Related objects
    related_booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    related_flight_booking = models.ForeignKey(
        'flights.FlightBooking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    related_car_rental_booking = models.ForeignKey(
        'car_rentals.CarRentalBooking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    related_tour_booking = models.ForeignKey(
        'tours.TourBooking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=NOTIFICATION_STATUS,
        default='pending'
    )
    
    # Delivery info
    delivery_attempts = models.PositiveSmallIntegerField(_('delivery attempts'), default=0)
    last_attempt_at = models.DateTimeField(_('last attempt at'), null=True, blank=True)
    
    # Error info
    error_message = models.TextField(_('error message'), blank=True)
    error_code = models.CharField(_('error code'), max_length=100, blank=True)
    
    # Metadata
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(_('sent at'), null=True, blank=True)
    delivered_at = models.DateTimeField(_('delivered at'), null=True, blank=True)
    read_at = models.DateTimeField(_('read at'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('notification')
        verbose_name_plural = _('notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status', 'created_at']),
            models.Index(fields=['channel', 'status']),
        ]
    
    def __str__(self):
        return f"Notification to {self.user.email} - {self.get_channel_display()} - {self.status}"
    
    @property
    def is_read(self):
        return self.read_at is not None


class UserNotificationPreference(models.Model):
    """User notification preferences."""
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    notification_type = models.ForeignKey(
        NotificationType,
        on_delete=models.CASCADE,
        related_name='user_preferences'
    )
    
    # Channel preferences
    email_enabled = models.BooleanField(_('email enabled'), default=True)
    sms_enabled = models.BooleanField(_('SMS enabled'), default=True)
    push_enabled = models.BooleanField(_('push enabled'), default=True)
    in_app_enabled = models.BooleanField(_('in-app enabled'), default=True)
    
    # Frequency (for digest notifications)
    frequency = models.CharField(
        _('frequency'),
        max_length=20,
        default='immediate',
        choices=[
            ('immediate', _('Immediate')),
            ('daily', _('Daily Digest')),
            ('weekly', _('Weekly Digest')),
            ('disabled', _('Disabled')),
        ]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('user notification preference')
        verbose_name_plural = _('user notification preferences')
        unique_together = ['user', 'notification_type']
    
    def __str__(self):
        return f"{self.user.email} - {self.notification_type.code}"


class EmailTemplate(models.Model):
    """Email templates for notifications."""
    
    TEMPLATE_TYPES = (
        ('booking_confirmation', _('Booking Confirmation')),
        ('booking_reminder', _('Booking Reminder')),
        ('booking_cancellation', _('Booking Cancellation')),
        ('payment_receipt', _('Payment Receipt')),
        ('password_reset', _('Password Reset')),
        ('welcome', _('Welcome Email')),
        ('promotional', _('Promotional')),
        ('review_reminder', _('Review Reminder')),
        ('security_alert', _('Security Alert')),
    )
    
    name = models.CharField(_('template name'), max_length=100)
    template_type = models.CharField(
        _('template type'),
        max_length=50,
        choices=TEMPLATE_TYPES
    )
    language = models.CharField(_('language'), max_length=10, default='en')
    
    # Content
    subject = models.CharField(_('subject'), max_length=255)
    html_content = models.TextField(_('HTML content'))
    plain_text_content = models.TextField(_('plain text content'), blank=True)
    
    # Variables
    variables = models.JSONField(
        _('variables'),
        default=list,
        help_text=_('List of available template variables')
    )
    
    # Settings
    is_active = models.BooleanField(_('active'), default=True)
    is_default = models.BooleanField(_('default'), default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()}) - {self.language}"
    
    class Meta:
        verbose_name = _('email template')
        verbose_name_plural = _('email templates')
        unique_together = ['template_type', 'language']
        ordering = ['template_type', 'language']


class SMSLog(models.Model):
    """SMS sending log."""
    
    notification = models.OneToOneField(
        Notification,
        on_delete=models.CASCADE,
        related_name='sms_log'
    )
    
    # SMS details
    phone_number = models.CharField(_('phone number'), max_length=50)
    message = models.TextField(_('message'))
    message_id = models.CharField(_('message ID'), max_length=255, blank=True)
    
    # Provider
    provider = models.CharField(_('provider'), max_length=100, blank=True)
    provider_response = models.JSONField(
        _('provider response'),
        default=dict,
        blank=True
    )
    
    # Cost
    cost = models.DecimalField(_('cost'), max_digits=8, decimal_places=4, default=0)
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    
    # Delivery
    delivered = models.BooleanField(_('delivered'), default=False)
    delivery_timestamp = models.DateTimeField(_('delivery timestamp'), null=True, blank=True)
    
    # Error
    error_code = models.CharField(_('error code'), max_length=100, blank=True)
    error_message = models.TextField(_('error message'), blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"SMS to {self.phone_number} - {self.notification_id}"
    
    class Meta:
        verbose_name = _('SMS log')
        verbose_name_plural = _('SMS logs')


class PushNotificationDevice(models.Model):
    """Push notification devices."""
    
    DEVICE_TYPES = (
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web'),
    )
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='push_devices'
    )
    
    # Device info
    device_type = models.CharField(_('device type'), max_length=20, choices=DEVICE_TYPES)
    device_token = models.CharField(_('device token'), max_length=255, unique=True)
    device_id = models.CharField(_('device ID'), max_length=255, blank=True)
    
    # App info
    app_version = models.CharField(_('app version'), max_length=50, blank=True)
    os_version = models.CharField(_('OS version'), max_length=50, blank=True)
    
    # Status
    is_active = models.BooleanField(_('active'), default=True)
    last_active = models.DateTimeField(_('last active'), auto_now=True)
    
    # Metadata
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.get_device_type_display()}"
    
    class Meta:
        verbose_name = _('push notification device')
        verbose_name_plural = _('push notification devices')
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]