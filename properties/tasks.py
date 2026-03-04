"""
properties/tasks.py - Celery Background Tasks for Properties

Asynchronous tasks for:
- Admin notification on property submission
- Owner confirmation emails
- Approval/rejection notifications
- Image processing and CDN upload
- Property analytics
"""

import logging
from urllib.parse import urljoin

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


def _build_absolute_uri(path: str) -> str:
    """Build absolute URL from path."""
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


def _get_admin_emails() -> list:
    """Get list of admin notification emails."""
    emails = set()
    
    # Primary admin
    primary_admin = getattr(settings, 'PROPERTY_ADMIN_EMAIL', 'marvelsafari@gmail.com')
    if primary_admin:
        emails.add(primary_admin)
    
    # Configured notification email
    contact_email = getattr(settings, 'CONTACT_NOTIFY_EMAIL', None)
    if contact_email:
        emails.add(contact_email)
    
    # Default from email as fallback
    default_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    if default_email and not emails:
        emails.add(default_email)
    
    return list(emails)


def _safe_send_mail(subject: str, message: str, recipient_list: list, html_message: str = None):
    """Send email with error handling."""
    if not recipient_list:
        logger.warning("No recipients for email: %s", subject)
        return False
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
        logger.info("Email sent: %s to %s", subject, recipient_list)
        return True
    except Exception as e:
        logger.exception("Failed to send email: %s - %s", subject, e)
        return False


# ============================================================================
# SUBMISSION NOTIFICATIONS
# ============================================================================

@shared_task(bind=True, max_retries=3, time_limit=120)
def notify_admin_property_submitted(self, property_id: str):
    """
    Notify admins when a property is submitted for review.
    
    Args:
        property_id: UUID of the submitted property
    """
    try:
        from properties.models import Property
        
        try:
            property_obj = Property.objects.select_related('owner', 'property_type').get(id=property_id)
        except Property.DoesNotExist:
            logger.warning("Property %s not found for admin notification", property_id)
            return {'status': 'skipped', 'reason': 'property_not_found'}
        
        owner_name = property_obj.owner.get_full_name() if property_obj.owner else 'Unknown'
        owner_email = property_obj.owner.email if property_obj.owner else 'N/A'
        
        # Build admin review URL
        admin_url = _build_absolute_uri(
            reverse('admin:properties_property_change', args=[property_id])
        )
        
        subject = f"[ACTION REQUIRED] New property submission: {property_obj.name}"
        
        message = f"""
A new property has been submitted for review.

PROPERTY DETAILS
================
Name: {property_obj.name}
Type: {property_obj.property_type.name if property_obj.property_type else 'N/A'}
Location: {property_obj.city}, {property_obj.country.name if property_obj.country else 'N/A'}
Address: {property_obj.address}

OWNER DETAILS
=============
Name: {owner_name}
Email: {owner_email}

PRICING
=======
Minimum: {property_obj.minimum_price or 'Not set'}
Maximum: {property_obj.maximum_price or 'Not set'}

ACTION REQUIRED
===============
Please review this property and approve or reject it.

Admin Panel: {admin_url}

---
This is an automated notification from the property management system.
"""
        
        admin_emails = _get_admin_emails()
        success = _safe_send_mail(subject, message, admin_emails)
        
        return {'status': 'sent' if success else 'failed', 'recipients': admin_emails}
        
    except Exception as exc:
        logger.exception("Error notifying admins about property %s", property_id)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3, time_limit=120)
def send_owner_submission_confirmation(self, property_id: str):
    """
    Send confirmation email to owner after property submission.
    
    Args:
        property_id: UUID of the submitted property
    """
    try:
        from properties.models import Property
        
        try:
            property_obj = Property.objects.select_related('owner').get(id=property_id)
        except Property.DoesNotExist:
            logger.warning("Property %s not found for owner confirmation", property_id)
            return {'status': 'skipped', 'reason': 'property_not_found'}
        
        if not property_obj.owner or not property_obj.owner.email:
            logger.warning("Property %s has no owner email", property_id)
            return {'status': 'skipped', 'reason': 'no_owner_email'}
        
        owner = property_obj.owner
        property_url = _build_absolute_uri(
            reverse('properties:detail', args=[property_obj.slug])
        )
        
        subject = f"Property submission received: {property_obj.name}"
        
        message = f"""
Dear {owner.get_full_name() or owner.email},

Thank you for submitting your property listing!

SUBMISSION DETAILS
==================
Property: {property_obj.name}
Location: {property_obj.city}, {property_obj.country.name if property_obj.country else 'N/A'}
Status: Pending Review

WHAT HAPPENS NEXT?
==================
1. Our team will review your listing within 24-48 business hours.
2. You'll receive an email once your property is approved or if we need more information.
3. Once approved, your property will be visible to travelers worldwide.

TIPS FOR QUICK APPROVAL
=======================
- Ensure all images are high quality and accurate
- Provide detailed descriptions
- Set competitive pricing
- Complete all required fields

If you have questions, please contact us at {getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL)}.

Best regards,
The Property Team
"""
        
        success = _safe_send_mail(subject, message, [owner.email])
        
        return {'status': 'sent' if success else 'failed', 'recipient': owner.email}
        
    except Exception as exc:
        logger.exception("Error sending submission confirmation for property %s", property_id)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# ============================================================================
# APPROVAL/REJECTION NOTIFICATIONS
# ============================================================================

@shared_task(bind=True, max_retries=3, time_limit=120)
def send_property_approved_email(self, property_id: str):
    """
    Send approval notification to property owner.
    
    Args:
        property_id: UUID of the approved property
    """
    try:
        from properties.models import Property
        
        try:
            property_obj = Property.objects.select_related('owner').get(id=property_id)
        except Property.DoesNotExist:
            logger.warning("Property %s not found for approval notification", property_id)
            return {'status': 'skipped', 'reason': 'property_not_found'}
        
        if not property_obj.owner or not property_obj.owner.email:
            return {'status': 'skipped', 'reason': 'no_owner_email'}
        
        owner = property_obj.owner
        property_url = _build_absolute_uri(
            reverse('properties:detail', args=[property_obj.slug])
        )
        dashboard_url = _build_absolute_uri('/dashboard/properties/')
        
        subject = f"Congratulations! Your property has been approved: {property_obj.name}"
        
        message = f"""
Dear {owner.get_full_name() or owner.email},

Great news! Your property listing has been approved and is now LIVE!

PROPERTY DETAILS
================
Property: {property_obj.name}
Location: {property_obj.city}, {property_obj.country.name if property_obj.country else 'N/A'}
Status: Approved & Published

VIEW YOUR LISTING
=================
Public URL: {property_url}
Dashboard: {dashboard_url}

NEXT STEPS
==========
1. Share your listing on social media to attract guests
2. Respond promptly to booking inquiries
3. Keep your calendar and pricing up to date
4. Provide great hospitality for positive reviews

TIPS FOR SUCCESS
================
- Fast response times lead to more bookings
- Professional photos increase visibility
- Competitive pricing attracts more guests

Welcome to our host community!

Best regards,
The Property Team
"""
        
        success = _safe_send_mail(subject, message, [owner.email])
        
        return {'status': 'sent' if success else 'failed', 'recipient': owner.email}
        
    except Exception as exc:
        logger.exception("Error sending approval notification for property %s", property_id)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3, time_limit=120)
def send_property_rejected_email(self, property_id: str, reason: str):
    """
    Send rejection notification to property owner with reason.
    
    Args:
        property_id: UUID of the rejected property
        reason: Rejection reason from admin
    """
    try:
        from properties.models import Property
        
        try:
            property_obj = Property.objects.select_related('owner').get(id=property_id)
        except Property.DoesNotExist:
            logger.warning("Property %s not found for rejection notification", property_id)
            return {'status': 'skipped', 'reason': 'property_not_found'}
        
        if not property_obj.owner or not property_obj.owner.email:
            return {'status': 'skipped', 'reason': 'no_owner_email'}
        
        owner = property_obj.owner
        edit_url = _build_absolute_uri(
            reverse('properties:edit', args=[property_obj.slug])
        )
        support_email = getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL)
        
        subject = f"Action needed: Property listing requires changes - {property_obj.name}"
        
        message = f"""
Dear {owner.get_full_name() or owner.email},

Thank you for your property submission. After review, we found some issues that need to be addressed before we can approve your listing.

PROPERTY DETAILS
================
Property: {property_obj.name}
Location: {property_obj.city}, {property_obj.country.name if property_obj.country else 'N/A'}
Status: Requires Changes

REASON FOR REJECTION
====================
{reason}

HOW TO FIX THIS
===============
1. Click the link below to edit your property
2. Address the issues mentioned above
3. Resubmit for review

Edit Your Property: {edit_url}

NEED HELP?
==========
If you have questions about the rejection reason or need assistance, please contact us at {support_email}.

We look forward to approving your property soon!

Best regards,
The Property Team
"""
        
        success = _safe_send_mail(subject, message, [owner.email])
        
        return {'status': 'sent' if success else 'failed', 'recipient': owner.email}
        
    except Exception as exc:
        logger.exception("Error sending rejection notification for property %s", property_id)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# ============================================================================
# IMAGE PROCESSING
# ============================================================================

@shared_task(bind=True, max_retries=2, time_limit=300)
def process_property_image(self, image_id: str):
    """
    Process and optimize property image.
    
    Operations:
    - Compress image
    - Generate thumbnails
    - Prepare for CDN upload
    
    Args:
        image_id: UUID of the PropertyImage
    """
    try:
        from properties.models import PropertyImage
        from PIL import Image
        import io
        
        try:
            property_image = PropertyImage.objects.get(id=image_id)
        except PropertyImage.DoesNotExist:
            logger.warning("PropertyImage %s not found for processing", image_id)
            return {'status': 'skipped', 'reason': 'image_not_found'}
        
        if not property_image.image:
            return {'status': 'skipped', 'reason': 'no_image_file'}
        
        # Open image
        img = Image.open(property_image.image)
        
        # Convert to RGB if necessary (for JPEG)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Resize if too large (max 2048px on longest side)
        max_dimension = 2048
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            new_size = tuple(int(dim * ratio) for dim in img.size)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Save optimized image
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        
        # Save back to field
        from django.core.files.base import ContentFile
        filename = property_image.image.name.rsplit('/', 1)[-1]
        if not filename.endswith('.jpg'):
            filename = filename.rsplit('.', 1)[0] + '.jpg'
        
        property_image.image.save(filename, ContentFile(output.read()), save=True)
        
        logger.info("Processed image %s successfully", image_id)
        return {'status': 'processed', 'image_id': image_id}
        
    except Exception as exc:
        logger.exception("Error processing image %s", image_id)
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# ANALYTICS
# ============================================================================

@shared_task(max_retries=2, time_limit=60)
def log_property_event(property_id: str, event_type: str, data: dict = None):
    """
    Log property events for analytics.
    
    Args:
        property_id: UUID of property
        event_type: Type of event (e.g., 'created', 'approved', 'viewed')
        data: Additional event data
    """
    try:
        logger.info(
            "Property event: %s - %s - %s",
            property_id,
            event_type,
            data or {}
        )
        
        # Here you would integrate with analytics service
        # e.g., send to analytics database, Mixpanel, Segment, etc.
        
        return {'status': 'logged', 'event_type': event_type}
        
    except Exception as e:
        logger.exception("Error logging property event: %s", e)
        return {'status': 'failed', 'error': str(e)}


# ============================================================================
# CLEANUP TASKS
# ============================================================================

@shared_task(bind=True, max_retries=2, time_limit=600)
def cleanup_orphaned_images(self):
    """
    Clean up orphaned property images (no associated property).
    
    Run periodically to free storage.
    """
    try:
        from properties.models import PropertyImage
        
        # Find images with deleted properties
        orphaned = PropertyImage.objects.filter(property__is_deleted=True)
        count = orphaned.count()
        
        if count > 0:
            # Delete image files and records
            for image in orphaned:
                if image.image:
                    try:
                        image.image.delete(save=False)
                    except Exception as e:
                        logger.warning("Failed to delete image file: %s", e)
                image.delete()
            
            logger.info("Cleaned up %s orphaned images", count)
        
        return {'status': 'completed', 'cleaned': count}
        
    except Exception as exc:
        logger.exception("Error cleaning up orphaned images")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=2, time_limit=600)
def expire_stale_drafts(self, days: int = 90):
    """
    Notify owners about stale draft properties.
    
    Args:
        days: Number of days after which drafts are considered stale
    """
    try:
        from properties.models import Property, PropertyStatus
        from datetime import timedelta
        
        cutoff = timezone.now() - timedelta(days=days)
        
        stale_drafts = Property.objects.filter(
            status=PropertyStatus.DRAFT,
            is_deleted=False,
            updated_at__lt=cutoff
        ).select_related('owner')
        
        notified = 0
        for prop in stale_drafts:
            if prop.owner and prop.owner.email:
                # Send reminder email
                edit_url = _build_absolute_uri(
                    reverse('properties:edit', args=[prop.slug])
                )
                
                subject = f"Complete your property listing: {prop.name}"
                message = f"""
Your property listing "{prop.name}" has been in draft status for over {days} days.

Complete your listing to start receiving bookings: {edit_url}

If you no longer wish to list this property, you can delete it from your dashboard.
"""
                _safe_send_mail(subject, message, [prop.owner.email])
                notified += 1
        
        logger.info("Notified %s owners about stale drafts", notified)
        return {'status': 'completed', 'notified': notified}
        
    except Exception as exc:
        logger.exception("Error processing stale drafts")
        raise self.retry(exc=exc, countdown=300)
