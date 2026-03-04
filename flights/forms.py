from django import forms
from .models import FlightBooking


class FlightBookingForm(forms.ModelForm):
    class Meta:
        model = FlightBooking
        fields = [
            'flight_schedule',
            'fare',
            'passenger_count',
        ]
        widgets = {
            'passenger_count': forms.NumberInput(attrs={'min': 1}),
        }
