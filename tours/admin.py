from django.contrib import admin
from .models import TourCategory, TourOperator, Tour, TourImage, TourSchedule, TourBooking
from travel_booking.admin import admin_site

@admin.register(TourCategory, site=admin_site)
class TourCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')


@admin.register(TourOperator, site=admin_site)
class TourOperatorAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'is_verified', 'average_rating')
    list_filter = ('is_verified',)
    search_fields = ('name', 'phone', 'email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Tour, site=admin_site)
class TourAdmin(admin.ModelAdmin):
    list_display = ('name', 'operator', 'duration_days', 'base_price', 'is_active', 'average_rating')
    list_filter = ('is_active', 'country', 'difficulty')
    search_fields = ('name', 'operator__name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'booking_count')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(TourImage, site=admin_site)
class TourImageAdmin(admin.ModelAdmin):
    list_display = ('tour', 'image', 'caption', 'is_primary', 'display_order')
    list_filter = ('is_primary',)
    search_fields = ('tour__name', 'caption')


@admin.register(TourSchedule, site=admin_site)
class TourScheduleAdmin(admin.ModelAdmin):
    list_display = ('tour', 'date', 'start_time', 'end_time', 'total_spots', 'available_spots', 'is_available')
    list_filter = ('is_available', 'date')
    search_fields = ('tour__name', 'guide_name')
    date_hierarchy = 'date'


@admin.register(TourBooking, site=admin_site)
class TourBookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'tour_schedule', 'participant_count', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__email', 'tour_schedule__tour__name', 'id')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
