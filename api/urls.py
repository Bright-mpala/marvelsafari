from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'properties', views.PropertyViewSet)
router.register(r'bookings', views.BookingViewSet)

app_name = 'api'

urlpatterns = [
    path('', include(router.urls)),
]