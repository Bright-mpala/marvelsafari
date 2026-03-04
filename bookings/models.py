from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from datetime import timedelta

from core.models import SoftDeletableModel
from properties.models import Property, PropertyAvailability, PropertyStatus
from car_rentals.models import Car, CarAvailability, CarStatus
from tours.models import Tour, TourSchedule

class Booking(SoftDeletableModel):
    """Unified booking model for properties, cars, and tours with availability validation."""

    # Backwards-compatible alias used by views/templates
    BOOKING_STATUS = (
        ('pending', _('Pending')),
        ('confirmed', _('Confirmed')),
        ('cancelled', _('Cancelled')),
        ('completed', _('Completed')),
    )

    class BookingStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        CONFIRMED = 'confirmed', _('Confirmed')
        CANCELLED = 'cancelled', _('Cancelled')
        COMPLETED = 'completed', _('Completed')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings',
        help_text=_('User who made the booking')
    )

    # One of these must be set
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='unified_bookings',
        null=True,
        blank=True,
        help_text=_('Property being booked')
    )
    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name='unified_bookings',
        null=True,
        blank=True,
        help_text=_('Car being booked')
    )
    tour = models.ForeignKey(
        Tour,
        on_delete=models.CASCADE,
        related_name='unified_bookings',
        null=True,
        blank=True,
        help_text=_('Tour being booked')
    )
    tour_schedule = models.ForeignKey(
        TourSchedule,
        on_delete=models.SET_NULL,
        related_name='unified_bookings',
        null=True,
        blank=True,
    )

    check_in_date = models.DateField(_('check-in date'))
    check_out_date = models.DateField(_('check-out date'))

    guests = models.PositiveIntegerField(_('number of guests'), default=1)
    special_requests = models.TextField(_('special requests'), blank=True, help_text=_('Any special requests or preferences'))

    price_per_night = models.DecimalField(_('price per night'), max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(_('total amount'), max_digits=10, decimal_places=2, default=0)

    status = models.CharField(
        _('status'),
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING
    )
    cancellation_reason = models.TextField(_('cancellation reason'), blank=True)

    def __str__(self):
        target = self.property or self.car or self.tour
        return f"Booking #{self.id} - {self.user.email} ({target})"

    def clean(self):
        """Central booking validation for all listing types."""
        self._validate_dates()
        self._validate_listing_selection()
        self._validate_not_owner()
        self._validate_moderation_state()
        self._validate_availability()

    def _validate_dates(self):
        if self.check_out_date <= self.check_in_date:
            raise ValidationError({'check_out_date': _('Check-out must be after check-in.')})

    def _validate_listing_selection(self):
        selected = [bool(self.property), bool(self.car), bool(self.tour)]
        if sum(selected) != 1:
            raise ValidationError(_('Exactly one of property, car, or tour must be specified for a booking.'))

    def _validate_not_owner(self):
        owner = None
        if self.property:
            owner = getattr(self.property, 'owner', None)
        elif self.car:
            owner = getattr(self.car, 'owner', None)
        elif self.tour and self.tour.property:
            owner = getattr(self.tour.property, 'owner', None)

        if owner and owner == self.user:
            raise ValidationError(_('Owners cannot book their own listings.'))

    def _validate_moderation_state(self):
        if self.property and self.property.status not in {PropertyStatus.APPROVED, PropertyStatus.ACTIVE}:
            raise ValidationError(_('Property must be approved before it can be booked.'))
        if self.car and self.car.moderation_status != CarStatus.APPROVED:
            raise ValidationError(_('Car must be approved before it can be booked.'))
        if self.tour:
            if self.tour.property and self.tour.property.status not in {PropertyStatus.APPROVED, PropertyStatus.ACTIVE}:
                raise ValidationError(_('Tour property must be approved before the tour can be booked.'))
            if not self.tour.is_active:
                raise ValidationError(_('Tour is not active.'))

    def _validate_availability(self):
        if self.property:
            self._validate_property_availability()
        if self.car:
            self._validate_car_availability()
        if self.tour:
            self._validate_tour_availability()

    def _validate_property_availability(self):
        overlapping = Booking.objects.filter(
            property=self.property,
            status__in=[self.BookingStatus.PENDING, self.BookingStatus.CONFIRMED],
            check_in_date__lt=self.check_out_date,
            check_out_date__gt=self.check_in_date,
        )
        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)

        # Allow multiple simultaneous bookings up to the property's room capacity.
        # A hotel or lodge can have many rooms; only when the number of
        # overlapping bookings reaches total_rooms should we block further
        # bookings for those dates.
        capacity = getattr(self.property, 'total_rooms', 1) or 1
        if overlapping.count() >= capacity:
            raise ValidationError(_(
                'All rooms for this property are fully booked for the selected dates.'
            ))

        # availability table
        dates = self._date_range()
        unavailable = PropertyAvailability.objects.filter(
            property=self.property,
            date__in=dates,
            is_available=False,
        )
        if unavailable.exists():
            raise ValidationError(_('Selected dates are not available for this property.'))

    def _validate_car_availability(self):
        overlapping = Booking.objects.filter(
            car=self.car,
            status__in=[self.BookingStatus.PENDING, self.BookingStatus.CONFIRMED],
            check_in_date__lt=self.check_out_date,
            check_out_date__gt=self.check_in_date,
        )
        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)
        if overlapping.exists():
            raise ValidationError(_('The car is already booked for the selected dates.'))

        dates = self._date_range()
        unavailable = CarAvailability.objects.filter(
            car=self.car,
            date__in=dates,
            is_available=False,
        )
        if unavailable.exists():
            raise ValidationError(_('Selected dates are not available for this car.'))

    def _validate_tour_availability(self):
        if self.tour_schedule:
            if not self.tour_schedule.is_available or self.tour_schedule.is_booked_out:
                raise ValidationError(_('The selected tour schedule is not available.'))
        else:
            # Fallback: ensure schedule_date matches check-in
            if self.tour.schedule_date and self.tour.schedule_date != self.check_in_date:
                raise ValidationError(_('Tour schedule date does not match check-in date.'))

    def _date_range(self):
        current = self.check_in_date
        while current < self.check_out_date:
            yield current
            current += timedelta(days=1)

    def save(self, *args, **kwargs):
        # Only calculate if not already computed (don't override explicit values)
        if not self.total_amount or self.total_amount == Decimal('0'):
            # Gracefully handle cases where dates are not yet set
            if self.check_in_date and self.check_out_date:
                nights = (self.check_out_date - self.check_in_date).days
            else:
                nights = 0
            base_rate = self.price_per_night or Decimal('0')
            if self.car and self.car.daily_price:
                base_rate = self.car.daily_price
            if self.property and nights and base_rate:
                self.total_amount = base_rate * Decimal(str(nights))
            elif self.car and nights and base_rate:
                self.total_amount = base_rate * Decimal(str(nights))
            elif self.tour:
                self.total_amount = self.tour.base_price or base_rate

        self.full_clean()  # Run validation after total is computed
        super().save(*args, **kwargs)

    # builtins.property is used here because the class defines a field named
    # `property` which shadows the built-in `property` decorator inside the
    # class body. Using builtins.property avoids the TypeError encountered when
    # the decorator attempted to call the ForeignKey object.
    import builtins

    @builtins.property
    def nights_count(self):
        """Calculate number of nights."""
        if not self.check_in_date or not self.check_out_date:
            return 0
        return (self.check_out_date - self.check_in_date).days

    @builtins.property
    def is_upcoming(self):
        """Check if booking is in the future."""
        from django.utils import timezone
        return self.check_in_date >= timezone.now().date()

    class Meta:
        verbose_name = _('booking')
        verbose_name_plural = _('bookings')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['property', 'check_in_date', 'check_out_date']),
            models.Index(fields=['car', 'check_in_date', 'check_out_date']),
            models.Index(fields=['tour', 'check_in_date']),
            models.Index(fields=['status', 'check_in_date']),
        ]
