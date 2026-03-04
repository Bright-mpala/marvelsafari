import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Property, PropertyStatus

logger = logging.getLogger(__name__)


def _safe_send_mail(subject, message, recipient_list):
    if not recipient_list:
        return
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
    except Exception:
        logger.exception("Failed to send property notification email")


def _get_admin_recipients():
    primary_admin = getattr(settings, 'PROPERTY_ADMIN_EMAIL', 'marvelsafari@gmail.com')
    contact_email = getattr(settings, 'CONTACT_NOTIFY_EMAIL', None)
    default_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)

    recipients = {email for email in (primary_admin, contact_email, default_email) if email}
    return sorted(recipients)


def _format_location(instance: Property) -> str:
    city = (instance.city or '').strip()
    try:
        country = instance.country.name if instance.country else ''
    except AttributeError:
        country = str(instance.country) if instance.country else ''

    if city and country:
        return f"{city}, {country}"
    return city or country or 'N/A'


def _notify_admin_property_submitted(instance: Property):
    recipients = _get_admin_recipients()
    if not recipients:
        return

    owner_email = getattr(instance.owner, 'email', '') or instance.email or 'N/A'
    subject = f"New property submitted: {instance.name}"
    message = (
        "A new property listing has been submitted and is awaiting review.\n\n"
        f"Property: {instance.name}\n"
        f"Owner: {owner_email}\n"
        f"Location: {_format_location(instance)}\n"
        f"Status: {instance.status}\n"
    )
    _safe_send_mail(subject, message, recipients)


def _notify_owner_submission_received(instance: Property):
    recipients = {
        getattr(instance.owner, 'email', None),
        instance.email,
    }
    recipients = sorted({email for email in recipients if email})
    if not recipients:
        return

    subject = f"Property received: {instance.name}"
    message = (
        "We received your property listing and will review it shortly.\n\n"
        f"Property: {instance.name}\n"
        f"Location: {_format_location(instance)}\n"
    )
    _safe_send_mail(subject, message, recipients)


def _notify_owner_property_approved(instance: Property):
    recipients = {
        getattr(instance.owner, 'email', None),
        instance.email,
    }
    recipients = sorted({email for email in recipients if email})
    if not recipients:
        return

    subject = f"Property approved: {instance.name}"
    message = (
        "Your property listing has been approved and is now live.\n\n"
        f"Property: {instance.name}\n"
        f"Location: {_format_location(instance)}\n"
    )
    _safe_send_mail(subject, message, recipients)


def _notify_admin_property_approved(instance: Property):
    recipients = _get_admin_recipients()
    if not recipients:
        return

    subject = f"Property approved and published: {instance.name}"
    message = (
        "A property listing has been approved and published.\n\n"
        f"Property: {instance.name}\n"
        f"Owner: {getattr(getattr(instance, 'owner', None), 'email', 'N/A')}\n"
        f"Location: {_format_location(instance)}\n"
        f"Status: {instance.status}\n"
    )
    _safe_send_mail(subject, message, recipients)


@receiver(pre_save, sender=Property)
def property_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return

    previous = Property.objects.filter(pk=instance.pk).values('status').first()
    if previous:
        instance._previous_status = previous['status']
    else:
        instance._previous_status = None


@receiver(post_save, sender=Property)
def property_post_save(sender, instance, created, **kwargs):
    if created:
        if instance.status == PropertyStatus.PENDING:
            _notify_admin_property_submitted(instance)
            _notify_owner_submission_received(instance)
        return

    previous_status = getattr(instance, '_previous_status', None)
    current_status = instance.status

    if (
        current_status == PropertyStatus.PENDING and
        previous_status != PropertyStatus.PENDING
    ):
        _notify_admin_property_submitted(instance)
        _notify_owner_submission_received(instance)

    approval_statuses = {PropertyStatus.APPROVED, PropertyStatus.ACTIVE}
    if current_status in approval_statuses and previous_status not in approval_statuses:
        if not instance.verification_date or not instance.published_at:
            now = timezone.now()
            if not instance.verification_date:
                instance.verification_date = now
            if not instance.published_at:
                instance.published_at = now
            Property.objects.filter(pk=instance.pk).update(
                verification_date=instance.verification_date,
                published_at=instance.published_at,
            )

        _notify_owner_property_approved(instance)
        _notify_admin_property_approved(instance)
