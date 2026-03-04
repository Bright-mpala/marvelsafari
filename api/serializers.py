from rest_framework import serializers
from properties.models import Property
from bookings.models import Booking

class PropertySerializer(serializers.ModelSerializer):
    """Serializer for Property model."""
    
    class Meta:
        model = Property
        fields = [
            'id', 'name', 'slug', 'description', 'property_type', 
            'star_rating', 'address', 'city', 'state', 'postal_code', 
            'country', 'latitude', 'longitude', 'phone', 'email', 
            'website', 'check_in_time', 'check_out_time', 'status'
        ]

class BookingSerializer(serializers.ModelSerializer):
    """Serializer for Booking model."""
    
    class Meta:
        model = Booking
        fields = '__all__'