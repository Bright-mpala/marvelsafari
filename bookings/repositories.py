"""
bookings/repositories.py - Data access layer for bookings

Repository pattern for decoupling database access from business logic.
This allows for easier testing, database switching, and query optimization.
"""

from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone
from decimal import Decimal
from .models import Booking
from properties.models import Property
import logging

logger = logging.getLogger(__name__)


class BookingRepository:
    """
    Repository for booking data access operations.
    
    Provides abstraction over Django ORM for:
    - Querying
    - Creating/updating/deleting bookings
    - Transaction management
    - Locking mechanisms
    """
    
    @staticmethod
    def get_booking(booking_id, user=None):
        """
        Get a single booking by ID.
        
        Args:
            booking_id: UUID of booking
            user: Optional user filter (for permission check)
        
        Returns:
            Booking instance or None
        """
        query = Booking.objects.select_related('property', 'user')
        
        if user:
            query = query.filter(user=user)
        
        try:
            return query.get(id=booking_id)
        except Booking.DoesNotExist:
            return None
    
    @staticmethod
    def get_user_bookings(user, status=None, date_filter=None):
        """
        Get all bookings for a user with optional filters.
        
        Args:
            user: User instance
            status: Optional status filter
            date_filter: 'upcoming', 'past', or None for all
        
        Returns:
            QuerySet of bookings
        """
        query = Booking.objects.filter(user=user).select_related('property').order_by('-created_at')
        
        if status:
            query = query.filter(status=status)
        
        if date_filter == 'upcoming':
            today = timezone.now().date()
            query = query.filter(check_in_date__gte=today)
        elif date_filter == 'past':
            today = timezone.now().date()
            query = query.filter(check_out_date__lt=today)
        
        return query
    
    @staticmethod
    def get_property_bookings(property_id, start_date=None, end_date=None):
        """
        Get all bookings for a property (active bookings).
        
        Used for availability checking. Only includes pending and confirmed bookings.
        
        Args:
            property_id: UUID of property
            start_date: Optional start date filter
            end_date: Optional end date filter
        
        Returns:
            QuerySet of active bookings
        """
        query = Booking.objects.filter(
            property_id=property_id,
            status__in=['pending', 'confirmed']
        ).select_related('user')
        
        if start_date:
            query = query.filter(check_out_date__gt=start_date)
        
        if end_date:
            query = query.filter(check_in_date__lt=end_date)
        
        return query
    
    @staticmethod
    def check_availability(property_id, check_in_date, check_out_date):
        """
        Check if property is available for dates.
        
        Args:
            property_id: UUID of property
            check_in_date: Check-in date
            check_out_date: Check-out date
        
        Returns:
            True if available, False otherwise
        """
        overlapping = Booking.objects.filter(
            property_id=property_id,
            status__in=['pending', 'confirmed'],
            check_in_date__lt=check_out_date,
            check_out_date__gt=check_in_date,
        ).exists()
        
        return not overlapping
    
    @staticmethod
    @transaction.atomic
    def create_booking(user, property_obj, check_in_date, check_out_date,
                       guests=1, special_requests='', price_per_night=None):
        """
        Create a new booking within a transaction.
        
        Args:
            user: User creating the booking
            property_obj: Property instance
            check_in_date: Check-in date
            check_out_date: Check-out date
            guests: Number of guests
            special_requests: Special requests
            price_per_night: Price per night (optional, default from property)
        
        Returns:
            Booking instance
            
        Raises:
            ValidationError: If booking is invalid
        """
        from core.exceptions import NonRecoverableBookingError
        
        # Lock property row to prevent race conditions
        Property.objects.select_for_update().get(id=property_obj.id)
        
        # Check for overlapping bookings
        overlapping = Booking.objects.filter(
            property_id=property_obj.id,
            status__in=['pending', 'confirmed'],
            check_in_date__lt=check_out_date,
            check_out_date__gt=check_in_date,
        ).exists()
        
        if overlapping:
            raise NonRecoverableBookingError(
                message='Property is not available for these dates',
                code='property_not_available'
            )
        
        # Calculate number of nights
        nights = (check_out_date - check_in_date).days
        if nights <= 0:
            raise NonRecoverableBookingError(
                message='Check-out must be after check-in',
                code='invalid_dates'
            )
        
        # Get price per night
        if not price_per_night:
            price_per_night = property_obj.minimum_price or Decimal('100.00')
        
        # Calculate total
        total_amount = price_per_night * Decimal(str(nights))
        
        # Create booking
        booking = Booking.objects.create(
            user=user,
            property=property_obj,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            guests=guests,
            special_requests=special_requests,
            price_per_night=price_per_night,
            total_amount=total_amount,
            status='pending'
        )
        
        logger.info(
            f"Booking created: {booking.id}",
            extra={'booking_id': booking.id, 'user_id': user.id}
        )
        
        return booking
    
    @staticmethod
    @transaction.atomic
    def update_booking_status(booking_id, new_status, reason=''):
        """
        Update booking status with audit trail.
        
        Args:
            booking_id: UUID of booking
            new_status: New status
            reason: Reason for status change
        
        Returns:
            Updated Booking instance or None
        """
        from django.utils.timezone import now
        
        try:
            booking = Booking.objects.select_for_update().get(id=booking_id)
        except Booking.DoesNotExist:
            return None
        
        old_status = booking.status
        booking.status = new_status
        
        if new_status == 'cancelled':
            booking.cancellation_reason = reason
        
        booking.save()
        
        logger.info(
            f"Booking status updated: {old_status} -> {new_status}",
            extra={
                'booking_id': booking_id,
                'old_status': old_status,
                'new_status': new_status,
                'reason': reason
            }
        )
        
        return booking
    
    @staticmethod
    def get_pending_expiring_bookings(minutes=30):
        """
        Get pending bookings that are about to expire.
        
        Used by Celery task to auto-cancel unpaid bookings.
        
        Args:
            minutes: Minutes old for pending bookings
        
        Returns:
            QuerySet of expiring bookings
        """
        cutoff_time = timezone.now() - timezone.timedelta(minutes=minutes)
        
        return Booking.objects.filter(
            status='pending',
            created_at__lte=cutoff_time
        ).select_related('user', 'property')
    
    @staticmethod
    def get_bookings_for_review_reminder(days=5):
        """
        Get recently completed bookings ready for review reminders.
        
        Args:
            days: Number of days after completion
        
        Returns:
            QuerySet of completed bookings
        """
        cutoff_date = timezone.now().date() - timezone.timedelta(days=days)
        
        return Booking.objects.filter(
            status='completed',
            check_out_date__gte=cutoff_date,
        ).select_related('user', 'property').exclude(
            reviews__isnull=False
        )
