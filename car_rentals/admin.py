from django.contrib import admin, messages
from .models import (
    CarCategory, CarRentalCompany, RentalLocation, Car, CarImage,
    RentalRate, CarRentalBooking, RentalDamageReport, CarDriver,
    CarDriverReview, CarRentalReview, TaxiBooking, CarLocationTracker,
    CarStatus, OperationalStatus,
)
from travel_booking.admin import admin_site


@admin.register(CarCategory, site=admin_site)
class CarCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'passenger_capacity', 'transmission', 'fuel_type', 'is_active')
    search_fields = ('name', 'description')
    list_filter = ('fuel_type', 'transmission', 'is_active')


@admin.register(CarRentalCompany, site=admin_site)
class CarRentalCompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'offers_rental', 'offers_taxi', 'is_active', 'customer_rating')
    list_filter = ('is_active', 'offers_rental', 'offers_taxi', 'country')
    search_fields = ('name', 'phone', 'email')


@admin.register(RentalLocation, site=admin_site)
class RentalLocationAdmin(admin.ModelAdmin):
    list_display = ('company', 'name', 'city', 'location_type', 'country', 'supports_taxi_pickup', 'is_active')
    list_filter = ('country', 'location_type', 'supports_taxi_pickup', 'is_active')
    search_fields = ('name', 'city', 'company__name')


class CarImageInline(admin.TabularInline):
    model = CarImage
    extra = 1
    fields = ('image', 'caption', 'is_primary', 'display_order')


@admin.register(Car, site=admin_site)
class CarAdmin(admin.ModelAdmin):
    list_display = ('make', 'model', 'company', 'year', 'service_type', 'usage_function', 'license_plate', 'status', 'moderation_status', 'average_rating', 'is_featured')
    list_filter = ('company', 'category', 'service_type', 'usage_function', 'status', 'is_featured', 'has_ac', 'has_gps', 'moderation_status')
    search_fields = ('make', 'model', 'license_plate', 'company__name')
    readonly_fields = ('average_rating', 'review_count', 'slug')
    inlines = [CarImageInline]
    actions = ['approve_selected_listings']
    fieldsets = (
        ('Basic Info', {
            'fields': ('company', 'category', 'make', 'model', 'year', 'license_plate', 'color', 'featured_image', 'is_featured', 'slug')
        }),
        ('Service Type', {
            'fields': ('service_type', 'usage_function')
        }),
        ('Specifications', {
            'fields': ('doors', 'seats', 'engine_capacity', 'fuel_consumption')
        }),
        ('Features', {
            'fields': ('has_ac', 'has_gps', 'has_bluetooth', 'has_usb', 'has_child_seat', 'has_wifi', 'has_dashcam')
        }),
        ('Taxi Pricing', {
            'fields': ('taxi_base_fare', 'taxi_rate_per_km', 'taxi_per_hour'),
            'classes': ('collapse',),
        }),
        ('Status & Location', {
            'fields': ('status', 'moderation_status', 'current_location', 'current_latitude', 'current_longitude', 'location_updated_at', 'mileage', 'average_rating', 'review_count')
        }),
    )

    @admin.action(description='Approve selected listings')
    def approve_selected_listings(self, request, queryset):
        updated = 0
        for car in queryset:
            if car.moderation_status == CarStatus.APPROVED:
                continue
            car.moderation_status = CarStatus.APPROVED
            car.status = OperationalStatus.AVAILABLE
            car.save(update_fields=['moderation_status', 'status'])
            updated += 1
        if updated:
            self.message_user(request, f"Approved {updated} car(s) and notified owners.", messages.SUCCESS)
        else:
            self.message_user(request, "Selected cars were already approved.", messages.INFO)


@admin.register(CarImage, site=admin_site)
class CarImageAdmin(admin.ModelAdmin):
    list_display = ('car', 'caption', 'is_primary', 'display_order')
    list_filter = ('is_primary',)


@admin.register(CarDriver, site=admin_site)
class CarDriverAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'company', 'is_active', 'is_available', 'average_rating', 'review_count')
    list_filter = ('is_active', 'is_available', 'company')
    search_fields = ('full_name', 'email', 'license_number', 'company__name')
    filter_horizontal = ('cars',)


@admin.register(RentalRate, site=admin_site)
class RentalRateAdmin(admin.ModelAdmin):
    list_display = ('category', 'daily_rate', 'weekly_rate', 'monthly_rate', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('category__name', 'company__name')


@admin.register(CarRentalBooking, site=admin_site)
class CarRentalBookingAdmin(admin.ModelAdmin):
    list_display = ('booking_reference', 'user', 'car', 'pickup_date', 'dropoff_date', 'total_amount', 'status')
    list_filter = ('status', 'payment_status', 'pickup_date', 'dropoff_date')
    search_fields = ('booking_reference', 'user__email', 'car__model')
    readonly_fields = ('created_at', 'updated_at', 'booking_reference')
    date_hierarchy = 'pickup_date'


@admin.register(TaxiBooking, site=admin_site)
class TaxiBookingAdmin(admin.ModelAdmin):
    list_display = ('booking_reference', 'user', 'trip_type', 'pickup_datetime', 'total_fare', 'status')
    list_filter = ('status', 'trip_type', 'payment_status')
    search_fields = ('booking_reference', 'user__email', 'passenger_name')
    readonly_fields = ('created_at', 'updated_at', 'booking_reference')
    date_hierarchy = 'pickup_datetime'


@admin.register(CarLocationTracker, site=admin_site)
class CarLocationTrackerAdmin(admin.ModelAdmin):
    list_display = ('car', 'latitude', 'longitude', 'speed_kmh', 'recorded_at')
    list_filter = ('car',)
    readonly_fields = ('recorded_at',)


@admin.register(RentalDamageReport, site=admin_site)
class RentalDamageReportAdmin(admin.ModelAdmin):
    list_display = ('booking', 'reported_by', 'repair_cost', 'status')
    list_filter = ('status',)
    search_fields = ('booking__user__email', 'damage_description')


@admin.register(CarDriverReview, site=admin_site)
class CarDriverReviewAdmin(admin.ModelAdmin):
    list_display = ('driver', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('driver__full_name', 'user__email', 'feedback')


@admin.register(CarRentalReview, site=admin_site)
class CarRentalReviewAdmin(admin.ModelAdmin):
    list_display = ('car', 'user', 'rating', 'available_after', 'created_at')
    list_filter = ('rating', 'available_after')
    search_fields = ('car__make', 'car__model', 'user__email', 'feedback')
