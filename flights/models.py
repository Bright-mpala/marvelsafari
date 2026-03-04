from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class Airport(models.Model):
    """Airport information."""
    
    iata_code = models.CharField(_('IATA code'), max_length=3, unique=True)
    icao_code = models.CharField(_('ICAO code'), max_length=4, unique=True)
    name = models.CharField(_('airport name'), max_length=255)
    city = models.CharField(_('city'), max_length=100)
    country = models.CharField(_('country'), max_length=100)
    latitude = models.DecimalField(_('latitude'), max_digits=9, decimal_places=6)
    longitude = models.DecimalField(_('longitude'), max_digits=9, decimal_places=6)
    timezone = models.CharField(_('timezone'), max_length=50)
    
    # Additional info
    terminal_count = models.PositiveSmallIntegerField(_('terminal count'), default=1)
    is_international = models.BooleanField(_('international'), default=True)
    is_active = models.BooleanField(_('active'), default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.iata_code} - {self.name}, {self.city}"
    
    class Meta:
        verbose_name = _('airport')
        verbose_name_plural = _('airports')
        ordering = ['iata_code']


class Airline(models.Model):
    """Airline information."""
    
    iata_code = models.CharField(_('IATA code'), max_length=2, unique=True)
    icao_code = models.CharField(_('ICAO code'), max_length=3, unique=True)
    name = models.CharField(_('airline name'), max_length=255)
    callsign = models.CharField(_('callsign'), max_length=100, blank=True)
    country = models.CharField(_('country'), max_length=100)
    
    # Contact info
    website = models.URLField(_('website'), blank=True)
    phone = models.CharField(_('phone'), max_length=50, blank=True)
    email = models.EmailField(_('email'), blank=True)
    
    # Fleet info
    fleet_size = models.PositiveIntegerField(_('fleet size'), null=True, blank=True)
    destinations_count = models.PositiveIntegerField(_('destinations count'), null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(_('active'), default=True)
    alliance = models.CharField(
        _('alliance'),
        max_length=50,
        blank=True,
        choices=[
            ('star_alliance', 'Star Alliance'),
            ('oneworld', 'Oneworld'),
            ('skyteam', 'SkyTeam'),
            ('', 'None'),
        ]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.iata_code} - {self.name}"
    
    class Meta:
        verbose_name = _('airline')
        verbose_name_plural = _('airlines')
        ordering = ['name']


class Aircraft(models.Model):
    """Aircraft information."""
    
    icao_code = models.CharField(_('ICAO code'), max_length=4, unique=True)
    iata_code = models.CharField(_('IATA code'), max_length=3, blank=True)
    name = models.CharField(_('aircraft name'), max_length=100)
    manufacturer = models.CharField(_('manufacturer'), max_length=100)
    model = models.CharField(_('model'), max_length=100)
    
    # Specifications
    wingspan = models.DecimalField(
        _('wingspan'),
        max_digits=6,
        decimal_places=2,
        help_text=_('in meters'),
        null=True,
        blank=True
    )
    length = models.DecimalField(
        _('length'),
        max_digits=6,
        decimal_places=2,
        help_text=_('in meters'),
        null=True,
        blank=True
    )
    height = models.DecimalField(
        _('height'),
        max_digits=6,
        decimal_places=2,
        help_text=_('in meters'),
        null=True,
        blank=True
    )
    
    # Capacity
    typical_seating = models.JSONField(
        _('typical seating'),
        default=dict,
        help_text=_('Typical seating configuration by class')
    )
    max_seating = models.PositiveSmallIntegerField(_('maximum seating'))
    cargo_capacity = models.DecimalField(
        _('cargo capacity'),
        max_digits=10,
        decimal_places=2,
        help_text=_('in kilograms'),
        null=True,
        blank=True
    )
    
    # Performance
    range = models.DecimalField(
        _('range'),
        max_digits=8,
        decimal_places=2,
        help_text=_('in kilometers'),
        null=True,
        blank=True
    )
    cruise_speed = models.DecimalField(
        _('cruise speed'),
        max_digits=6,
        decimal_places=2,
        help_text=_('in km/h'),
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.icao_code} - {self.manufacturer} {self.model}"
    
    class Meta:
        verbose_name = _('aircraft')
        verbose_name_plural = _('aircraft')


class Flight(models.Model):
    """Flight schedule information."""
    
    FLIGHT_TYPES = (
        ('domestic', _('Domestic')),
        ('international', _('International')),
        ('regional', _('Regional')),
        ('charter', _('Charter')),
    )
    
    flight_number = models.CharField(_('flight number'), max_length=10)
    airline = models.ForeignKey(Airline, on_delete=models.PROTECT, related_name='flights')
    
    # Route
    origin = models.ForeignKey(
        Airport,
        on_delete=models.PROTECT,
        related_name='departing_flights'
    )
    destination = models.ForeignKey(
        Airport,
        on_delete=models.PROTECT,
        related_name='arriving_flights'
    )
    
    # Schedule
    departure_time = models.TimeField(_('departure time'))
    arrival_time = models.TimeField(_('arrival time'))
    duration = models.DurationField(_('duration'))
    days_of_week = models.CharField(
        _('days of week'),
        max_length=50,
        help_text=_('Comma-separated days (0=Monday, 6=Sunday)')
    )
    
    # Aircraft
    aircraft = models.ForeignKey(
        Aircraft,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='flights'
    )
    
    # Flight info
    flight_type = models.CharField(
        _('flight type'),
        max_length=20,
        choices=FLIGHT_TYPES,
        default='domestic'
    )
    is_code_share = models.BooleanField(_('code share'), default=False)
    operating_airline = models.ForeignKey(
        Airline,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operating_flights'
    )
    code_share_flight_number = models.CharField(
        _('code share flight number'),
        max_length=10,
        blank=True
    )
    
    # Status
    is_active = models.BooleanField(_('active'), default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.airline.iata_code}{self.flight_number} - {self.origin.iata_code} to {self.destination.iata_code}"
    
    class Meta:
        verbose_name = _('flight')
        verbose_name_plural = _('flights')
        unique_together = ['airline', 'flight_number']
        indexes = [
            models.Index(fields=['origin', 'destination']),
        ]


class FlightSchedule(models.Model):
    """Actual flight schedule for specific dates."""
    
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE, related_name='schedules')
    departure_date = models.DateField(_('departure date'))
    
    # Actual times (can differ from scheduled)
    actual_departure_time = models.DateTimeField(
        _('actual departure time'),
        null=True,
        blank=True
    )
    actual_arrival_time = models.DateTimeField(
        _('actual arrival time'),
        null=True,
        blank=True
    )
    actual_duration = models.DurationField(
        _('actual duration'),
        null=True,
        blank=True
    )
    
    # Status
    STATUS_CHOICES = (
        ('scheduled', _('Scheduled')),
        ('boarding', _('Boarding')),
        ('departed', _('Departed')),
        ('in_air', _('In Air')),
        ('landed', _('Landed')),
        ('arrived', _('Arrived')),
        ('cancelled', _('Cancelled')),
        ('delayed', _('Delayed')),
        ('diverted', _('Diverted')),
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled'
    )
    
    # Gate information
    departure_gate = models.CharField(_('departure gate'), max_length=10, blank=True)
    arrival_gate = models.CharField(_('arrival gate'), max_length=10, blank=True)
    
    # Aircraft info for this specific schedule
    aircraft_registration = models.CharField(
        _('aircraft registration'),
        max_length=10,
        blank=True
    )
    
    # Delay information
    delay_reason = models.TextField(_('delay reason'), blank=True)
    delay_minutes = models.PositiveIntegerField(_('delay minutes'), default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.flight} - {self.departure_date}"
    
    class Meta:
        verbose_name = _('flight schedule')
        verbose_name_plural = _('flight schedules')
        unique_together = ['flight', 'departure_date']
        indexes = [
            models.Index(fields=['departure_date', 'status']),
        ]


class FlightSeatClass(models.Model):
    """Seat class configuration for flights."""
    
    name = models.CharField(_('class name'), max_length=50)
    code = models.CharField(_('class code'), max_length=2, unique=True)
    description = models.TextField(_('description'), blank=True)
    
    # Features
    baggage_allowance = models.JSONField(
        _('baggage allowance'),
        default=dict,
        help_text=_('Baggage allowance in JSON format')
    )
    meal_included = models.BooleanField(_('meal included'), default=True)
    entertainment_included = models.BooleanField(_('entertainment included'), default=True)
    wifi_included = models.BooleanField(_('WiFi included'), default=False)
    priority_boarding = models.BooleanField(_('priority boarding'), default=False)
    lounge_access = models.BooleanField(_('lounge access'), default=False)
    
    # Display order
    display_order = models.PositiveIntegerField(_('display order'), default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    class Meta:
        verbose_name = _('flight seat class')
        verbose_name_plural = _('flight seat classes')
        ordering = ['display_order']


class FlightFare(models.Model):
    """Flight fare information."""
    
    flight_schedule = models.ForeignKey(
        FlightSchedule,
        on_delete=models.CASCADE,
        related_name='fares'
    )
    seat_class = models.ForeignKey(
        FlightSeatClass,
        on_delete=models.PROTECT,
        related_name='fares'
    )
    
    # Pricing
    base_fare = models.DecimalField(_('base fare'), max_digits=10, decimal_places=2)
    taxes = models.DecimalField(_('taxes'), max_digits=10, decimal_places=2, default=0)
    fees = models.DecimalField(_('fees'), max_digits=10, decimal_places=2, default=0)
    total_fare = models.DecimalField(_('total fare'), max_digits=10, decimal_places=2)
    
    # Currency
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    
    # Availability
    available_seats = models.PositiveIntegerField(_('available seats'))
    total_seats = models.PositiveIntegerField(_('total seats'))
    
    # Booking conditions
    is_refundable = models.BooleanField(_('refundable'), default=False)
    cancellation_fee = models.DecimalField(
        _('cancellation fee'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    change_fee = models.DecimalField(
        _('change fee'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    # Restrictions
    min_days_before_departure = models.PositiveSmallIntegerField(
        _('minimum days before departure'),
        default=0
    )
    max_days_before_departure = models.PositiveSmallIntegerField(
        _('maximum days before departure'),
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.flight_schedule} - {self.seat_class} - {self.total_fare} {self.currency}"
    
    class Meta:
        verbose_name = _('flight fare')
        verbose_name_plural = _('flight fares')
        unique_together = ['flight_schedule', 'seat_class']
    
    def save(self, *args, **kwargs):
        self.total_fare = self.base_fare + self.taxes + self.fees
        super().save(*args, **kwargs)


class FlightBooking(models.Model):
    """Flight booking information."""
    
    BOOKING_STATUS = (
        ('pending', _('Pending')),
        ('confirmed', _('Confirmed')),
        ('ticketed', _('Ticketed')),
        ('cancelled', _('Cancelled')),
        ('refunded', _('Refunded')),
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
        related_name='flight_bookings'
    )
    
    # Flight details
    flight_schedule = models.ForeignKey(
        FlightSchedule,
        on_delete=models.PROTECT,
        related_name='bookings'
    )
    fare = models.ForeignKey(
        FlightFare,
        on_delete=models.PROTECT,
        related_name='bookings'
    )
    
    # Passenger information
    passenger_count = models.PositiveSmallIntegerField(_('passenger count'), default=1)
    
    # Pricing
    base_fare = models.DecimalField(_('base fare'), max_digits=10, decimal_places=2)
    taxes = models.DecimalField(_('taxes'), max_digits=10, decimal_places=2, default=0)
    fees = models.DecimalField(_('fees'), max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(_('total amount'), max_digits=10, decimal_places=2)
    
    # Discounts
    discount_amount = models.DecimalField(
        _('discount amount'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    coupon_code = models.CharField(_('coupon code'), max_length=50, blank=True)
    
    # Currency
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    
    # Payment
    payment_status = models.CharField(
        _('payment status'),
        max_length=20,
        choices=(
            ('pending', _('Pending')),
            ('paid', _('Paid')),
            ('failed', _('Failed')),
            ('refunded', _('Refunded')),
        ),
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
    
    # Business booking
    is_business_booking = models.BooleanField(_('business booking'), default=False)
    business_account = models.ForeignKey(
        'accounts.BusinessAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='flight_bookings'
    )
    
    # Additional info
    special_requests = models.TextField(_('special requests'), blank=True)
    booking_notes = models.TextField(_('booking notes'), blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ticketed_at = models.DateTimeField(_('ticketed at'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('flight booking')
        verbose_name_plural = _('flight bookings')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Flight Booking {self.booking_reference}"
    
    def save(self, *args, **kwargs):
        if not self.booking_reference:
            import random
            import string
            self.booking_reference = 'FLT-' + ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            )
        
        # Calculate total amount
        self.total_amount = self.base_fare + self.taxes + self.fees - self.discount_amount
        if self.total_amount < 0:
            self.total_amount = 0
        
        super().save(*args, **kwargs)


class FlightPassenger(models.Model):
    """Passenger information for flight bookings."""
    
    GENDER_CHOICES = (
        ('male', _('Male')),
        ('female', _('Female')),
        ('other', _('Other')),
        ('prefer_not_to_say', _('Prefer not to say')),
    )
    
    booking = models.ForeignKey(
        FlightBooking,
        on_delete=models.CASCADE,
        related_name='passengers'
    )
    
    # Personal info
    title = models.CharField(
        _('title'),
        max_length=10,
        choices=[
            ('mr', 'Mr'),
            ('mrs', 'Mrs'),
            ('ms', 'Ms'),
            ('miss', 'Miss'),
            ('dr', 'Dr'),
        ]
    )
    first_name = models.CharField(_('first name'), max_length=100)
    last_name = models.CharField(_('last name'), max_length=100)
    date_of_birth = models.DateField(_('date of birth'))
    gender = models.CharField(_('gender'), max_length=20, choices=GENDER_CHOICES)
    nationality = models.CharField(_('nationality'), max_length=100)
    
    # Contact info
    email = models.EmailField(_('email'), blank=True)
    phone = models.CharField(_('phone'), max_length=50, blank=True)
    
    # Travel document
    passport_number = models.CharField(_('passport number'), max_length=50)
    passport_expiry = models.DateField(_('passport expiry'))
    passport_country = models.CharField(_('passport country'), max_length=100)
    
    # Frequent flyer
    frequent_flyer_number = models.CharField(
        _('frequent flyer number'),
        max_length=50,
        blank=True
    )
    frequent_flyer_airline = models.ForeignKey(
        Airline,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='passengers'
    )
    
    # Seat assignment
    seat_number = models.CharField(_('seat number'), max_length=10, blank=True)
    seat_preference = models.CharField(
        _('seat preference'),
        max_length=20,
        blank=True,
        choices=[
            ('window', 'Window'),
            ('aisle', 'Aisle'),
            ('middle', 'Middle'),
            ('', 'No Preference'),
        ]
    )
    
    # Meal preference
    meal_preference = models.CharField(
        _('meal preference'),
        max_length=50,
        blank=True,
        choices=[
            ('standard', 'Standard'),
            ('vegetarian', 'Vegetarian'),
            ('vegan', 'Vegan'),
            ('gluten_free', 'Gluten Free'),
            ('kosher', 'Kosher'),
            ('halal', 'Halal'),
            ('child', 'Child Meal'),
        ]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.booking.booking_reference}"
    
    class Meta:
        verbose_name = _('flight passenger')
        verbose_name_plural = _('flight passengers')
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"