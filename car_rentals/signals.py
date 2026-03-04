import logging
from datetime import datetime

from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.template.loader import render_to_string

from notifications.models import Notification, NotificationType

from .models import Car, CarStatus, CarRentalBooking, TaxiBooking

logger = logging.getLogger(__name__)


def _safe_send_html_mail(subject, plain_message, html_message, recipients):
    """Send email with HTML content, falling back to plain text."""
    if not recipients:
        return
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            html_message=html_message,
            fail_silently=False,
        )
    except Exception:  # pragma: no cover - log only
        logger.exception("Failed to send car notification email")


def _push_in_app_notification(*, user, code: str, label: str, message: str, booking=None):
    if not user:
        return

    notification_type, _ = NotificationType.objects.get_or_create(
        code=code,
        defaults={
            'name': label,
            'channels': ['in_app'],
            'priority': 1,
            'default_enabled': True,
        },
    )

    Notification.objects.create(
        user=user,
        notification_type=notification_type,
        channel='in_app',
        subject=label,
        message=message,
        related_car_rental_booking=booking if isinstance(booking, CarRentalBooking) else None,
    )


@receiver(pre_save, sender=Car)
def car_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_moderation_status = None
        return

    previous = Car.objects.filter(pk=instance.pk).values('moderation_status').first()
    instance._previous_moderation_status = previous['moderation_status'] if previous else None


@receiver(post_save, sender=Car)
def car_post_save(sender, instance, created, **kwargs):
    if created:
        return

    previous_status = getattr(instance, '_previous_moderation_status', None)
    if previous_status != CarStatus.APPROVED and instance.moderation_status == CarStatus.APPROVED:
        recipients = set()
        if instance.owner and instance.owner.email:
            recipients.add(instance.owner.email)
        if instance.company and instance.company.email:
            recipients.add(instance.company.email)

        subject = f"Car approved: {instance.make} {instance.model}"
        
        # Plain text fallback
        plain_message = (
            "Good news! Compliance cleared your car and it is now visible to travelers.\n\n"
            f"Vehicle: {instance.make} {instance.model} ({instance.license_plate})\n"
            f"Service type: {instance.get_service_type_display()}\n"
            "MarvelSafari connects you with renters but does not cover mechanical issues or damages. Please keep your insurance active.\n"
        )
        
        # HTML email
        html_message = render_to_string('car_rentals/emails/car_approved.html', {
            'car': instance,
            'service_type': instance.get_service_type_display(),
            'dashboard_url': f"{settings.SITE_URL}/cars/my-listings/" if hasattr(settings, 'SITE_URL') else '/cars/my-listings/',
            'year': datetime.now().year,
        })
        
        _safe_send_html_mail(subject, plain_message, html_message, sorted(recipients))

        if instance.owner:
            _push_in_app_notification(
                user=instance.owner,
                code='car_listing_approved',
                label='Your car is live',
                message=f"{instance.make} {instance.model} is approved and ready for bookings. Keep insurance active — owners are responsible for damages.",
            )


@receiver(post_save, sender=CarRentalBooking)
def rental_booking_created(sender, instance, created, **kwargs):
    if not created:
        return

    car = instance.car
    recipients = []
    if car and car.owner and car.owner.email:
        recipients.append(car.owner.email)
    if car and car.company and car.company.email:
        recipients.append(car.company.email)

    if not recipients:
        return

    vehicle_label = f"{car.make} {car.model}" if car else instance.category.name
    traveler_name = instance.user.get_full_name() or instance.user.email
    traveler_email = instance.user.email
    traveler_initial = (traveler_name[0] if traveler_name else 'T').upper()
    
    subject = f"Your car was booked: {instance.booking_reference}"
    
    # Plain text fallback
    plain_message = (
        "A traveler just booked your car.\n\n"
        f"Booking: {instance.booking_reference}\n"
        f"Vehicle: {vehicle_label}\n"
        f"Pickup: {instance.pickup_date} {instance.pickup_time}\n"
        f"Dropoff: {instance.dropoff_date} {instance.dropoff_time}\n"
        f"Traveler: {traveler_name}\n"
        "Reminder: maintain valid insurance — MarvelSafari does not assume damage liability.\n"
    )
    
    # HTML email
    html_message = render_to_string('car_rentals/emails/car_rental_booking.html', {
        'booking': instance,
        'vehicle_label': vehicle_label,
        'traveler_name': traveler_name,
        'traveler_email': traveler_email,
        'traveler_initial': traveler_initial,
        'dashboard_url': f"{settings.SITE_URL}/cars/my-listings/" if hasattr(settings, 'SITE_URL') else '/cars/my-listings/',
        'year': datetime.now().year,
    })
    
    _safe_send_html_mail(subject, plain_message, html_message, recipients)

    if car and car.owner:
        window = f"{instance.pickup_date.strftime('%b %d')} → {instance.dropoff_date.strftime('%b %d')}"
        _push_in_app_notification(
            user=car.owner,
            code='car_rental_request_owner_alert',
            label='New rental request',
            message=f"{instance.user.get_full_name() or instance.user.email} wants {car.make} {car.model} for {window}.",
            booking=instance,
        )


@receiver(post_save, sender=TaxiBooking)
def taxi_booking_created(sender, instance, created, **kwargs):
    if not created:
        return

    car = instance.car
    recipients = []
    if car and car.owner and car.owner.email:
        recipients.append(car.owner.email)
    if car and car.company and car.company.email:
        recipients.append(car.company.email)

    if not recipients:
        return

    vehicle_label = f"{car.make} {car.model}" if car else 'Unassigned vehicle'
    subject = f"Your car was booked for a ride: {instance.booking_reference}"
    
    # Render HTML email template
    context = {
        'booking_reference': instance.booking_reference,
        'vehicle_label': vehicle_label,
        'pickup_address': instance.pickup_address,
        'dropoff_address': instance.dropoff_address,
        'passenger_name': instance.user.get_full_name() or instance.user.email,
        'year': datetime.now().year,
    }
    html_message = render_to_string('car_rentals/emails/taxi_booking.html', context)
    plain_message = (
        "A traveler booked your car for a taxi trip.\n\n"
        f"Booking: {instance.booking_reference}\n"
        f"Vehicle: {vehicle_label}\n"
        f"Pickup: {instance.pickup_address}\n"
        f"Dropoff: {instance.dropoff_address}\n"
        f"Passenger: {instance.user.get_full_name() or instance.user.email}\n"
        "Reminder: drivers and owners remain responsible for the vehicle condition; MarvelSafari is only the connector.\n"
    )
    _safe_send_html_mail(subject, plain_message, recipients, html_message)

    if car and car.owner:
        _push_in_app_notification(
            user=car.owner,
            code='car_taxi_request_owner_alert',
            label='Taxi trip requested',
            message=f"{instance.user.get_full_name() or instance.user.email} booked {car.make} {car.model} for a taxi trip starting at {instance.pickup_address}.",
        )
