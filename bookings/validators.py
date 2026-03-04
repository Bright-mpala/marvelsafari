"""
bookings/validators.py - Validation rules for bookings

Centralized validation logic for:
- Date validation
- Guest count validation
- Pricing validation
- Business rule checks
"""

from datetime import date, datetime
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class BookingValidator:
    """Validates booking data according to business rules."""
    
    MIN_GUESTS = 1
    MAX_GUESTS = 20
    MAX_ADVANCE_BOOKING_DAYS = 365
    MIN_STAY_DAYS = 1
    MAX_STAY_DAYS = 365
    MIN_PRICE = Decimal('0.01')
    MAX_PRICE = Decimal('99999.99')
    
    @classmethod
    def validate_dates(cls, check_in_date, check_out_date):
        """
        Validate check-in and check-out dates.
        
        Args:
            check_in_date: Date or datetime
            check_out_date: Date or datetime
        
        Raises:
            ValidationError: If dates are invalid
        """
        # Convert to date if datetime
        if isinstance(check_in_date, datetime):
            check_in_date = check_in_date.date()
        if isinstance(check_out_date, datetime):
            check_out_date = check_out_date.date()
        
        today = timezone.now().date()
        
        # Check-in cannot be in the past
        if check_in_date < today:
            raise ValidationError(
                _('Check-in date cannot be in the past.'),
                code='past_checkin'
            )
        
        # Check-out must be after check-in
        if check_out_date <= check_in_date:
            raise ValidationError(
                _('Check-out date must be after check-in date.'),
                code='invalid_checkout'
            )
        
        # Minimum stay duration
        length_of_stay = (check_out_date - check_in_date).days
        if length_of_stay < cls.MIN_STAY_DAYS:
            raise ValidationError(
                _('Minimum stay is %(min_days)d day(s).'),
                code='minimum_stay',
                params={'min_days': cls.MIN_STAY_DAYS}
            )
        
        # Maximum stay duration
        if length_of_stay > cls.MAX_STAY_DAYS:
            raise ValidationError(
                _('Maximum stay is %(max_days)d days.'),
                code='maximum_stay',
                params={'max_days': cls.MAX_STAY_DAYS}
            )
        
        # Maximum advance booking
        advance_days = (check_in_date - today).days
        if advance_days > cls.MAX_ADVANCE_BOOKING_DAYS:
            raise ValidationError(
                _('Cannot book more than %(max_days)d days in advance.'),
                code='too_far_advance',
                params={'max_days': cls.MAX_ADVANCE_BOOKING_DAYS}
            )
        
        return True
    
    @classmethod
    def validate_guests(cls, guests):
        """
        Validate number of guests.
        
        Args:
            guests: Number of guests
        
        Raises:
            ValidationError: If invalid
        """
        if not isinstance(guests, int):
            raise ValidationError(
                _('Guests must be an integer.'),
                code='invalid_type'
            )
        
        if guests < cls.MIN_GUESTS:
            raise ValidationError(
                _('Minimum %(min_guests)d guest(s) required.'),
                code='too_few_guests',
                params={'min_guests': cls.MIN_GUESTS}
            )
        
        if guests > cls.MAX_GUESTS:
            raise ValidationError(
                _('Maximum %(max_guests)d guests allowed.'),
                code='too_many_guests',
                params={'max_guests': cls.MAX_GUESTS}
            )
        
        return True
    
    @classmethod
    def validate_price(cls, price):
        """
        Validate price per night.
        
        Args:
            price: Price as Decimal
        
        Raises:
            ValidationError: If invalid
        """
        if not isinstance(price, (Decimal, int, float)):
            raise ValidationError(
                _('Price must be a number.'),
                code='invalid_type'
            )
        
        price = Decimal(str(price))
        
        if price < cls.MIN_PRICE:
            raise ValidationError(
                _('Price must be at least %(min_price)s.'),
                code='price_too_low',
                params={'min_price': cls.MIN_PRICE}
            )
        
        if price > cls.MAX_PRICE:
            raise ValidationError(
                _('Price cannot exceed %(max_price)s.'),
                code='price_too_high',
                params={'max_price': cls.MAX_PRICE}
            )
        
        return True
    
    @classmethod
    def validate_special_requests(cls, special_requests):
        """
        Validate special requests text.
        
        Args:
            special_requests: Special requests text
        
        Raises:
            ValidationError: If invalid
        """
        if not isinstance(special_requests, str):
            raise ValidationError(
                _('Special requests must be text.'),
                code='invalid_type'
            )
        
        if len(special_requests) > 1000:
            raise ValidationError(
                _('Special requests must be under 1000 characters.'),
                code='too_long'
            )
        
        return True
    
    @classmethod
    def validate_booking_data(cls, check_in_date, check_out_date, guests,
                              price_per_night=None, special_requests=''):
        """
        Validate all booking data together.
        
        Args:
            check_in_date: Check-in date
            check_out_date: Check-out date
            guests: Number of guests
            price_per_night: Price (optional)
            special_requests: Special requests (optional)
        
        Returns:
            dict: Errors (empty dict if valid)
        """
        errors = {}
        
        # Validate dates
        try:
            cls.validate_dates(check_in_date, check_out_date)
        except ValidationError as e:
            errors['dates'] = str(e.message)
        
        # Validate guests
        try:
            cls.validate_guests(guests)
        except ValidationError as e:
            errors['guests'] = str(e.message)
        
        # Validate price if provided
        if price_per_night:
            try:
                cls.validate_price(price_per_night)
            except ValidationError as e:
                errors['price_per_night'] = str(e.message)
        
        # Validate special requests
        if special_requests:
            try:
                cls.validate_special_requests(special_requests)
            except ValidationError as e:
                errors['special_requests'] = str(e.message)
        
        return errors
