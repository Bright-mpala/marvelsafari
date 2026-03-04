from django.contrib import admin

from travel_booking.admin import admin_site

from .models import NewsletterCampaign, NewsletterSubscriber


@admin.register(NewsletterSubscriber, site=admin_site)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_active', 'subscribed_at')
    list_filter = ('is_active',)
    search_fields = ('email',)


@admin.register(NewsletterCampaign, site=admin_site)
class NewsletterCampaignAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'created_by', 'status', 'sent_at', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'subject', 'body', 'created_by__email')
