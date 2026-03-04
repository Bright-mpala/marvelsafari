"""
properties/services.py - Service Layer for Property Management

Production-ready service layer handling:
- Property creation with atomic transactions
- Owner assignment and validation
- Status management (draft -> pending -> approved)
- Admin review workflow
- Notification triggers via Celery
- Image management with CDN preparation
- Redis caching integration
- Audit logging
"""

import logging
import uuid
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import User, UserRole
from core.exceptions import InvalidDataError, PermissionError as AppPermissionError
from core.models import AuditLogEntry

if TYPE_CHECKING:
    from properties.models import Property, PropertyImage

logger = logging.getLogger(__name__)


class PropertyService:
    """
    High-level service for property management operations.
    
    This service encapsulates all business logic for:
    - Creating properties (with automatic owner assignment)
    - Submitting properties for review
    - Admin approval/rejection workflow
    - Status transitions
    - Image management
    - Notification orchestration
    
    All write operations are wrapped in atomic transactions.
    Status changes are audit logged.
    """
    
    # Status that allows public visibility
    PUBLIC_STATUSES = frozenset(['approved', 'active'])
    
    # Status that allows editing by owner
    EDITABLE_STATUSES = frozenset(['draft', 'pending', 'rejected'])
    
    def __init__(self, request_user: Optional[User] = None, request_ip: Optional[str] = None):
        """
        Initialize service with request context.
        
        Args:
            request_user: User making the request (for audit logging)
            request_ip: IP address of request (for audit logging)
        """
        self.request_user = request_user
        self.request_ip = request_ip
    
    # =========================================================================
    # PROPERTY CREATION
    # =========================================================================
    
    @transaction.atomic
    def create_property(
        self,
        owner: User,
        name: str,
        description: str,
        property_type_id: int,
        address: str,
        city: str,
        country: str,
        postal_code: str = '',
        state: str = '',
        latitude: Decimal = None,
        longitude: Decimal = None,
        phone: str = '',
        email: str = '',
        minimum_price: Decimal = None,
        maximum_price: Decimal = None,
        amenity_ids: List[int] = None,
        save_as_draft: bool = True,
        **extra_fields
    ) -> 'Property':
        """
        Create a new property with full validation and security.
        
        This method:
        1. Validates user has HOST role
        2. Forces status to DRAFT or PENDING (never APPROVED)
        3. Generates unique slug
        4. Assigns owner
        5. Validates all business rules
        6. Creates property atomically
        7. Triggers admin notification asynchronously
        8. Logs creation to audit trail
        
        Args:
            owner: User who will own the property (must be HOST)
            name: Property name
            description: Property description
            property_type_id: ID of PropertyType
            address: Street address
            city: City name
            country: Country code
            postal_code: Postal/ZIP code
            state: State/province
            latitude: Geo latitude
            longitude: Geo longitude
            phone: Contact phone
            email: Contact email
            minimum_price: Min nightly rate
            maximum_price: Max nightly rate
            amenity_ids: List of amenity IDs
            save_as_draft: If True, save as DRAFT; if False, submit as PENDING
            **extra_fields: Additional property fields
            
        Returns:
            Property instance
            
        Raises:
            PermissionDenied: If user cannot create properties
            ValidationError: If validation fails
            InvalidDataError: If data is malformed
        """
        from properties.models import Property, PropertyType, Amenity, PropertyStatus
        from properties.validators import (
            validate_property_name,
            validate_property_description,
            validate_price,
            validate_price_range,
            validate_coordinates,
        )
        
        # 1. Verify owner has HOST role
        self._verify_host_permission(owner)
        
        # 2. Validate inputs
        validate_property_name(name)
        validate_property_description(description)
        
        if minimum_price:
            validate_price(minimum_price, 'minimum price')
        if maximum_price:
            validate_price(maximum_price, 'maximum price')
        validate_price_range(minimum_price, maximum_price)
        
        if latitude or longitude:
            validate_coordinates(latitude, longitude)
        
        # 3. Get property type
        try:
            property_type = PropertyType.objects.get(id=property_type_id, is_active=True)
        except PropertyType.DoesNotExist:
            raise InvalidDataError(
                message='Invalid property type',
                code='invalid_property_type'
            )
        
        # 4. Generate unique slug
        slug = self._generate_unique_slug(name)
        
        # 5. Force status (owners cannot set APPROVED)
        status = PropertyStatus.DRAFT if save_as_draft else PropertyStatus.PENDING
        
        # 6. Whitelist allowed extra fields (prevent overposting)
        allowed_extra_fields = {
            'check_in_time', 'check_out_time', 'earliest_check_in', 'latest_check_out',
            'manager_name', 'manager_phone', 'manager_email', 'website',
            'cancellation_policy', 'house_rules', 'special_instructions',
            'star_rating', 'total_rooms', 'year_built', 'year_renovated',
            'meta_title', 'meta_description', 'meta_keywords',
        }
        safe_extra = {k: v for k, v in extra_fields.items() if k in allowed_extra_fields}
        
        # 7. Create property atomically
        try:
            property_obj = Property.objects.create(
                owner=owner,
                name=name,
                slug=slug,
                description=description,
                property_type=property_type,
                address=address,
                city=city,
                country=country,
                postal_code=postal_code,
                state=state,
                latitude=latitude,
                longitude=longitude,
                phone=phone,
                email=email or owner.email,
                minimum_price=minimum_price,
                maximum_price=maximum_price,
                status=status,
                is_active=True,
                is_verified=False,
                is_featured=False,
                **safe_extra
            )
        except IntegrityError as e:
            logger.error(f"Property creation integrity error: {e}")
            raise InvalidDataError(
                message='Property creation failed due to data conflict',
                code='integrity_error'
            )
        
        # 8. Add amenities
        if amenity_ids:
            amenities = Amenity.objects.filter(id__in=amenity_ids, is_active=True)
            property_obj.amenities.set(amenities)
        
        # 9. Audit log
        self._log_audit(
            property_obj,
            action='create',
            changes={'status': status}
        )
        
        # 10. Send notifications asynchronously
        if status == PropertyStatus.PENDING:
            self._trigger_submission_notifications(property_obj)
        
        logger.info(
            f"Property created: {property_obj.id} by user {owner.id} "
            f"with status {status}"
        )
        
        return property_obj
    
    # =========================================================================
    # STATUS MANAGEMENT
    # =========================================================================
    
    @transaction.atomic
    def submit_for_review(self, property_obj: 'Property', user: User) -> 'Property':
        """
        Submit a draft property for admin review.
        
        Validates:
        - User owns the property
        - Property is in DRAFT or REJECTED status
        - Property has at least one image
        - All required fields are filled
        
        Args:
            property_obj: Property to submit
            user: User making the request
            
        Returns:
            Updated property
            
        Raises:
            PermissionDenied: If user doesn't own property
            ValidationError: If property fails validation
        """
        from properties.models import PropertyStatus
        from properties.validators import validate_property_for_submission
        
        # Verify ownership
        self._verify_property_ownership(property_obj, user)
        
        # Verify valid source status
        if property_obj.status not in {PropertyStatus.DRAFT, PropertyStatus.REJECTED}:
            raise ValidationError(
                f'Cannot submit property with status "{property_obj.status}". '
                'Only DRAFT or REJECTED properties can be submitted.'
            )
        
        # Comprehensive validation
        validate_property_for_submission(property_obj)
        
        # Update status
        old_status = property_obj.status
        property_obj.status = PropertyStatus.PENDING
        property_obj.rejection_reason = ''  # Clear previous rejection
        property_obj.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        
        # Audit log
        self._log_audit(
            property_obj,
            action='update',
            changes={'status': {'from': old_status, 'to': PropertyStatus.PENDING}}
        )
        
        # Trigger notifications
        self._trigger_submission_notifications(property_obj)
        
        logger.info(f"Property {property_obj.id} submitted for review by user {user.id}")
        
        return property_obj
    
    @transaction.atomic
    def approve_property(
        self,
        property_obj: 'Property',
        admin_user: User,
        notes: str = ''
    ) -> 'Property':
        """
        Approve a pending property (admin only).
        
        Args:
            property_obj: Property to approve
            admin_user: Admin user approving
            notes: Optional approval notes
            
        Returns:
            Updated property
            
        Raises:
            PermissionDenied: If user is not admin
            ValidationError: If property cannot be approved
        """
        from properties.models import PropertyStatus
        
        # Verify admin role
        self._verify_admin_permission(admin_user)
        
        if property_obj.status != PropertyStatus.PENDING:
            raise ValidationError(
                f'Only PENDING properties can be approved. Current status: {property_obj.status}'
            )
        
        old_status = property_obj.status
        now = timezone.now()
        
        property_obj.status = PropertyStatus.APPROVED
        property_obj.approved_by = admin_user
        property_obj.approved_at = now
        property_obj.is_verified = True
        property_obj.verification_date = now
        property_obj.published_at = now
        property_obj.rejection_reason = ''
        property_obj.save(update_fields=[
            'status', 'approved_by', 'approved_at', 'is_verified',
            'verification_date', 'published_at', 'rejection_reason', 'updated_at'
        ])
        
        # Audit log
        self._log_audit(
            property_obj,
            action='approve',
            changes={
                'status': {'from': old_status, 'to': PropertyStatus.APPROVED},
                'approved_by': str(admin_user.id),
                'notes': notes
            }
        )
        
        # Notify owner
        self._trigger_approval_notification(property_obj)
        
        logger.info(f"Property {property_obj.id} approved by admin {admin_user.id}")
        
        return property_obj
    
    @transaction.atomic
    def reject_property(
        self,
        property_obj: 'Property',
        admin_user: User,
        reason: str
    ) -> 'Property':
        """
        Reject a pending property with reason (admin only).
        
        Args:
            property_obj: Property to reject
            admin_user: Admin user rejecting
            reason: Required rejection reason
            
        Returns:
            Updated property
            
        Raises:
            PermissionDenied: If user is not admin
            ValidationError: If property cannot be rejected or reason missing
        """
        from properties.models import PropertyStatus
        
        # Verify admin role
        self._verify_admin_permission(admin_user)
        
        if not reason or not reason.strip():
            raise ValidationError('Rejection reason is required')
        
        if property_obj.status != PropertyStatus.PENDING:
            raise ValidationError(
                f'Only PENDING properties can be rejected. Current status: {property_obj.status}'
            )
        
        old_status = property_obj.status
        
        property_obj.status = PropertyStatus.REJECTED
        property_obj.rejection_reason = reason.strip()
        property_obj.approved_by = None
        property_obj.approved_at = None
        property_obj.save(update_fields=[
            'status', 'rejection_reason', 'approved_by', 'approved_at', 'updated_at'
        ])
        
        # Audit log
        self._log_audit(
            property_obj,
            action='reject',
            changes={
                'status': {'from': old_status, 'to': PropertyStatus.REJECTED},
                'rejected_by': str(admin_user.id),
                'reason': reason
            }
        )
        
        # Notify owner
        self._trigger_rejection_notification(property_obj, reason)
        
        logger.info(f"Property {property_obj.id} rejected by admin {admin_user.id}")
        
        return property_obj
    
    @transaction.atomic
    def deactivate_property(self, property_obj: 'Property', user: User) -> 'Property':
        """
        Deactivate an approved property (owner or admin).
        
        Args:
            property_obj: Property to deactivate
            user: User making request
            
        Returns:
            Updated property
        """
        from properties.models import PropertyStatus
        
        # Verify ownership or admin
        is_admin = self._is_admin(user)
        if not is_admin:
            self._verify_property_ownership(property_obj, user)
        
        if property_obj.status not in {PropertyStatus.APPROVED, PropertyStatus.ACTIVE}:
            raise ValidationError('Only approved/active properties can be deactivated')
        
        old_status = property_obj.status
        property_obj.status = PropertyStatus.INACTIVE
        property_obj.save(update_fields=['status', 'updated_at'])
        
        self._log_audit(
            property_obj,
            action='update',
            changes={'status': {'from': old_status, 'to': PropertyStatus.INACTIVE}}
        )
        
        return property_obj
    
    # =========================================================================
    # PROPERTY UPDATE
    # =========================================================================
    
    @transaction.atomic
    def update_property(
        self,
        property_obj: 'Property',
        user: User,
        **updates
    ) -> 'Property':
        """
        Update property with validation and security.
        
        Prevents overposting by whitelisting allowed fields.
        Status cannot be changed via this method.
        
        Args:
            property_obj: Property to update
            user: User making request
            **updates: Field updates
            
        Returns:
            Updated property
        """
        from properties.models import PropertyStatus
        from properties.validators import (
            validate_property_name,
            validate_property_description,
            validate_price,
            validate_price_range,
        )
        
        # Verify ownership (admins can also edit)
        is_admin = self._is_admin(user)
        if not is_admin:
            self._verify_property_ownership(property_obj, user)
        
        # Only allow editing in certain statuses
        if property_obj.status not in self.EDITABLE_STATUSES and not is_admin:
            raise ValidationError(
                f'Cannot edit property with status "{property_obj.status}". '
                'Contact support to make changes.'
            )
        
        # Whitelist allowed fields (prevent overposting)
        allowed_fields = {
            'name', 'description', 'address', 'city', 'state', 'postal_code', 'country',
            'latitude', 'longitude', 'phone', 'email', 'website',
            'check_in_time', 'check_out_time', 'earliest_check_in', 'latest_check_out',
            'minimum_price', 'maximum_price', 'manager_name', 'manager_phone', 'manager_email',
            'cancellation_policy', 'house_rules', 'special_instructions',
            'star_rating', 'total_rooms', 'year_built', 'year_renovated',
            'meta_title', 'meta_description', 'meta_keywords',
        }
        
        # Admin-only fields
        admin_fields = {'commission_rate', 'is_featured'}
        if is_admin:
            allowed_fields.update(admin_fields)
        
        # NEVER allow direct status/approval manipulation
        forbidden_fields = {
            'status', 'approved_by', 'approved_at', 'is_verified',
            'verification_date', 'published_at', 'owner', 'slug',
            'is_deleted', 'deleted_at', 'deleted_by',
            'view_count', 'booking_count', 'average_rating', 'review_count',
        }
        
        # Filter updates
        safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        blocked = [k for k in updates.keys() if k in forbidden_fields]
        
        if blocked:
            logger.warning(
                f"Blocked overposting attempt on property {property_obj.id}: {blocked}"
            )
        
        # Validate specific fields
        if 'name' in safe_updates:
            validate_property_name(safe_updates['name'])
        if 'description' in safe_updates:
            validate_property_description(safe_updates['description'])
        if 'minimum_price' in safe_updates:
            validate_price(safe_updates['minimum_price'], 'minimum price')
        if 'maximum_price' in safe_updates:
            validate_price(safe_updates['maximum_price'], 'maximum price')
        
        # Price range validation
        min_price = safe_updates.get('minimum_price', property_obj.minimum_price)
        max_price = safe_updates.get('maximum_price', property_obj.maximum_price)
        validate_price_range(min_price, max_price)
        
        # Apply updates
        changes = {}
        for field, value in safe_updates.items():
            old_value = getattr(property_obj, field)
            if old_value != value:
                changes[field] = {'from': str(old_value), 'to': str(value)}
                setattr(property_obj, field, value)
        
        if changes:
            property_obj.save()
            self._log_audit(property_obj, action='update', changes=changes)
            
        return property_obj
    
    # =========================================================================
    # IMAGE MANAGEMENT
    # =========================================================================
    
    @transaction.atomic
    def add_property_image(
        self,
        property_obj: 'Property',
        user: User,
        image_file,
        caption: str = '',
        alt_text: str = '',
        is_primary: bool = False
    ) -> 'PropertyImage':
        """
        Add an image to property with validation.
        
        Args:
            property_obj: Target property
            user: User adding image
            image_file: Uploaded image file
            caption: Image caption
            alt_text: Alt text for accessibility
            is_primary: Set as primary image
            
        Returns:
            PropertyImage instance
        """
        from properties.models import PropertyImage
        from properties.validators import validate_image_file, MAX_PROPERTY_IMAGES
        
        # Verify ownership
        self._verify_property_ownership(property_obj, user)
        
        # Check image count
        current_count = PropertyImage.objects.filter(property=property_obj).count()
        if current_count >= MAX_PROPERTY_IMAGES:
            raise ValidationError(
                f'Maximum of {MAX_PROPERTY_IMAGES} images allowed per property'
            )
        
        # Validate image
        validate_image_file(image_file)
        
        # Generate secure upload path
        upload_path = self._generate_image_upload_path(property_obj, image_file.name)
        
        # Handle primary image logic
        if is_primary:
            PropertyImage.objects.filter(property=property_obj).update(is_primary=False)
        elif current_count == 0:
            is_primary = True  # First image is always primary
        
        # Create image record
        property_image = PropertyImage.objects.create(
            property=property_obj,
            image=image_file,
            caption=caption[:255] if caption else '',
            alt_text=alt_text[:255] if alt_text else '',
            is_primary=is_primary,
            display_order=current_count
        )
        
        logger.info(f"Image added to property {property_obj.id} by user {user.id}")
        
        return property_image
    
    @transaction.atomic
    def delete_property_image(
        self,
        image: 'PropertyImage',
        user: User
    ) -> None:
        """
        Delete a property image.
        
        Args:
            image: PropertyImage to delete
            user: User making request
        """
        from properties.models import PropertyImage
        
        property_obj = image.property
        
        # Verify ownership
        self._verify_property_ownership(property_obj, user)
        
        was_primary = image.is_primary
        image.delete()
        
        # If deleted image was primary, set new primary
        if was_primary:
            next_image = PropertyImage.objects.filter(
                property=property_obj
            ).order_by('display_order', 'created_at').first()
            
            if next_image:
                next_image.is_primary = True
                next_image.save(update_fields=['is_primary'])
        
        logger.info(f"Image deleted from property {property_obj.id} by user {user.id}")
    
    @transaction.atomic
    def set_primary_image(
        self,
        image: 'PropertyImage',
        user: User
    ) -> 'PropertyImage':
        """
        Set an image as the primary image.
        
        Args:
            image: PropertyImage to set as primary
            user: User making request
            
        Returns:
            Updated PropertyImage
        """
        from properties.models import PropertyImage
        
        property_obj = image.property
        self._verify_property_ownership(property_obj, user)
        
        # Unset all other primary images
        PropertyImage.objects.filter(property=property_obj).update(is_primary=False)
        
        # Set this one as primary
        image.is_primary = True
        image.save(update_fields=['is_primary'])
        
        return image
    
    # =========================================================================
    # QUERY METHODS
    # =========================================================================
    
    def get_owner_properties(self, owner: User, include_deleted: bool = False):
        """
        Get all properties owned by a user.
        
        Args:
            owner: Property owner
            include_deleted: Include soft-deleted properties
            
        Returns:
            QuerySet of properties
        """
        from properties.models import Property
        
        queryset = Property.objects.filter(owner=owner)
        
        if not include_deleted:
            queryset = queryset.filter(is_deleted=False)
        
        return queryset.select_related('property_type').prefetch_related('images')
    
    def get_pending_properties(self):
        """
        Get all properties pending admin review.
        
        Returns:
            QuerySet of pending properties
        """
        from properties.models import Property, PropertyStatus
        
        return Property.objects.filter(
            status=PropertyStatus.PENDING,
            is_deleted=False
        ).select_related('owner', 'property_type').prefetch_related('images')
    
    def get_public_properties(self):
        """
        Get all publicly visible properties.
        
        Returns:
            QuerySet of public properties
        """
        from properties.models import Property, PropertyStatus
        
        return Property.objects.filter(
            status__in=[PropertyStatus.APPROVED, PropertyStatus.ACTIVE],
            is_deleted=False,
            is_active=True
        ).select_related('owner', 'property_type').prefetch_related('images', 'amenities')
    
    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================
    
    def _verify_host_permission(self, user: User) -> None:
        """Verify user can create properties (must be HOST role)."""
        if not user.is_authenticated:
            raise PermissionDenied('Authentication required')
        
        # Admins and superusers can always create
        if user.is_staff or user.is_superuser:
            return
        
        if user.role not in {UserRole.HOST, UserRole.ADMIN}:
            raise PermissionDenied(
                'Only hosts can create property listings. '
                'Please upgrade your account to host status.'
            )
    
    def _verify_admin_permission(self, user: User) -> None:
        """Verify user has admin privileges."""
        if not user.is_authenticated:
            raise PermissionDenied('Authentication required')
        
        if not (user.is_staff or user.is_superuser or user.role == UserRole.ADMIN):
            raise PermissionDenied('Admin privileges required')
    
    def _verify_property_ownership(self, property_obj: 'Property', user: User) -> None:
        """Verify user owns the property."""
        if property_obj.owner_id != user.id:
            raise PermissionDenied('You do not have permission to modify this property')
    
    def _is_admin(self, user: User) -> bool:
        """Check if user is admin."""
        return user.is_staff or user.is_superuser or user.role == UserRole.ADMIN
    
    def _generate_unique_slug(self, name: str, max_attempts: int = 100) -> str:
        """Generate a unique slug for property."""
        from properties.models import Property
        
        base_slug = slugify(name)[:250]  # Leave room for counter
        
        if not base_slug:
            base_slug = 'property'
        
        slug = base_slug
        counter = 1
        
        while Property.objects.filter(slug=slug).exists():
            if counter >= max_attempts:
                # Fallback to UUID suffix
                slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"
                break
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug
    
    def _generate_image_upload_path(self, property_obj: 'Property', filename: str) -> str:
        """
        Generate secure upload path for property images.
        
        Structure: properties/{owner_id}/{property_id}/{uuid}_{filename}
        """
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
        safe_filename = f"{uuid.uuid4().hex}.{ext}"
        
        owner_id = str(property_obj.owner_id) if property_obj.owner_id else 'system'
        property_id = str(property_obj.id)
        
        return f"properties/{owner_id}/{property_id}/{safe_filename}"
    
    def _log_audit(
        self,
        property_obj: 'Property',
        action: str,
        changes: Dict[str, Any]
    ) -> None:
        """Log action to audit trail."""
        try:
            AuditLogEntry.objects.create(
                user=self.request_user,
                content_type='properties.Property',
                object_id=property_obj.id,
                object_repr=str(property_obj)[:500],
                action=action,
                changes=changes,
                ip_address=self.request_ip
            )
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
    
    def _trigger_submission_notifications(self, property_obj: 'Property') -> None:
        """Trigger async notifications for property submission."""
        try:
            from properties.tasks import (
                notify_admin_property_submitted,
                send_owner_submission_confirmation
            )
            
            notify_admin_property_submitted.delay(str(property_obj.id))
            send_owner_submission_confirmation.delay(str(property_obj.id))
            
        except Exception as e:
            logger.warning(f"Failed to queue submission notifications: {e}")
    
    def _trigger_approval_notification(self, property_obj: 'Property') -> None:
        """Trigger async notification for property approval."""
        try:
            from properties.tasks import send_property_approved_email
            send_property_approved_email.delay(str(property_obj.id))
        except Exception as e:
            logger.warning(f"Failed to queue approval notification: {e}")
    
    def _trigger_rejection_notification(
        self,
        property_obj: 'Property',
        reason: str
    ) -> None:
        """Trigger async notification for property rejection."""
        try:
            from properties.tasks import send_property_rejected_email
            send_property_rejected_email.delay(str(property_obj.id), reason)
        except Exception as e:
            logger.warning(f"Failed to queue rejection notification: {e}")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_property_service(request=None) -> PropertyService:
    """
    Factory function to create PropertyService with request context.
    
    Args:
        request: Django request object (optional)
        
    Returns:
        Configured PropertyService instance
    """
    user = None
    ip = None
    
    if request:
        user = request.user if request.user.is_authenticated else None
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()
    
    return PropertyService(request_user=user, request_ip=ip)
