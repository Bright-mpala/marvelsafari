import logging
from datetime import timedelta
from urllib.parse import urljoin

from celery import shared_task
from django.conf import settings
from django.contrib.sites.models import Site
from django.urls import reverse
from django.utils import timezone

from .services import EmailTemplateService

logger = logging.getLogger(__name__)


def _build_absolute_uri(path: str) -> str:
    base_url = getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/')
    if not base_url:
        try:
            site = Site.objects.get_current()
            domain = site.domain or 'localhost:8000'
        except Exception:
            domain = 'localhost:8000'
        scheme = 'https' if getattr(settings, 'USE_HTTPS', False) else 'http'
        base_url = f"{scheme}://{domain}"
    return urljoin(f"{base_url}/", path.lstrip('/'))


def _default_support_email() -> str:
    return getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL)


def _booking_context(booking) -> dict:
    listing = booking.property or booking.car or booking.tour
    destination_parts = []
    if getattr(listing, 'city', None):
        destination_parts.append(listing.city)
    country = getattr(getattr(listing, 'country', None), 'name', None)
    if country:
        destination_parts.append(country)
    destination = ', '.join(destination_parts) or 'your destination'

    booking_path = reverse('bookings:detail', args=[booking.pk])
    manage_booking_url = _build_absolute_uri(booking_path)

    return {
        'user_name': booking.user.get_full_name() or booking.user.email or 'Traveler',
        'property_name': getattr(listing, 'name', 'your stay'),
        'destination': destination,
        'check_in_date': booking.check_in_date.strftime('%B %d, %Y'),
        'check_in_time': '14:00',
        'guests': booking.guests,
        'booking_reference': getattr(booking, 'booking_reference', None) or str(booking.id),
        'booking_total': f"${booking.total_amount}",
        'manage_booking_url': manage_booking_url,
        'support_email': _default_support_email(),
    }


def _review_context(booking) -> dict:
    review_path = reverse('reviews:review_create', args=[booking.pk])
    review_url = _build_absolute_uri(review_path)
    stay_date = booking.check_out_date.strftime('%B %d, %Y')

    return {
        'user_name': booking.user.get_full_name() or booking.user.email or 'Traveler',
        'property_name': getattr(booking.property, 'name', 'your stay'),
        'stay_date': stay_date,
        'review_url': review_url,
        'support_email': _default_support_email(),
    }


@shared_task(bind=True, max_retries=3, time_limit=120)
def send_booking_reminders(self):
    """Schedule reminder emails for bookings starting soon."""
    try:
        from bookings.models import Booking

        tomorrow = (timezone.now() + timedelta(days=1)).date()
        in_three_days = (timezone.now() + timedelta(days=3)).date()

        upcoming = Booking.objects.filter(
            status='confirmed',
            check_in_date__gte=tomorrow,
            check_in_date__lte=in_three_days,
        ).select_related('user', 'property', 'car', 'tour')

        count = 0
        for booking in upcoming:
            if booking.user.email:
                send_booking_reminder_email.delay(booking.id)
                count += 1

        logger.info("Queued %s booking reminder emails", count)
        return {'status': 'queued', 'count': count}
    except Exception as exc:
        logger.exception("Failed to enqueue booking reminders")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3, time_limit=120)
def send_booking_reminder_email(self, booking_id):
    """Send a single booking reminder email."""
    from bookings.models import Booking

    try:
        booking = Booking.objects.select_related('user', 'property', 'car', 'tour').get(id=booking_id)
    except Booking.DoesNotExist:
        logger.warning("Booking %s not found for reminder", booking_id)
        return {'status': 'missing'}

    if not booking.user.email:
        return {'status': 'skipped', 'reason': 'missing_email'}

    service = EmailTemplateService()
    context = _booking_context(booking)
    subject = f"Upcoming stay at {context['property_name']}"

    sent = service.send('booking_reminder', [booking.user.email], context, fallback_subject=subject)
    return {'status': 'sent' if sent else 'failed'}


@shared_task(bind=True, max_retries=3, time_limit=120)
def send_review_reminder_email(self, booking_id):
    """Send a review reminder after checkout."""
    from bookings.models import Booking

    try:
        booking = Booking.objects.select_related('user', 'property').get(id=booking_id)
    except Booking.DoesNotExist:
        logger.warning("Booking %s not found for review reminder", booking_id)
        return {'status': 'missing'}

    if not booking.user.email or not booking.property:
        return {'status': 'skipped', 'reason': 'missing_data'}

    service = EmailTemplateService()
    context = _review_context(booking)
    subject = f"Share your stay at {context['property_name']}"

    sent = service.send('review_reminder', [booking.user.email], context, fallback_subject=subject)
    return {'status': 'sent' if sent else 'failed'}


# =============================================================================
# OWNER NOTIFICATION TASKS
# =============================================================================

def _owner_booking_context(booking, owner, booking_type='property') -> dict:
    """Build context for owner notification emails."""
    guest = booking.user
    guest_name = guest.get_full_name() or guest.email or 'Guest'
    
    if booking_type == 'property':
        listing_name = getattr(booking.property, 'name', 'Your property')
        date_info = f"{booking.check_in_date.strftime('%B %d, %Y')} - {booking.check_out_date.strftime('%B %d, %Y')}"
        guests_count = getattr(booking, 'guests', 1)
        amount = booking.total_amount
    elif booking_type == 'car':
        listing_name = f"{booking.car.make} {booking.car.model}" if booking.car else 'Your car'
        date_info = f"{booking.pickup_date.strftime('%B %d, %Y')} - {booking.dropoff_date.strftime('%B %d, %Y')}"
        guests_count = 1
        amount = booking.total_amount
    elif booking_type == 'taxi':
        listing_name = f"{booking.car.make} {booking.car.model}" if booking.car else 'Your taxi'
        date_info = booking.pickup_datetime.strftime('%B %d, %Y at %H:%M') if booking.pickup_datetime else 'TBD'
        guests_count = getattr(booking, 'passengers', 1)
        amount = booking.total_fare
    elif booking_type == 'tour':
        listing_name = getattr(booking.tour, 'name', 'Your tour')
        date_info = booking.tour_date.strftime('%B %d, %Y') if hasattr(booking, 'tour_date') and booking.tour_date else 'TBD'
        guests_count = getattr(booking, 'number_of_guests', 1)
        amount = booking.total_price
    else:
        listing_name = 'Your listing'
        date_info = 'TBD'
        guests_count = 1
        amount = 0

    booking_ref = getattr(booking, 'booking_reference', None) or str(booking.id)
    dashboard_url = _build_absolute_uri(reverse('accounts:dashboard'))

    return {
        'owner_name': owner.get_full_name() or owner.email or 'Host',
        'guest_name': guest_name,
        'guest_email': guest.email,
        'guest_phone': getattr(guest, 'phone_number', '') or '',
        'listing_name': listing_name,
        'booking_type': booking_type.title(),
        'date_info': date_info,
        'guests_count': guests_count,
        'booking_amount': f"${amount}" if amount else 'TBD',
        'booking_reference': booking_ref,
        'dashboard_url': dashboard_url,
        'support_email': _default_support_email(),
    }


@shared_task(bind=True, max_retries=3, time_limit=120)
def send_owner_booking_notification(self, booking_id, booking_type='property'):
    """Send email notification to owner when a booking is made."""
    try:
        if booking_type == 'property':
            from bookings.models import Booking
            booking = Booking.objects.select_related('user', 'property', 'property__owner').get(id=booking_id)
            owner = booking.property.owner if booking.property else None
        elif booking_type == 'car':
            from car_rentals.models import CarRentalBooking
            booking = CarRentalBooking.objects.select_related('user', 'car', 'car__owner').get(id=booking_id)
            owner = booking.car.owner if booking.car else None
        elif booking_type == 'taxi':
            from car_rentals.models import TaxiBooking
            booking = TaxiBooking.objects.select_related('user', 'car', 'car__owner').get(id=booking_id)
            owner = booking.car.owner if booking.car else None
        elif booking_type == 'tour':
            from tours.models import TourBooking
            booking = TourBooking.objects.select_related('user', 'tour', 'tour__operator').get(id=booking_id)
            operator = booking.tour.operator if booking.tour else None
            owner = operator.user if operator and hasattr(operator, 'user') else None
        else:
            logger.warning("Unknown booking type: %s", booking_type)
            return {'status': 'failed', 'reason': 'unknown_type'}

        if not owner or not owner.email:
            logger.info("No owner email for %s booking %s", booking_type, booking_id)
            return {'status': 'skipped', 'reason': 'no_owner_email'}

        service = EmailTemplateService()
        context = _owner_booking_context(booking, owner, booking_type)
        
        subject = f"New {booking_type.title()} Booking: {context['listing_name']}"
        
        # Try template first, fall back to plain email
        sent = service.send('owner_new_booking', [owner.email], context, fallback_subject=subject)
        
        if not sent:
            # Fallback: send plain text email
            from django.core.mail import send_mail
            plain_message = f"""
Hi {context['owner_name']},

Great news! You have a new booking for {context['listing_name']}.

Booking Details:
- Reference: {context['booking_reference']}
- Guest: {context['guest_name']} ({context['guest_email']})
- Dates: {context['date_info']}
- Guests: {context['guests_count']}
- Amount: {context['booking_amount']}

Log in to your dashboard to view and manage this booking:
{context['dashboard_url']}

Best regards,
Marvel Safari Team
"""
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [owner.email],
                fail_silently=True
            )
            sent = True

        logger.info("Owner notification sent for %s booking %s to %s", booking_type, booking_id, owner.email)
        return {'status': 'sent' if sent else 'failed'}

    except Exception as exc:
        logger.exception("Failed to send owner notification for %s booking %s", booking_type, booking_id)
        raise self.retry(exc=exc, countdown=60)

