"""
bookings/services.py - Business logic layer for bookings

Service layer orchestrates business logic, coordinates between repositories,
and handles domain-specific operations like booking workflows.
"""

import logging
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from core.exceptions import (
    NonRecoverableBookingError, 
    ConcurrencyError,
    InvalidDataError,
    EnterpriseAPIException
)
from core.monitoring import record_booking_created, record_booking_cancelled, record_booking_completed
from .repositories import BookingRepository
from properties.models import Property

logger = logging.getLogger(__name__)


class BookingService:
    """
    High-level booking operations and domain logic.
    
    Responsibilities:
    - Validate booking requests
    - Coordinate with repositories
    - Send notifications
    - Handle state transitions
    - Publish domain events
    """
    
    def __init__(self):
        self.repository = BookingRepository()
    
    def create_booking(self, user, property_id, check_in_date, check_out_date,
                      guests=1, special_requests='', price_per_night=None):
        """
        Create a new booking through the service layer.
        
        This method:
        1. Validates input
        2. Checks property availability
        3. Creates booking with transaction safety
        4. Publishes booking created event
        5. Triggers notification tasks
        
        Args:
            user: User creating the booking
            property_id: Property UUID
            check_in_date: Date object for check-in
            check_out_date: Date object for check-out
            guests: Number of guests
            special_requests: Special requests text
            price_per_night: Custom price (optional)
        
        Returns:
            Booking instance
        
        Raises:
            NonRecoverableBookingError: If booking cannot be created
            InvalidDataError: If input is invalid
        """
        
        # Validate dates
        if check_out_date <= check_in_date:
            raise InvalidDataError(
                message='Check-out date must be after check-in date',
                code='invalid_dates'
            )
        
        today = timezone.now().date()
        if check_in_date < today:
            raise InvalidDataError(
                message='Cannot book dates in the past',
                code='past_dates'
            )
        
        # Validate guests count
        if not isinstance(guests, int) or guests < 1 or guests > 20:
            raise InvalidDataError(
                message='Guests must be between 1 and 20',
                code='invalid_guests'
            )
        
        # Get property
        property_obj = self._get_and_validate_property(property_id)
        
        # Create booking with transaction safety
        try:
            booking = self.repository.create_booking(
                user=user,
                property_obj=property_obj,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                guests=guests,
                special_requests=special_requests,
                price_per_night=price_per_night
            )
            
            # Record metrics
            record_booking_created()
            
            # Publish event (async via Celery)
            self._publish_booking_created_event(booking)
            
            # Send confirmation email (background task)
            self._send_booking_confirmation(booking)
            
            logger.info(
                f"Booking created successfully: {booking.id}",
                extra={
                    'booking_id': str(booking.id),
                    'user_id': str(user.id),
                    'property_id': str(property_id)
                }
            )
            
            return booking
        
        except Exception as e:
            logger.error(
                f"Error creating booking: {str(e)}",
                exc_info=True,
                extra={
                    'user_id': str(user.id),
                    'property_id': str(property_id)
                }
            )
            raise
    
    def confirm_booking(self, booking_id, user):
        """
        Confirm a pending booking (transition to confirmed state).
        
        Args:
            booking_id: Booking UUID
            user: User confirming the booking
        
        Returns:
            Updated Booking instance
        
        Raises:
            NonRecoverableBookingError: If booking cannot be confirmed
        """
        
        booking = self.repository.get_booking(booking_id, user=user)
        if not booking:
            raise NonRecoverableBookingError(
                message='Booking not found',
                code='booking_not_found'
            )
        
        if booking.status != 'pending':
            raise NonRecoverableBookingError(
                message=f'Cannot confirm booking in {booking.status} status',
                code='invalid_state_transition'
            )
        
        # Update status
        booking = self.repository.update_booking_status(
            booking_id,
            'confirmed',
            reason='Payment confirmed'
        )
        
        # Publish event
        self._publish_booking_confirmed_event(booking)
        
        # Send confirmation
        self._send_confirmation_notification(booking)
        
        return booking
    
    def cancel_booking(self, booking_id, user, reason=''):
        """
        Cancel an existing booking.
        
        Args:
            booking_id: Booking UUID
            user: User cancelling
            reason: Cancellation reason
        
        Returns:
            Updated Booking instance
        
        Raises:
            NonRecoverableBookingError: If booking cannot be cancelled
        """
        
        booking = self.repository.get_booking(booking_id, user=user)
        if not booking:
            raise NonRecoverableBookingError(
                message='Booking not found',
                code='booking_not_found'
            )
        
        if booking.status not in ['pending', 'confirmed']:
            raise NonRecoverableBookingError(
                message=f'Cannot cancel booking in {booking.status} status',
                code='invalid_state_transition'
            )
        
        # Check cancellation policy
        today = timezone.now().date()
        days_until_checkin = (booking.check_in_date - today).days
        
        if days_until_checkin < 0:
            raise NonRecoverableBookingError(
                message='Cannot cancel cancelled past bookings',
                code='already_passed'
            )
        
        # Update status
        booking = self.repository.update_booking_status(
            booking_id,
            'cancelled',
            reason=reason
        )
        
        # Record metrics
        record_booking_cancelled()
        
        # Publish event
        self._publish_booking_cancelled_event(booking)
        
        # Send cancellation notification
        self._send_cancellation_notification(booking)
        
        return booking
    
    def get_booking_details(self, booking_id, user):
        """Get booking details with authorization check."""
        booking = self.repository.get_booking(booking_id, user=user)
        if not booking:
            raise NonRecoverableBookingError(
                message='Booking not found',
                code='booking_not_found'
            )
        return booking
    
    def get_user_bookings(self, user, status=None, date_filter=None, page=1, page_size=20):
        """Get paginated list of user bookings."""
        query = self.repository.get_user_bookings(user, status=status, date_filter=date_filter)
        
        # Simple pagination
        offset = (page - 1) * page_size
        total_count = query.count()
        bookings = query[offset:offset + page_size]
        
        return {
            'bookings': bookings,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        }
    
    @staticmethod
    def _get_and_validate_property(property_id):
        """Get and validate property exists and is active."""
        try:
            property_obj = Property.objects.get(id=property_id, status='active')
            return property_obj
        except Property.DoesNotExist:
            raise InvalidDataError(
                message='Property not found or not available',
                code='property_not_found'
            )
    
    @staticmethod
    def _publish_booking_created_event(booking):
        """Publish booking created event (async)."""
        # In a full microservices architecture, this would publish to a message queue
        # For now, we'll use Celery
        try:
            from bookings.tasks import publish_booking_event
            publish_booking_event.delay(booking.id, 'booking.created')
        except Exception as e:
            logger.warning(f"Failed to publish booking event: {e}")
    
    @staticmethod
    def _publish_booking_confirmed_event(booking):
        """Publish booking confirmed event (async)."""
        try:
            from bookings.tasks import publish_booking_event
            publish_booking_event.delay(booking.id, 'booking.confirmed')
        except Exception as e:
            logger.warning(f"Failed to publish booking event: {e}")
    
    @staticmethod
    def _publish_booking_cancelled_event(booking):
        """Publish booking cancelled event (async)."""
        try:
            from bookings.tasks import publish_booking_event
            publish_booking_event.delay(booking.id, 'booking.cancelled')
        except Exception as e:
            logger.warning(f"Failed to publish booking event: {e}")
    
    @staticmethod
    def _send_booking_confirmation(booking):
        """Send booking confirmation email (async)."""
        try:
            from notifications.tasks import send_booking_confirmation_email
            send_booking_confirmation_email.delay(booking.id)
        except Exception as e:
            logger.warning(f"Failed to send booking confirmation: {e}")
        
        # Also notify the property owner
        BookingService._send_owner_notification(booking, 'property')
    
    @staticmethod
    def _send_owner_notification(booking, booking_type='property'):
        """Send notification to listing owner when booking is made (async)."""
        try:
            from notifications.tasks import send_owner_booking_notification
            send_owner_booking_notification.delay(booking.id, booking_type)
        except Exception as e:
            logger.warning(f"Failed to send owner notification: {e}")
    
    @staticmethod
    def _send_confirmation_notification(booking):
        """Send booking confirmed notification (async)."""
        try:
            from notifications.tasks import send_booking_confirmed_email
            send_booking_confirmed_email.delay(booking.id)
        except Exception as e:
            logger.warning(f"Failed to send confirmed notification: {e}")
    
    @staticmethod
    def _send_cancellation_notification(booking):
        """Send booking cancellation notification (async)."""
        try:
            from notifications.tasks import send_booking_cancelled_email
            send_booking_cancelled_email.delay(booking.id)
        except Exception as e:
            logger.warning(f"Failed to send cancellation notification: {e}")
    
    @staticmethod
    def expire_pending_bookings(minutes=30):
        """
        Expire old pending bookings.

        When payment is disabled, this task becomes a no-op so pending bookings
        can stay open for manual host/approver workflows.
        
        Called by scheduled Celery task.
        
        Args:
            minutes: Minutes old for pending bookings to expire
        
        Returns:
            Number of bookings expired
        """
        if not getattr(settings, 'BOOKING_REQUIRE_PAYMENT', False):
            logger.info("Skipping pending booking expiration because payment is disabled.")
            return 0

        bookings = BookingRepository.get_pending_expiring_bookings(minutes=minutes)
        expired_count = 0
        
        for booking in bookings:
            try:
                BookingRepository.update_booking_status(
                    booking.id,
                    'cancelled',
                    reason='Auto-expired: Payment not received'
                )
                record_booking_cancelled()
                expired_count += 1
            except Exception as e:
                logger.error(f"Failed to expire booking {booking.id}: {e}")
        
        logger.info(f"Expired {expired_count} pending bookings")
        return expired_count


# Singleton-like service instance
_booking_service = None


def get_booking_service():
    """Get or create booking service instance."""
    global _booking_service
    if _booking_service is None:
        _booking_service = BookingService()
    return _booking_service
