# urls.py

from django.urls import path, re_path
from . import views

app_name = 'car_rentals'

urlpatterns = [
    # Main listing (rental + taxi tabs)
    path('', views.car_list, name='car_list'),

    # User car submission
    path('list-your-car/', views.car_submission, name='car_submission'),
    path('list-your-car/success/', views.car_submission_success, name='car_submission_success'),

    # Car detail page
    path('<uuid:car_id>/', views.car_detail, name='car_detail'),

    # Rental booking
    path('book/<uuid:car_id>/', views.car_booking_create, name='car_booking_create'),
    
    # Booking confirmation - accept both UUID and reference string
    path('booking/<str:booking_id>/confirmation/', views.booking_confirmation, name='booking_confirmation'),

    # Taxi booking
    path('taxi/book/', views.taxi_booking_create, name='taxi_booking_create'),
    
    # Taxi confirmation - accept both UUID and reference string
    path('taxi/<str:booking_id>/confirmation/', views.taxi_confirmation, name='taxi_confirmation'),

    # My bookings
    path('my-bookings/', views.my_bookings, name='my_bookings'),

    # My listings dashboard
    path('my-cars/', views.my_listings, name='my_listings'),
    
    # Edit car listing
    path('<uuid:car_id>/edit/', views.car_edit, name='car_edit'),

    # Real-time tracking - accept both UUID and reference string
    path('track/<str:booking_id>/', views.track_car, name='track_car'),

    # Location APIs (JSON)
    path('api/car-location/<uuid:car_id>/', views.car_location_api, name='car_location_api'),
    path('api/driver-location/<int:driver_id>/', views.driver_location_api, name='driver_location_api'),

    # Driver review - accept both UUID and reference string
    path('bookings/<str:booking_id>/review-driver/', views.driver_review_create, name='driver_review_create'),
    path('bookings/<str:booking_id>/review-car/', views.car_review_create, name='car_review_create'),
]