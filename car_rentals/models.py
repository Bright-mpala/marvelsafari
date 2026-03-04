# models.py - Fixes and updates

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import datetime, time, timedelta
import uuid
from django_countries.fields import CountryField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ObjectDoesNotExist
from django.utils.text import slugify
from decimal import Decimal
from core.models import SoftDeletableModel, BaseModel


class CarCategory(models.Model):
    """Car category/class."""
    
    name = models.CharField(_('category name'), max_length=100)
    code = models.CharField(_('category code'), max_length=10, unique=True)
    description = models.TextField(_('description'), blank=True)
    icon = models.CharField(_('icon class'), max_length=50, blank=True, 
                           help_text=_('Font Awesome icon class, e.g. fa-car'))

    # Features
    typical_cars = models.TextField(_('typical cars'), blank=True)
    passenger_capacity = models.PositiveSmallIntegerField(_('passenger capacity'), default=4)
    luggage_capacity = models.PositiveSmallIntegerField(_('luggage capacity'), default=2)

    # Fuel
    fuel_type = models.CharField(
        _('fuel type'),
        max_length=20,
        default='petrol',
        choices=[
            ('petrol', _('Petrol')),
            ('diesel', _('Diesel')),
            ('hybrid', _('Hybrid')),
            ('electric', _('Electric')),
        ]
    )

    # Transmission
    transmission = models.CharField(
        _('transmission'),
        max_length=20,
        default='automatic',
        choices=[
            ('automatic', _('Automatic')),
            ('manual', _('Manual')),
        ]
    )

    display_order = models.PositiveIntegerField(_('display order'), default=0)
    is_active = models.BooleanField(_('active'), default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        verbose_name = _('car category')
        verbose_name_plural = _('car categories')
        ordering = ['display_order', 'name']


class CarRentalCompany(models.Model):
    """Car rental company."""
    
    name = models.CharField(_('company name'), max_length=255)
    code = models.CharField(_('company code'), max_length=10, unique=True)
    logo = models.ImageField(_('logo'), upload_to='car_companies/logos/', blank=True, null=True)

    # Contact info
    website = models.URLField(_('website'), blank=True)
    phone = models.CharField(_('phone'), max_length=50, blank=True)
    email = models.EmailField(_('email'), blank=True)

    # Location
    headquarters = models.CharField(_('headquarters'), max_length=255, blank=True)
    country = CountryField(_('country'), blank=True)

    # Fleet info
    fleet_size = models.PositiveIntegerField(_('fleet size'), null=True, blank=True)
    countries_operating = models.PositiveIntegerField(
        _('countries operating'),
        null=True,
        blank=True
    )

    # Ratings
    customer_rating = models.DecimalField(
        _('customer rating'),
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Services offered
    offers_rental = models.BooleanField(_('offers car rental'), default=True)
    offers_taxi = models.BooleanField(_('offers taxi service'), default=False)

    is_active = models.BooleanField(_('active'), default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        verbose_name = _('car rental company')
        verbose_name_plural = _('car rental companies')
        ordering = ['name']


class RentalLocation(models.Model):
    """Car rental location (pickup/dropoff)."""
    
    LOCATION_TYPES = (
        ('airport', _('Airport')),
        ('downtown', _('Downtown')),
        ('station', _('Train/Bus Station')),
        ('hotel', _('Hotel')),
        ('custom', _('Custom Address')),
        ('other', _('Other')),
    )

    company = models.ForeignKey(
        CarRentalCompany,
        on_delete=models.CASCADE,
        related_name='locations'
    )
    name = models.CharField(_('location name'), max_length=255)
    location_type = models.CharField(
        _('location type'),
        max_length=20,
        choices=LOCATION_TYPES
    )

    # Address
    address = models.TextField(_('address'))
    city = models.CharField(_('city'), max_length=100)
    state = models.CharField(_('state/province'), max_length=100, blank=True)
    postal_code = models.CharField(_('postal code'), max_length=20, blank=True)
    country = CountryField(_('country'))

    # Coordinates
    latitude = models.DecimalField(
        _('latitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        _('longitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )

    # Contact
    phone = models.CharField(_('phone'), max_length=50, blank=True)
    email = models.EmailField(_('email'), blank=True)

    # Hours
    opening_hours = models.JSONField(
        _('opening hours'),
        default=dict,
        blank=True,
        help_text=_('Opening hours in JSON format')
    )

    # Services
    is_24_hours = models.BooleanField(_('24 hours'), default=False)
    has_shuttle_service = models.BooleanField(_('shuttle service'), default=False)
    has_free_parking = models.BooleanField(_('free parking'), default=False)
    supports_taxi_pickup = models.BooleanField(_('supports taxi pickup'), default=True)

    is_active = models.BooleanField(_('active'), default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}, {self.city}"

    class Meta:
        verbose_name = _('rental location')
        verbose_name_plural = _('rental locations')
        unique_together = ['company', 'name', 'city']


class CarStatus(models.TextChoices):
    """Moderation states for car listings."""
    
    PENDING = 'pending', _('Pending Review')
    APPROVED = 'approved', _('Approved')
    REJECTED = 'rejected', _('Rejected')
    INACTIVE = 'inactive', _('Inactive')


class OperationalStatus(models.TextChoices):
    """Operational status for cars."""
    
    AVAILABLE = 'available', _('Available')
    RENTED = 'rented', _('Rented')
    ON_TRIP = 'on_trip', _('On Trip')
    MAINTENANCE = 'maintenance', _('Maintenance')
    RESERVED = 'reserved', _('Reserved')


class Car(SoftDeletableModel):
    """Car inventory."""
    
    SERVICE_TYPES = (
        ('rental', _('Self-Drive Rental')),
        ('taxi', _('Taxi / Chauffeur')),
        ('both', _('Rental & Taxi')),
    )

    USAGE_FUNCTIONS = (
        ('mini', _('City / Mini')),
        ('taxi', _('Taxi & Ride-hailing')),
        ('safari', _('Safari & Overland')),
        ('executive', _('Executive Transfer')),
        ('logistics', _('Utility & Logistics')),
    )

    company = models.ForeignKey(
        CarRentalCompany,
        on_delete=models.CASCADE,
        related_name='cars'
    )
    category = models.ForeignKey(
        CarCategory,
        on_delete=models.PROTECT,
        related_name='cars'
    )

    owner = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='owned_cars',
        help_text=_('Listing owner/car provider'),
        null=True,
        blank=True
    )

    # Car details
    slug = models.SlugField(_('slug'), max_length=255, unique=True, blank=True)
    make = models.CharField(_('make'), max_length=100)
    model = models.CharField(_('model'), max_length=100)
    year = models.PositiveSmallIntegerField(_('year'))
    license_plate = models.CharField(_('license plate'), max_length=20, unique=True)
    color = models.CharField(_('color'), max_length=50, blank=True)

    # Images
    featured_image = models.ImageField(
        _('featured image'),
        upload_to='cars/featured/',
        blank=True,
        null=True,
        help_text=_('Main display image for this car')
    )

    # Service type
    service_type = models.CharField(
        _('service type'),
        max_length=10,
        choices=SERVICE_TYPES,
        default='rental',
        help_text=_('Whether this car is available for rental, taxi, or both')
    )

    usage_function = models.CharField(
        _('primary function'),
        max_length=20,
        choices=USAGE_FUNCTIONS,
        default='mini',
        help_text=_('Headline use case travelers should expect (mini, taxi, safari, executive, logistics).')
    )

    # Specifications
    doors = models.PositiveSmallIntegerField(_('doors'), default=4)
    seats = models.PositiveSmallIntegerField(_('seats'), default=5)
    engine_capacity = models.CharField(_('engine capacity'), max_length=20, blank=True, 
                                       help_text=_('e.g. 2.0L'))
    fuel_consumption = models.CharField(_('fuel consumption'), max_length=30, blank=True, 
                                        help_text=_('e.g. 8L/100km'))

    # Features
    has_ac = models.BooleanField(_('air conditioning'), default=True)
    has_gps = models.BooleanField(_('GPS'), default=False)
    has_bluetooth = models.BooleanField(_('Bluetooth'), default=False)
    has_usb = models.BooleanField(_('USB ports'), default=True)
    has_child_seat = models.BooleanField(_('child seat available'), default=False)
    has_wifi = models.BooleanField(_('WiFi hotspot'), default=False)
    has_dashcam = models.BooleanField(_('dashcam'), default=False)

    # Taxi-specific fields
    taxi_rate_per_km = models.DecimalField(
        _('taxi rate per km'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Rate per kilometer for taxi service')
    )
    taxi_base_fare = models.DecimalField(
        _('taxi base fare'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Base fare for taxi service')
    )
    taxi_per_hour = models.DecimalField(
        _('taxi hourly rate'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Rate per hour for taxi service')
    )

    # Status
    status = models.CharField(
        _('operational status'),
        max_length=20,
        choices=OperationalStatus.choices,
        default=OperationalStatus.AVAILABLE
    )
    moderation_status = models.CharField(
        _('listing status'),
        max_length=20,
        choices=CarStatus.choices,
        default=CarStatus.PENDING,
        help_text=_('Approval state for public listing')
    )

    # Current location
    current_location = models.ForeignKey(
        RentalLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cars_present'
    )

    # Real-time GPS coordinates
    current_latitude = models.DecimalField(
        _('current latitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    current_longitude = models.DecimalField(
        _('current longitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    location_updated_at = models.DateTimeField(
        _('location last updated'),
        null=True,
        blank=True
    )

    # Mileage
    mileage = models.DecimalField(
        _('mileage'),
        max_digits=10,
        decimal_places=2,
        help_text=_('in kilometers'),
        default=0
    )

    daily_price = models.DecimalField(
        _('daily price'),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_('Base rental price per day')
    )

    is_featured = models.BooleanField(_('featured car'), default=False)

    average_rating = models.DecimalField(
        _('average rating'),
        max_digits=3,
        decimal_places=2,
        default=0,
        help_text=_('Rolling average from renter reviews')
    )
    review_count = models.PositiveIntegerField(_('review count'), default=0)

    @property
    def is_rental(self):
        return self.service_type in ('rental', 'both')

    @property
    def is_taxi(self):
        return self.service_type in ('taxi', 'both')

    @property
    def primary_image_url(self):
        if self.featured_image and self.featured_image.name:
            return self.featured_image.url
        first_img = self.images.first()
        if first_img and first_img.image and first_img.image.name:
            return first_img.image.url
        return None

    @property
    def feature_list(self):
        features = []
        if self.has_ac:
            features.append('A/C')
        if self.has_gps:
            features.append('GPS')
        if self.has_bluetooth:
            features.append('Bluetooth')
        if self.has_usb:
            features.append('USB')
        if self.has_child_seat:
            features.append('Child Seat')
        if self.has_wifi:
            features.append('WiFi')
        if self.has_dashcam:
            features.append('Dashcam')
        return features

    def refresh_rating_stats(self):
        from django.db.models import Avg, Count
        stats = self.reviews.aggregate(avg=Avg('rating'), total=Count('id'))
        self.average_rating = round(stats.get('avg') or 0, 2)
        self.review_count = stats.get('total') or 0
        self.save(update_fields=['average_rating', 'review_count'])

    def __str__(self):
        return f"{self.make} {self.model} ({self.license_plate})"

    class Meta:
        verbose_name = _('car')
        verbose_name_plural = _('cars')
        ordering = ['make', 'model']
        indexes = [
            models.Index(fields=['moderation_status', 'status']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['category', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = f"{self.make}-{self.model}-{self.license_plate}"
            self.slug = slugify(base)
            # Ensure uniqueness
            original_slug = self.slug
            queryset = Car.objects.filter(slug=self.slug)
            if queryset.exists():
                counter = 1
                while queryset.filter(slug=self.slug).exists():
                    self.slug = f"{original_slug}-{counter}"
                    counter += 1
        super().save(*args, **kwargs)


class CarImage(BaseModel):
    """Multiple images for a car."""
    
    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(_('image'), upload_to='cars/gallery/')
    caption = models.CharField(_('caption'), max_length=200, blank=True)
    is_primary = models.BooleanField(_('primary image'), default=False)
    display_order = models.PositiveIntegerField(_('display order'), default=0)

    def __str__(self):
        return f"{self.car} - Image {self.display_order}"

    class Meta:
        verbose_name = _('car image')
        verbose_name_plural = _('car images')
        ordering = ['display_order']


class CarAvailability(BaseModel):
    """Date-based availability for cars with optional price overrides."""
    
    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name='availabilities'
    )
    date = models.DateField(_('date'), db_index=True)
    is_available = models.BooleanField(_('available'), default=True)
    price_override = models.DecimalField(
        _('price override'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Optional override price for this date')
    )

    class Meta:
        verbose_name = _('car availability')
        verbose_name_plural = _('car availability')
        unique_together = ['car', 'date']
        indexes = [
            models.Index(fields=['car', 'date']),
            models.Index(fields=['car', 'date', 'is_available']),
        ]

    def __str__(self):
        return f"{self.car} - {self.date}"


class CarDriver(models.Model):
    """Driver profile for car rental bookings."""
    
    company = models.ForeignKey(
        CarRentalCompany,
        on_delete=models.CASCADE,
        related_name='drivers'
    )
    cars = models.ManyToManyField(
        Car,
        blank=True,
        related_name='assigned_drivers',
        verbose_name=_('assigned cars')
    )
    full_name = models.CharField(_('full name'), max_length=255)
    photo = models.ImageField(_('photo'), upload_to='drivers/photos/', blank=True, null=True)
    email = models.EmailField(_('email'), blank=True)
    phone = models.CharField(_('phone'), max_length=50, blank=True)
    license_number = models.CharField(_('license number'), max_length=100, unique=True)
    license_country = CountryField(_('license country'))
    years_experience = models.PositiveSmallIntegerField(_('years of experience'), default=1)
    languages_spoken = models.CharField(_('languages spoken'), max_length=200, blank=True, 
                                        help_text=_('Comma-separated'))
    is_active = models.BooleanField(_('active'), default=True)

    # Real-time location
    current_latitude = models.DecimalField(
        _('current latitude'), max_digits=9, decimal_places=6, null=True, blank=True
    )
    current_longitude = models.DecimalField(
        _('current longitude'), max_digits=9, decimal_places=6, null=True, blank=True
    )
    is_available = models.BooleanField(_('currently available'), default=True)
    location_updated_at = models.DateTimeField(_('location last updated'), null=True, blank=True)

    average_rating = models.DecimalField(
        _('average rating'),
        max_digits=3,
        decimal_places=2,
        default=0
    )
    review_count = models.PositiveIntegerField(_('review count'), default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} ({self.company.name})"

    class Meta:
        verbose_name = _('car driver')
        verbose_name_plural = _('car drivers')
        ordering = ['full_name']


class RentalRate(models.Model):
    """Rental rates for car categories at locations."""
    
    company = models.ForeignKey(
        CarRentalCompany,
        on_delete=models.CASCADE,
        related_name='rates'
    )
    location = models.ForeignKey(
        RentalLocation,
        on_delete=models.CASCADE,
        related_name='rates'
    )
    category = models.ForeignKey(
        CarCategory,
        on_delete=models.CASCADE,
        related_name='rates'
    )

    # Pricing
    daily_rate = models.DecimalField(_('daily rate'), max_digits=10, decimal_places=2)
    weekly_rate = models.DecimalField(_('weekly rate'), max_digits=10, decimal_places=2)
    monthly_rate = models.DecimalField(_('monthly rate'), max_digits=10, decimal_places=2)

    # Currency
    currency = models.CharField(_('currency'), max_length=3, default='USD')

    # Mileage
    mileage_limit = models.PositiveIntegerField(
        _('mileage limit per day'),
        default=100,
        help_text=_('in kilometers')
    )
    extra_mileage_rate = models.DecimalField(
        _('extra mileage rate'),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_('per kilometer')
    )

    # Additional charges
    young_driver_surcharge = models.DecimalField(
        _('young driver surcharge'),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_('for drivers under 25')
    )
    additional_driver_fee = models.DecimalField(
        _('additional driver fee'),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_('per day')
    )

    # Insurance
    insurance_options = models.JSONField(
        _('insurance options'),
        default=dict,
        blank=True,
        help_text=_('Insurance options and prices in JSON')
    )

    # Validity
    valid_from = models.DateField(_('valid from'))
    valid_to = models.DateField(_('valid to'))
    is_active = models.BooleanField(_('active'), default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.category.name} - {self.daily_rate} {self.currency}/day"

    class Meta:
        verbose_name = _('rental rate')
        verbose_name_plural = _('rental rates')
        unique_together = ['company', 'location', 'category', 'valid_from', 'valid_to']


class CarRentalBooking(models.Model):
    """Car rental booking."""
    
    BOOKING_STATUS = (
        ('pending', _('Pending')),
        ('confirmed', _('Confirmed')),
        ('active', _('Active')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
        ('no_show', _('No Show')),
    )

    PAYMENT_STATUS = (
        ('pending', _('Pending')),
        ('deposit_paid', _('Deposit Paid')),
        ('paid', _('Paid')),
        ('failed', _('Failed')),
        ('refunded', _('Refunded')),
    )

    INSURANCE_TYPES = (
        ('basic', _('Basic')),
        ('full', _('Full Coverage')),
        ('premium', _('Premium')),
        ('none', _('None')),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_reference = models.CharField(
        _('booking reference'),
        max_length=20,
        unique=True,
        editable=False
    )

    # User
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='car_rental_bookings'
    )

    # Rental details
    company = models.ForeignKey(
        CarRentalCompany,
        on_delete=models.PROTECT,
        related_name='bookings'
    )
    category = models.ForeignKey(
        CarCategory,
        on_delete=models.PROTECT,
        related_name='bookings'
    )
    car = models.ForeignKey(
        Car,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rental_bookings'
    )
    selected_driver = models.ForeignKey(
        CarDriver,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings'
    )

    # Locations
    pickup_location = models.ForeignKey(
        RentalLocation,
        on_delete=models.PROTECT,
        related_name='pickup_bookings'
    )
    dropoff_location = models.ForeignKey(
        RentalLocation,
        on_delete=models.PROTECT,
        related_name='dropoff_bookings'
    )

    # Dates and times
    pickup_date = models.DateField(_('pickup date'))
    pickup_time = models.TimeField(_('pickup time'))
    dropoff_date = models.DateField(_('dropoff date'))
    dropoff_time = models.TimeField(_('dropoff time'))

    # Actual times (filled after rental)
    actual_pickup = models.DateTimeField(_('actual pickup'), null=True, blank=True)
    actual_dropoff = models.DateTimeField(_('actual dropoff'), null=True, blank=True)

    # Rental duration
    rental_days = models.PositiveIntegerField(_('rental days'), default=1)

    # Driver information
    driver_name = models.CharField(_('driver name'), max_length=255)
    driver_email = models.EmailField(_('driver email'), blank=True)
    driver_phone = models.CharField(_('driver phone'), max_length=50, blank=True)

    driver_age = models.PositiveSmallIntegerField(_('driver age'), null=True, blank=True)
    driver_license_number = models.CharField(_('license number'), max_length=100, blank=True)
    driver_license_country = CountryField(_('license country'), blank=True)
    driver_license_expiry = models.DateField(_('license expiry'), null=True, blank=True)

    # Additional drivers
    additional_drivers = models.JSONField(
        _('additional drivers'),
        default=list,
        blank=True
    )

    # Pricing
    daily_rate = models.DecimalField(_('daily rate'), max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(_('subtotal'), max_digits=10, decimal_places=2, default=0)

    # Additional charges
    young_driver_surcharge = models.DecimalField(
        _('young driver surcharge'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    additional_driver_fee = models.DecimalField(
        _('additional driver fee'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    location_fee = models.DecimalField(
        _('location fee'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    insurance_fee = models.DecimalField(
        _('insurance fee'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    equipment_fee = models.DecimalField(
        _('equipment fee'),
        max_digits=10,
        decimal_places=2,
        default=0
    )

    # Taxes and fees
    taxes = models.DecimalField(_('taxes'), max_digits=10, decimal_places=2, default=0)
    service_fee = models.DecimalField(_('service fee'), max_digits=10, decimal_places=2, default=0)

    # Discounts
    discount_amount = models.DecimalField(
        _('discount amount'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    coupon_code = models.CharField(_('coupon code'), max_length=50, blank=True)

    # Totals
    total_amount = models.DecimalField(_('total amount'), max_digits=10, decimal_places=2, default=0)

    # Currency
    currency = models.CharField(_('currency'), max_length=3, default='USD')

    # Payment
    payment_status = models.CharField(
        _('payment status'),
        max_length=20,
        choices=PAYMENT_STATUS,
        default='pending'
    )
    amount_paid = models.DecimalField(
        _('amount paid'),
        max_digits=10,
        decimal_places=2,
        default=0
    )

    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=BOOKING_STATUS,
        default='pending'
    )

    # Insurance
    insurance_type = models.CharField(
        _('insurance type'),
        max_length=50,
        blank=True,
        choices=INSURANCE_TYPES,
        default='basic'
    )

    # Equipment
    equipment = models.JSONField(
        _('equipment'),
        default=list,
        blank=True,
        help_text=_('Additional equipment (GPS, child seat, etc.)')
    )

    # Special requests
    special_requests = models.TextField(_('special requests'), blank=True)

    # Business booking
    is_business_booking = models.BooleanField(_('business booking'), default=False)
    business_account = models.ForeignKey(
        'accounts.BusinessAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='car_rental_bookings'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('car rental booking')
        verbose_name_plural = _('car rental bookings')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking_reference']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Car Rental {self.booking_reference}"

    def review_release_at(self):
        if not self.dropoff_date:
            return None
        dropoff_dt = datetime.combine(self.dropoff_date, self.dropoff_time or time.min)
        if timezone.is_naive(dropoff_dt):
            dropoff_dt = timezone.make_aware(dropoff_dt, timezone.get_current_timezone())
        return dropoff_dt + timedelta(days=3)

    def can_review_car(self):
        if getattr(self, 'car_review', None):
            return False
        release_at = self.review_release_at()
        if not release_at:
            return False
        return timezone.now() >= release_at and self.status in {'completed', 'active'}

    def save(self, *args, **kwargs):
        if not self.booking_reference:
            import random
            import string
            self.booking_reference = 'CAR-' + ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=8)
            )

        if self.user_id and not self.business_account_id and hasattr(self.user, 'is_business_account') and self.user.is_business_account:
            try:
                self.business_account = self.user.business_account
                self.is_business_booking = True
            except ObjectDoesNotExist:
                self.business_account = None
                self.is_business_booking = False

        if self.selected_driver:
            self.driver_name = self.selected_driver.full_name
            self.driver_email = self.selected_driver.email
            self.driver_phone = self.selected_driver.phone
            self.driver_license_number = self.selected_driver.license_number
            self.driver_license_country = self.selected_driver.license_country

        # Calculate rental days
        if self.pickup_date and self.dropoff_date:
            delta = self.dropoff_date - self.pickup_date
            self.rental_days = max(delta.days, 1)

        # Calculate subtotal
        self.subtotal = self.daily_rate * self.rental_days

        # Calculate total
        self.total_amount = (
            self.subtotal +
            self.young_driver_surcharge +
            self.additional_driver_fee +
            self.location_fee +
            self.insurance_fee +
            self.equipment_fee +
            self.taxes +
            self.service_fee -
            self.discount_amount
        )

        if self.total_amount < 0:
            self.total_amount = Decimal('0')

        super().save(*args, **kwargs)


class TaxiBooking(models.Model):
    """Taxi / transfer booking."""
    
    BOOKING_STATUS = (
        ('pending', _('Pending')),
        ('confirmed', _('Confirmed')),
        ('driver_assigned', _('Driver Assigned')),
        ('en_route', _('Driver En Route')),
        ('arrived', _('Driver Arrived')),
        ('in_progress', _('Trip In Progress')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
        ('no_show', _('No Show')),
    )

    TRIP_TYPES = (
        ('one_way', _('One Way')),
        ('round_trip', _('Round Trip')),
        ('hourly', _('Hourly Hire')),
        ('airport_transfer', _('Airport Transfer')),
        ('city_tour', _('City Tour')),
    )

    PAYMENT_METHODS = (
        ('cash', _('Cash')),
        ('card', _('Card')),
        ('mobile', _('Mobile Money')),
    )

    PAYMENT_STATUS = (
        ('pending', _('Pending')),
        ('paid', _('Paid')),
        ('failed', _('Failed')),
        ('refunded', _('Refunded')),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_reference = models.CharField(
        _('booking reference'),
        max_length=20,
        unique=True,
        editable=False
    )

    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='taxi_bookings'
    )

    # Vehicle
    car = models.ForeignKey(
        Car,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='taxi_bookings'
    )
    category = models.ForeignKey(
        CarCategory,
        on_delete=models.PROTECT,
        related_name='taxi_bookings',
        null=True,
        blank=True
    )
    driver = models.ForeignKey(
        CarDriver,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='taxi_trips'
    )
    company = models.ForeignKey(
        CarRentalCompany,
        on_delete=models.PROTECT,
        related_name='taxi_bookings',
        null=True,
        blank=True
    )

    # Trip type
    trip_type = models.CharField(
        _('trip type'),
        max_length=20,
        choices=TRIP_TYPES,
        default='one_way'
    )

    # Pickup
    pickup_address = models.TextField(_('pickup address'))
    pickup_latitude = models.DecimalField(
        _('pickup latitude'), max_digits=9, decimal_places=6, null=True, blank=True
    )
    pickup_longitude = models.DecimalField(
        _('pickup longitude'), max_digits=9, decimal_places=6, null=True, blank=True
    )
    pickup_datetime = models.DateTimeField(_('pickup date & time'))

    # Dropoff
    dropoff_address = models.TextField(_('dropoff address'))
    dropoff_latitude = models.DecimalField(
        _('dropoff latitude'), max_digits=9, decimal_places=6, null=True, blank=True
    )
    dropoff_longitude = models.DecimalField(
        _('dropoff longitude'), max_digits=9, decimal_places=6, null=True, blank=True
    )

    # For hourly bookings
    hours_booked = models.PositiveSmallIntegerField(_('hours booked'), null=True, blank=True)

    # Passenger info
    passenger_name = models.CharField(_('passenger name'), max_length=255)
    passenger_phone = models.CharField(_('passenger phone'), max_length=50)
    passenger_email = models.EmailField(_('passenger email'), blank=True)
    number_of_passengers = models.PositiveSmallIntegerField(_('number of passengers'), default=1)
    luggage_count = models.PositiveSmallIntegerField(_('luggage pieces'), default=0)

    # Flight info (for airport transfers)
    flight_number = models.CharField(_('flight number'), max_length=20, blank=True)
    flight_arrival_time = models.DateTimeField(_('flight arrival time'), null=True, blank=True)

    # Distance & duration estimates
    estimated_distance_km = models.DecimalField(
        _('estimated distance (km)'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )
    estimated_duration_minutes = models.PositiveIntegerField(
        _('estimated duration (minutes)'),
        null=True,
        blank=True
    )

    # Pricing
    base_fare = models.DecimalField(_('base fare'), max_digits=10, decimal_places=2, default=0)
    distance_charge = models.DecimalField(_('distance charge'), max_digits=10, decimal_places=2, default=0)
    time_charge = models.DecimalField(_('time charge'), max_digits=10, decimal_places=2, default=0)
    # Use Decimal default to avoid float/Decimal multiplication issues
    surge_multiplier = models.DecimalField(_('surge multiplier'), max_digits=4, decimal_places=2, default=Decimal('1.00'))
    taxes = models.DecimalField(_('taxes'), max_digits=10, decimal_places=2, default=0)
    total_fare = models.DecimalField(_('total fare'), max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(_('currency'), max_length=3, default='USD')

    # Payment
    payment_status = models.CharField(
        _('payment status'),
        max_length=20,
        choices=PAYMENT_STATUS,
        default='pending'
    )
    payment_method = models.CharField(
        _('payment method'),
        max_length=20,
        choices=PAYMENT_METHODS,
        default='card'
    )

    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=BOOKING_STATUS,
        default='pending'
    )

    # Actual times
    actual_pickup_time = models.DateTimeField(_('actual pickup time'), null=True, blank=True)
    actual_dropoff_time = models.DateTimeField(_('actual dropoff time'), null=True, blank=True)
    actual_distance_km = models.DecimalField(
        _('actual distance (km)'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Special requests
    special_requests = models.TextField(_('special requests'), blank=True)
    is_business_booking = models.BooleanField(_('business booking'), default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('taxi booking')
        verbose_name_plural = _('taxi bookings')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking_reference']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Taxi {self.booking_reference}"

    def save(self, *args, **kwargs):
        if not self.booking_reference:
            import random
            import string
            self.booking_reference = 'TAXI-' + ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=8)
            )

        # Calculate total fare
        # Normalize to Decimal in case form provides floats
        subtotal = Decimal(self.base_fare or 0) + Decimal(self.distance_charge or 0) + Decimal(self.time_charge or 0)
        multiplier = Decimal(self.surge_multiplier or 1)
        taxes = Decimal(self.taxes or 0)
        self.total_fare = (subtotal * multiplier) + taxes

        if self.total_fare < 0:
            self.total_fare = Decimal('0')

        super().save(*args, **kwargs)


class CarLocationTracker(models.Model):
    """Real-time GPS tracking log for cars."""
    
    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name='location_history'
    )
    latitude = models.DecimalField(_('latitude'), max_digits=9, decimal_places=6)
    longitude = models.DecimalField(_('longitude'), max_digits=9, decimal_places=6)
    speed_kmh = models.DecimalField(
        _('speed (km/h)'),
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    heading = models.DecimalField(
        _('heading (degrees)'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    recorded_at = models.DateTimeField(_('recorded at'), auto_now_add=True)

    class Meta:
        verbose_name = _('car location log')
        verbose_name_plural = _('car location logs')
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['car', '-recorded_at']),
        ]

    def __str__(self):
        return f"{self.car} @ {self.recorded_at}"


class CarRentalReview(models.Model):
    """Authenticated renter feedback about a specific car."""

    booking = models.OneToOneField(
        CarRentalBooking,
        on_delete=models.CASCADE,
        related_name='car_review'
    )
    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='car_reviews'
    )
    rating = models.PositiveSmallIntegerField(
        _('rating'),
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    feedback = models.TextField(_('feedback'), blank=True)
    available_after = models.DateTimeField(
        _('review window opens'),
        default=timezone.now,
        help_text=_('User can submit once this timestamp is reached')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('car rental review')
        verbose_name_plural = _('car rental reviews')
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['car', 'user'], name='unique_car_review_per_user')
        ]

    def __str__(self):
        return f"{self.car} - {self.rating}★"

    def save(self, *args, **kwargs):
        if self.booking and self.booking.dropoff_date:
            dropoff_dt = datetime.combine(
                self.booking.dropoff_date,
                self.booking.dropoff_time or time.min,
            )
            if timezone.is_naive(dropoff_dt):
                dropoff_dt = timezone.make_aware(dropoff_dt, timezone.get_current_timezone())
            self.available_after = dropoff_dt + timedelta(days=3)
        super().save(*args, **kwargs)
        self.car.refresh_rating_stats()

    @property
    def can_publish(self) -> bool:
        return timezone.now() >= self.available_after


class CarDriverReview(models.Model):
    """Authenticated user review for a rental driver."""
    
    booking = models.OneToOneField(
        CarRentalBooking,
        on_delete=models.CASCADE,
        related_name='driver_review',
        null=True,
        blank=True
    )
    taxi_booking = models.OneToOneField(
        TaxiBooking,
        on_delete=models.CASCADE,
        related_name='driver_review',
        null=True,
        blank=True
    )
    driver = models.ForeignKey(
        CarDriver,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='driver_reviews'
    )
    rating = models.PositiveSmallIntegerField(
        _('rating'),
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    feedback = models.TextField(_('feedback'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('car driver review')
        verbose_name_plural = _('car driver reviews')
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['driver', 'user'], name='unique_driver_review_per_user')
        ]

    def __str__(self):
        return f"{self.driver.full_name} - {self.rating}★"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_driver_rating()

    def update_driver_rating(self):
        from django.db.models import Avg
        driver_reviews = CarDriverReview.objects.filter(driver=self.driver)
        if driver_reviews.exists():
            avg = driver_reviews.aggregate(Avg('rating'))['rating__avg']
            self.driver.average_rating = round(avg, 2)
            self.driver.review_count = driver_reviews.count()
            self.driver.save(update_fields=['average_rating', 'review_count'])


class RentalDamageReport(models.Model):
    """Damage report for rented cars."""
    
    STATUS_CHOICES = (
        ('reported', _('Reported')),
        ('assessed', _('Assessed')),
        ('repaired', _('Repaired')),
        ('closed', _('Closed')),
    )

    booking = models.OneToOneField(
        CarRentalBooking,
        on_delete=models.CASCADE,
        related_name='damage_report'
    )

    reported_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='damage_reports'
    )
    reported_at = models.DateTimeField(_('reported at'), auto_now_add=True)

    # Damage details
    damage_description = models.TextField(_('damage description'))
    damage_photos = models.JSONField(
        _('damage photos'),
        default=list,
        blank=True
    )

    # Assessment
    estimated_repair_cost = models.DecimalField(
        _('estimated repair cost'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    assessed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assessed_damages'
    )
    assessment_date = models.DateTimeField(_('assessment date'), null=True, blank=True)

    # Resolution
    repair_cost = models.DecimalField(
        _('actual repair cost'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    insurance_covered = models.BooleanField(_('insurance covered'), default=False)
    customer_charged = models.DecimalField(
        _('customer charged'),
        max_digits=10,
        decimal_places=2,
        default=0
    )

    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='reported'
    )

    notes = models.TextField(_('notes'), blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Damage Report for {self.booking.booking_reference}"

    class Meta:
        verbose_name = _('rental damage report')
        verbose_name_plural = _('rental damage reports')