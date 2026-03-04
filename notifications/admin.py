from django.contrib import admin
from .models import (
    NotificationType, Notification, UserNotificationPreference,
    EmailTemplate, SMSLog, PushNotificationDevice
)
from travel_booking.admin import admin_site

@admin.register(NotificationType, site=admin_site)
class NotificationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')


@admin.register(Notification, site=admin_site)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'subject', 'is_read', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__email', 'subject', 'message')
    readonly_fields = ('created_at', 'read_at')
    date_hierarchy = 'created_at'


@admin.register(UserNotificationPreference, site=admin_site)
class UserNotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'email_enabled', 'sms_enabled', 'push_enabled')
    list_filter = ('email_enabled', 'sms_enabled', 'push_enabled')
    search_fields = ('user__email', 'notification_type__name')


@admin.register(EmailTemplate, site=admin_site)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'subject')


@admin.register(SMSLog, site=admin_site)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ('notification', 'phone_number', 'message', 'delivered', 'delivery_timestamp')
    list_filter = ('delivered',)
    search_fields = ('notification__user__email', 'phone_number', 'message')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PushNotificationDevice, site=admin_site)
class PushNotificationDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_type', 'device_token', 'is_active', 'created_at')
    list_filter = ('device_type', 'is_active', 'created_at')
    search_fields = ('user__email', 'device_token')
