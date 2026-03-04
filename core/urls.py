"""Core app URL patterns - health checks and monitoring"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Health checks for orchestration
    path('health/live', views.health_check_live, name='health_live'),
    path('health/ready', views.health_check_ready, name='health_ready'),
    path('health/deep', views.health_check_deep, name='health_deep'),
    path('health/', views.health_check_ready, name='health'),
    
    # Static pages
    path('contact/', views.contact_us, name='contact'),
    path('about/', views.about_us, name='about'),
    path('privacy/', views.privacy_policy, name='privacy'),
    path('terms/', views.terms_of_service, name='terms'),
    path('cookies/', views.cookie_policy, name='cookies'),
    path('accessibility/', views.accessibility, name='accessibility'),
    path('careers/', views.careers, name='careers'),
    path('press/', views.press, name='press'),
    path('sustainability/', views.sustainability, name='sustainability'),
    path('help/', views.help_center, name='help'),
    path('faq/', views.faq, name='faq'),
]
