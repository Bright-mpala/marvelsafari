# forms.py - Updated

from django import forms
from django.utils import timezone

from .models import (
    Car,
    CarCategory,
    CarDriver,
    CarDriverReview,
    CarRentalBooking,
    CarRentalReview,
    RentalLocation,
    TaxiBooking,
)


class DriverSelectWidget(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if hasattr(value, 'instance') and value.instance:
            driver = value.instance
            option['attrs'].update({
                'data-driver-name': driver.full_name or '',
                'data-driver-email': driver.email or '',
                'data-driver-phone': driver.phone or '',
                'data-driver-license-number': driver.license_number or '',
                'data-driver-license-country': str(driver.license_country or ''),
            })
        return option


class CarRentalBookingForm(forms.ModelForm):
    selected_driver = forms.ModelChoiceField(
        queryset=CarDriver.objects.none(),
        required=False,
        widget=DriverSelectWidget,
        empty_label="Select a driver (optional)",
    )

    def __init__(self, *args, user=None, car=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.car = car
        self.fields['selected_driver'].queryset = CarDriver.objects.none()

        if car is not None:
            location_queryset = RentalLocation.objects.filter(
                company=car.company,
                is_active=True,
            ).order_by('name')
            
            self.fields['pickup_location'].queryset = location_queryset
            self.fields['dropoff_location'].queryset = location_queryset

            self.fields['selected_driver'].queryset = CarDriver.objects.filter(
                company=car.company,
                cars=car,
                is_active=True,
            ).order_by('-average_rating', 'full_name').distinct()

        if user is not None:
            self.fields['driver_name'].initial = getattr(user, 'full_name', '') or user.email
            self.fields['driver_email'].initial = user.email
            self.fields['driver_phone'].initial = getattr(user, 'phone_number', '')

        # Auto-select single driver
        if not self.is_bound and self.fields['selected_driver'].queryset.count() == 1:
            only_driver = self.fields['selected_driver'].queryset.first()
            self.fields['selected_driver'].initial = only_driver
            self.fields['driver_name'].initial = only_driver.full_name
            self.fields['driver_email'].initial = only_driver.email
            self.fields['driver_phone'].initial = only_driver.phone
            self.fields['driver_license_number'].initial = only_driver.license_number
            self.fields['driver_license_country'].initial = only_driver.license_country

        # Style all fields
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect, forms.HiddenInput)):
                field.widget.attrs.setdefault('class', 'form-input w-full rounded-lg border-gray-300 focus:border-[#0071c2] focus:ring-[#0071c2]')

    def clean_selected_driver(self):
        selected_driver = self.cleaned_data.get('selected_driver')
        if selected_driver and self.car and not selected_driver.cars.filter(pk=self.car.pk).exists():
            raise forms.ValidationError('Selected driver is not assigned to this car.')
        return selected_driver

    def clean(self):
        cleaned_data = super().clean()

        pickup_date = cleaned_data.get('pickup_date')
        pickup_time = cleaned_data.get('pickup_time')
        dropoff_date = cleaned_data.get('dropoff_date')
        dropoff_time = cleaned_data.get('dropoff_time')
        driver_age = cleaned_data.get('driver_age')
        driver_license_expiry = cleaned_data.get('driver_license_expiry')
        selected_driver = cleaned_data.get('selected_driver')

        today = timezone.localdate()

        # Pickup cannot be in the past
        if pickup_date and pickup_date < today:
            self.add_error('pickup_date', 'Pickup date cannot be in the past.')

        # Dropoff must be after pickup
        if pickup_date and dropoff_date:
            if dropoff_date < pickup_date:
                self.add_error('dropoff_date', 'Dropoff date cannot be before pickup date.')
            elif dropoff_date == pickup_date and pickup_time and dropoff_time and dropoff_time <= pickup_time:
                self.add_error('dropoff_time', 'For same-day rentals, dropoff time must be after pickup time.')

        # Basic age rule for self-drive
        if driver_age is not None and driver_age < 23 and not selected_driver:
            self.add_error('driver_age', 'Drivers under 23 must select a professional chauffeur.')

        # License must be valid on pickup date
        if driver_license_expiry and pickup_date and driver_license_expiry < pickup_date:
            self.add_error('driver_license_expiry', 'Driving license must be valid on the pickup date.')

        return cleaned_data

    class Meta:
        model = CarRentalBooking
        fields = [
            'pickup_date',
            'pickup_time',
            'dropoff_date',
            'dropoff_time',
            'pickup_location',
            'dropoff_location',
            'selected_driver',
            'driver_name',
            'driver_email',
            'driver_phone',
            'driver_age',
            'driver_license_number',
            'driver_license_country',
            'driver_license_expiry',
        ]
        widgets = {
            'pickup_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'dropoff_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'pickup_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-input'}),
            'dropoff_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-input'}),
            'driver_license_expiry': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class TaxiBookingForm(forms.ModelForm):
    """Form for booking a taxi/transfer."""
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['passenger_name'].initial = getattr(user, 'full_name', '') or user.email
            self.fields['passenger_email'].initial = user.email
            self.fields['passenger_phone'].initial = str(user.phone_number) if getattr(user, 'phone_number', None) else ''

        # Set default pickup time to 1 hour from now
        if not self.is_bound and not self.initial.get('pickup_datetime'):
            from datetime import timedelta
            self.initial['pickup_datetime'] = (timezone.now() + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')

        # Style all fields
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect, forms.HiddenInput)):
                field.widget.attrs.setdefault('class', 'form-input w-full rounded-lg border-gray-300 focus:border-[#0071c2] focus:ring-[#0071c2]')

    class Meta:
        model = TaxiBooking
        fields = [
            'trip_type',
            'pickup_address',
            'pickup_latitude',
            'pickup_longitude',
            'pickup_datetime',
            'dropoff_address',
            'dropoff_latitude',
            'dropoff_longitude',
            'passenger_name',
            'passenger_phone',
            'passenger_email',
            'number_of_passengers',
            'luggage_count',
            'flight_number',
            'special_requests',
            'payment_method',
        ]
        widgets = {
            'pickup_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'pickup_address': forms.TextInput(attrs={'placeholder': 'Enter pickup address'}),
            'dropoff_address': forms.TextInput(attrs={'placeholder': 'Enter destination address'}),
            'pickup_latitude': forms.HiddenInput(),
            'pickup_longitude': forms.HiddenInput(),
            'dropoff_latitude': forms.HiddenInput(),
            'dropoff_longitude': forms.HiddenInput(),
            'special_requests': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Any special requirements...'}),
            'flight_number': forms.TextInput(attrs={'placeholder': 'e.g. KQ100'}),
        }


class CarDriverReviewForm(forms.ModelForm):
    class Meta:
        model = CarDriverReview
        fields = ['rating', 'feedback']
        widgets = {
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5, 'class': 'form-control'}),
            'feedback': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Share your experience with the driver...'}),
        }


class CarReviewForm(forms.ModelForm):
    class Meta:
        model = CarRentalReview
        fields = ['rating', 'feedback']
        widgets = {
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5, 'class': 'form-control'}),
            'feedback': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Tell future guests about the car condition, comfort, and reliability...'}),
        }


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class CarSubmissionForm(forms.ModelForm):
    """Form for users to submit their own cars for rental or taxi."""

    gallery_images = forms.FileField(
        required=False,
        widget=MultiFileInput(attrs={'multiple': True}),
        help_text='Upload interior, exterior, and plate shots (up to 5).',
    )

    class Meta:
        model = Car
        fields = [
            'category',
            'make',
            'model',
            'year',
            'license_plate',
            'color',
            'featured_image',
            'current_location',
            'service_type',
            'usage_function',
            'doors',
            'seats',
            'engine_capacity',
            'fuel_consumption',
            'has_ac',
            'has_gps',
            'has_bluetooth',
            'has_usb',
            'has_child_seat',
            'has_wifi',
            'has_dashcam',
            'daily_price',
            'taxi_base_fare',
            'taxi_rate_per_km',
            'taxi_per_hour',
            'gallery_images',
        ]
        widgets = {
            'year': forms.NumberInput(attrs={'min': 1980, 'max': timezone.now().year + 1}),
            'license_plate': forms.TextInput(attrs={'placeholder': 'e.g. KAA 123A'}),
            'daily_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'taxi_base_fare': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'taxi_rate_per_km': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'taxi_per_hour': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = CarCategory.objects.filter(is_active=True)
        location_qs = RentalLocation.objects.filter(is_active=True)
        if company is not None:
            company_locations = location_qs.filter(company=company)
            if company_locations.exists():
                location_qs = company_locations
        self.fields['current_location'].queryset = location_qs.order_by('city', 'name')
        self.fields['current_location'].empty_label = 'Choose an active pickup point'

        # Apply consistent styling to inputs
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect, forms.ClearableFileInput)):
                continue
            field.widget.attrs.setdefault(
                'class',
                'form-input w-full rounded-lg border-gray-300 focus:border-[#0071c2] focus:ring-[#0071c2]'
            )

    def clean_year(self):
        year = self.cleaned_data.get('year')
        current_year = timezone.now().year + 1
        if year and (year < 1980 or year > current_year):
            raise forms.ValidationError('Enter a valid vehicle year.')
        return year

    def clean_gallery_images(self):
        return self.files.getlist('gallery_images')


class CarEditForm(CarSubmissionForm):
    """Form for owners to edit their approved car listings."""

    class Meta(CarSubmissionForm.Meta):
        # Same fields as submission, but some fields are read-only for approved cars
        fields = CarSubmissionForm.Meta.fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # For approved cars, make certain fields read-only
        instance = kwargs.get('instance')
        if instance and instance.moderation_status == 'approved':
            # License plate shouldn't change after approval
            self.fields['license_plate'].widget.attrs['readonly'] = True
            self.fields['license_plate'].help_text = 'License plate cannot be changed after approval'