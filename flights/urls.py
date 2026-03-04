from django.urls import path
from . import views

app_name = 'flights'

urlpatterns = [
    path('', views.flight_list, name='flight_list'),
    path('book/<int:flight_id>/', views.flight_booking_create, name='flight_booking_create'),
]