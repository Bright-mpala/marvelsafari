"""
URL configuration for travel_booking project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static
from .admin import admin_site
from properties.views import PropertyListView

urlpatterns = [
    # Health checks & core pages
    path('', include('core.urls')),
    
    # Admin interface (rebranded path)
    path('marvel.safari-essence.admin/', admin_site.urls),
    path('admin/', RedirectView.as_view(url='/marvel.safari-essence.admin/', permanent=False)),
    
    # Home page - show properties list
    path('', PropertyListView.as_view(), name='home'),

    # Redirect legacy allauth paths to custom auth routes
    path('accounts/signup/', RedirectView.as_view(url='/auth/register/', permanent=False)),
    path('accounts/login/', RedirectView.as_view(url='/auth/login/', permanent=False)),
    path('accounts/logout/', RedirectView.as_view(url='/auth/logout/', permanent=False)),
    path('accounts/', include('allauth.urls')),
    # Core functionality
    path('properties/', include('properties.urls')),
    path('bookings/', include('bookings.urls')),
    path('auth/', include('accounts.urls')),
    
    # API endpoints
    path('api/v1/', include(('api.urls', 'api'), namespace='api_v1')),
    
    # Additional features (can be disabled if not needed)
    path('flights/', include('flights.urls')),
    path('cars/', include('car_rentals.urls')),
    path('tours/', include('tours.urls')),
    path('reviews/', include('reviews.urls')),
    path('business/', include('business.urls')),
    path('payments/', include('payments.urls')),
    path('analytics/', include('analytics.urls')),
    path('notifications/', include('notifications.urls')),
    path('newsletter/', include('newsletter.urls')),
    path('blog/', include('blog.urls')),
    path('ai/', include(('ai_assistant.urls', 'ai_assistant'), namespace='ai')),
]

# Serve media and static files in development
# NOTE: Django's static() returns [] when DEBUG=False, so we use re_path directly
if settings.DEBUG or getattr(settings, 'ENVIRONMENT', '') == 'development':
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]
    # urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]

# Custom error handlers
handler400 = 'travel_booking.views.custom_400'
handler403 = 'travel_booking.views.custom_403'
handler404 = 'travel_booking.views.custom_404'
handler500 = 'travel_booking.views.custom_500'
