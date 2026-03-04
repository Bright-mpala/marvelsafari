"""URL routes for AI-powered endpoints."""

from django.urls import path

from . import views

app_name = 'ai_assistant'

urlpatterns = [
    # Task status polling
    path('tasks/<str:task_id>/', views.AITaskStatusView.as_view(), name='task_status'),
    
    # Usage stats
    path('usage/', views.AIUsageStatsView.as_view(), name='usage_stats'),
    
    # AI endpoints
    path('support/chatbot/ask/', views.SupportChatbotPageView.as_view(), name='support_chatbot_page'),
    path('support/chatbot/', views.SupportChatbotView.as_view(), name='support_chatbot'),
    path('itineraries/generate/', views.ItineraryGeneratorView.as_view(), name='generate_itinerary'),
    path('destinations/recommend/', views.DestinationRecommendationView.as_view(), name='recommend_destinations'),
    path('seo/generate/', views.SEOContentGeneratorView.as_view(), name='generate_seo'),
]
