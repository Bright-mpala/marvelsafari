from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Booking
from datetime import timedelta


class BookingForm(forms.ModelForm):
    """Form for creating and updating bookings with comprehensive validation."""

    class Meta:
        model = Booking
        fields = ['check_in_date', 'check_out_date', 'guests', 'special_requests']
        widgets = {
            'check_in_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': timezone.now().date().isoformat(),
                'required': 'required',
            }),
            'check_out_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'required': 'required',
            }),
            'guests': forms.NumberInput(attrs={
                'min': 1,
                'max': 10,
                'class': 'form-control',
                'placeholder': _('Number of guests'),
                'required': 'required',
            }),
            'special_requests': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Any special requests or preferences (optional)'),
            }),
        }
        labels = {
            'check_in_date': _('Check-in Date'),
            'check_out_date': _('Check-out Date'),
            'guests': _('Number of Guests'),
            'special_requests': _('Special Requests'),
        }
        help_texts = {
            'guests': _('Maximum 10 guests per booking'),
            'special_requests': _('Optional - let the host know about any special needs'),
        }

    def clean(self):
        """Comprehensive validation for booking form."""
        cleaned_data = super().clean()
        check_in_date = cleaned_data.get('check_in_date')
        check_out_date = cleaned_data.get('check_out_date')
        guests = cleaned_data.get('guests')

        # Validate dates
        if check_in_date and check_out_date:
            today = timezone.now().date()
            
            # Check-in cannot be in the past
            if check_in_date < today:
                self.add_error('check_in_date', _('Check-in date must be today or in the future.'))
            
            # Check-out must be after check-in
            if check_out_date <= check_in_date:
                self.add_error('check_out_date', _('Check-out date must be after check-in date.'))
            else:
                # Minimum stay requirement (at least 1 night)
                nights = (check_out_date - check_in_date).days
                if nights < 1:
                    self.add_error('check_out_date', _('Minimum stay is 1 night.'))
                
                # Maximum booking length (365 days)
                if nights > 365:
                    self.add_error('check_out_date', _('Maximum stay is 365 nights.'))
        
        # Validate guests
        if guests:
            if guests < 1 or guests > 10:
                self.add_error('guests', _('Number of guests must be between 1 and 10.'))

        return cleaned_data

    def clean_check_in_date(self):
        """Validate check-in date is not in the past."""
        check_in_date = self.cleaned_data.get('check_in_date')
        if check_in_date and check_in_date < timezone.now().date():
            raise ValidationError(_('Check-in date cannot be in the past.'))
        return check_in_date

    def clean_check_out_date(self):
        """Validate check-out date."""
        check_out_date = self.cleaned_data.get('check_out_date')
        check_in_date = self.cleaned_data.get('check_in_date')
        
        if check_out_date and check_in_date:
            if check_out_date <= check_in_date:
                raise ValidationError(_('Check-out date must be after check-in date.'))
        
        return check_out_date