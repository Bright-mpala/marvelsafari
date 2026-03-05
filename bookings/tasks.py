"""
bookings/tasks.py - Celery background tasks for bookings

Asynchronous tasks for:
- Booking expiration
- Email notifications
- Event publishing
- Analytics logging
"""

from celery import shared_task
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, time_limit=300)
def expire_pending_bookings(self, minutes=30):
    """
    Background task to expire old pending bookings.
    
    Called every 5 minutes by Celery Beat.
    Auto-cancels bookings that haven't been paid for when payment is enabled.
    """
    if not getattr(settings, 'BOOKING_REQUIRE_PAYMENT', False):
        logger.info("Skipping expire_pending_bookings task because payment is disabled.")
        return {'status': 'skipped', 'reason': 'payment_disabled'}

    try:
        from bookings.services import BookingService
        service = BookingService()
        expired_count = service.expire_pending_bookings(minutes=minutes)
        logger.info(f"Expired {expired_count} pending bookings")
        return {'status': 'success', 'expired_count': expired_count}
    
    except Exception as e:
        logger.error(f"Error expiring pending bookings: {e}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3, time_limit=300)
def send_booking_reminders(self):
    """
    Background task to send booking reminders.
    
    Called daily by Celery Beat.
    Sends reminders for upcoming bookings.
    """
    try:
        from bookings.models import Booking
        from notifications.tasks import send_booking_reminder_email
        from django.utils import timezone
        from datetime import timedelta
        
        # Get bookings for next 3 days
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        in_three_days = (timezone.now() + timedelta(days=3)).date()
        
        upcoming_bookings = Booking.objects.filter(
            status='confirmed',
            check_in_date__gte=tomorrow,
            check_in_date__lte=in_three_days
        ).select_related('user')
        
        sent_count = 0
        for booking in upcoming_bookings:
            try:
                send_booking_reminder_email.delay(booking.id)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send reminder for booking {booking.id}: {e}")
        
        logger.info(f"Sent {sent_count} booking reminders")
        return {'status': 'success', 'sent_count': sent_count}
    
    except Exception as e:
        logger.error(f"Error sending booking reminders: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3, time_limit=120)
def publish_booking_event(self, booking_id, event_type):
    """
    Publish booking events for external systems/analytics.
    
    Args:
        booking_id: UUID of booking
        event_type: Type of event (booking.created, booking.confirmed, etc.)
    """
    try:
        from bookings.models import Booking
        from analytics.tasks import log_booking_event
        
        booking = Booking.objects.select_related('user', 'property').get(id=booking_id)
        
        # Log to analytics
        log_booking_event.delay(
            booking_id=str(booking.id),
            user_id=str(booking.user.id),
            property_id=str(booking.property.id),
            event_type=event_type,
            amount=float(booking.total_amount)
        )
        
        logger.info(f"Published event: {event_type} for booking {booking_id}")
        return {'status': 'published', 'event_type': event_type}
    
    except Exception as e:
        logger.error(f"Error publishing booking event: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=30)


@shared_task(max_retries=3, time_limit=60)
def complete_booking_task(booking_id):
    """
    Mark booking as completed (called after checkout date passes).
    
    Args:
        booking_id: UUID of booking
    """
    try:
        from bookings.models import Booking
        
        booking = Booking.objects.get(id=booking_id)
        if booking.status == 'confirmed' and booking.check_out_date <= timezone.now().date():
            booking.status = 'completed'
            booking.save()
            logger.info(f"Completed booking {booking_id}")
            return {'status': 'completed'}
        return {'status': 'skipped', 'reason': 'Not eligible for completion'}
    
    except Exception as e:
        logger.error(f"Error completing booking {booking_id}: {e}", exc_info=True)
        raise


@shared_task(max_retries=2, time_limit=60)
def send_review_reminder(booking_id):
    """
    Send review reminder after booking completion.
    
    Args:
        booking_id: UUID of booking
    """
    try:
        from bookings.models import Booking
        from notifications.tasks import send_review_reminder_email
        
        booking = Booking.objects.select_related('user', 'property').get(id=booking_id)
        
        # Check if booking is completed and no review exists
        if booking.status == 'completed':
            from reviews.models import Review
            if not Review.objects.filter(booking=booking).exists():
                send_review_reminder_email.delay(booking.id)
                logger.info(f"Sent review reminder for booking {booking_id}")
                return {'status': 'reminder_sent'}
        
        return {'status': 'skipped'}
    
    except Exception as e:
        logger.error(f"Error sending review reminder for {booking_id}: {e}")
        raise
