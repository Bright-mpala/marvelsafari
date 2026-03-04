"""Automatic hooks that enrich booking objects with AI insights.

IMPORTANT: All AI operations are dispatched to Celery tasks to avoid
blocking the request/response cycle. Never make synchronous AI calls here.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from bookings.models import Booking

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Booking)
def analyze_booking_special_requests(sender, instance: Booking, created: bool, **kwargs):
    """
    Queue AI analysis when a booking is created or updated with special requests.
    
    This is non-blocking - the actual AI call happens in a Celery task.
    """
    if not instance.special_requests and not created:
        return
    
    # Import here to avoid circular imports
    from .tasks import analyze_booking_async
    
    # Dispatch to Celery - non-blocking
    try:
        analyze_booking_async.delay(
            booking_id=instance.pk,
            user_id=instance.user_id if instance.user else None,
        )
        logger.debug('Queued AI analysis for booking %s', instance.pk)
    except Exception as exc:
        # Don't break the booking flow if Celery is unavailable
        logger.warning('Failed to queue AI analysis for booking %s: %s', instance.pk, exc)
