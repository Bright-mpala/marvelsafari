from django.urls import path
from . import views

app_name = 'tours'

urlpatterns = [
    path('', views.tour_list, name='tour_list'),
    path('book/<uuid:tour_id>/', views.tour_booking_create, name='tour_booking_create'),
]