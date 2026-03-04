from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    # Booking management
    path('', views.booking_list, name='list'),
    # Use UUID primary keys for bookings (inherited from BaseModel)
    path('<uuid:pk>/', views.booking_detail, name='detail'),
    path('create/<str:property_id>/', views.booking_create, name='create'),
    path('<uuid:pk>/cancel/', views.booking_cancel, name='cancel'),
]