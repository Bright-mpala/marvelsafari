from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Booking
from travel_booking.admin import admin_site


@admin.register(Booking, site=admin_site)
class BookingAdmin(admin.ModelAdmin):
    """Customized admin for managing bookings."""
    
    list_display = (
        'booking_id', 'user_email', 'property_name', 'check_in_date',
        'check_out_date', 'nights', 'total_amount', 'status_badge', 'created_at'
    )
    list_filter = (
        'status', 'check_in_date', 'check_out_date', 'created_at',
        'property__country', 'property__city'
    )
    search_fields = (
        'id', 'user__email', 'user__first_name', 'user__last_name',
        'property__name', 'property__city'
    )
    readonly_fields = ('booking_id', 'created_at', 'updated_at', 'nights_display')
    
    fieldsets = (
        (_('Booking Information'), {
            'fields': ('booking_id', 'user', 'property', 'status')
        }),
        (_('Guest Information'), {
            'fields': ('guests', 'special_requests')
        }),
        (_('Dates'), {
            'fields': ('check_in_date', 'check_out_date', 'nights_display')
        }),
        (_('Payment'), {
            'fields': ('price_per_night', 'total_amount')
        }),
        (_('Cancellation'), {
            'fields': ('cancellation_reason',),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def booking_id(self, obj):
        """Display booking ID."""
        return f"#{obj.id}"
    booking_id.short_description = _('Booking ID')
    
    def user_email(self, obj):
        """Display user email."""
        return obj.user.email
    user_email.short_description = _('User Email')
    user_email.admin_order_field = 'user__email'
    
    def property_name(self, obj):
        """Display property name."""
        return obj.property.name
    property_name.short_description = _('Property')
    property_name.admin_order_field = 'property__name'
    
    def nights(self, obj):
        """Display number of nights."""
        return obj.nights_count
    nights.short_description = _('Nights')
    
    def nights_display(self, obj):
        """Display nights count in readonly mode."""
        return obj.nights_count
    nights_display.short_description = _('Number of Nights')
    
    def status_badge(self, obj):
        """Display colored status badge."""
        colors = {
            'pending': '#FFA500',
            'confirmed': '#00AA00',
            'cancelled': '#FF0000',
            'completed': '#0000FF',
        }
        color = colors.get(obj.status, '#CCCCCC')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    status_badge.admin_order_field = 'status'
    
    actions = ['mark_confirmed', 'mark_cancelled', 'mark_completed']
    
    def mark_confirmed(self, request, queryset):
        """Mark selected bookings as confirmed."""
        updated = queryset.filter(status='pending').update(status='confirmed')
        self.message_user(request, _('%d booking(s) marked as confirmed.' % updated))
    mark_confirmed.short_description = _('Mark selected as Confirmed')
    
    def mark_cancelled(self, request, queryset):
        """Mark selected bookings as cancelled."""
        updated = queryset.exclude(status='completed').update(status='cancelled')
        self.message_user(request, _('%d booking(s) marked as cancelled.' % updated))
    mark_cancelled.short_description = _('Mark selected as Cancelled')
    
    def mark_completed(self, request, queryset):
        """Mark selected bookings as completed."""
        updated = queryset.filter(status='confirmed').update(status='completed')
        self.message_user(request, _('%d booking(s) marked as completed.' % updated))
    mark_completed.short_description = _('Mark selected as Completed')
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'property')
    
    class Media:
        css = {
            'all': ('admin/css/booking_admin.css',)
        }
