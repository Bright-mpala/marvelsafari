from django.contrib import admin
from .models import Review, ReviewImage, ReviewHelpful, ReviewReport
from travel_booking.admin import admin_site

@admin.register(Review, site=admin_site)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'property', 'overall_rating', 'is_verified', 'is_featured', 'created_at')
    list_filter = ('overall_rating', 'is_verified', 'is_featured', 'created_at')
    search_fields = ('user__email', 'property__name', 'title', 'comment')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(ReviewImage, site=admin_site)
class ReviewImageAdmin(admin.ModelAdmin):
    list_display = ('review', 'image', 'caption', 'is_primary')
    list_filter = ('review__property',)
    search_fields = ('review__user__email', 'caption')


@admin.register(ReviewHelpful, site=admin_site)
class ReviewHelpfulAdmin(admin.ModelAdmin):
    list_display = ('user', 'review', 'is_helpful', 'created_at')
    list_filter = ('is_helpful', 'created_at')
    search_fields = ('user__email', 'review__property__name')


@admin.register(ReviewReport, site=admin_site)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = ('review', 'reported_by', 'reason', 'status', 'created_at')
    list_filter = ('reason', 'status', 'created_at')
    search_fields = ('review__user__email', 'reported_by__email', 'description')
    readonly_fields = ('created_at',)
