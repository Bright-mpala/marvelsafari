from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from accounts.permissions import HasBookingPermission, IsEmailVerified
from properties.models import Property
from bookings.models import Booking
from .serializers import PropertySerializer, BookingSerializer

class PropertyViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for properties."""
    queryset = Property.objects.filter(status='active')
    serializer_class = PropertySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

class BookingViewSet(viewsets.ModelViewSet):
    """API endpoint for bookings."""
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [IsEmailVerified, HasBookingPermission]

    def get_queryset(self):
        """Filter bookings by user."""
        if self.request.user.is_authenticated:
            if self.request.user.is_staff or self.request.user.is_superuser:
                return Booking.objects.all()
            return Booking.objects.filter(user=self.request.user)
        return Booking.objects.none()

    def perform_create(self, serializer):
        """Force booking ownership to the authenticated user."""
        serializer.save(user=self.request.user)
