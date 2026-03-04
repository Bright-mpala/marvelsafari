from django import forms
from .models import TourBooking


class TourBookingForm(forms.ModelForm):
    class Meta:
        model = TourBooking
        fields = [
            'tour',
            'tour_schedule',
            'participant_count',
            'contact_name',
            'contact_email',
            'contact_phone',
        ]
        widgets = {
            'participant_count': forms.NumberInput(attrs={'min': 1}),
        }
