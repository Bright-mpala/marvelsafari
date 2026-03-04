"""
properties/validators.py - Comprehensive validation for Property models

Enterprise-grade validation logic:
- Price validation
- Date validation
- Content validation
- File upload validation
- Business rule validation
"""

import os
import re
import logging
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from PIL import Image

# Magic is optional - used for MIME type detection
try:
    import magic  # type: ignore[import-not-found]
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    magic = None

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

MAX_PROPERTY_IMAGES = 50
MIN_PROPERTY_IMAGES_FOR_SUBMISSION = 1
MAX_IMAGE_SIZE_MB = 5
MAX_IMAGE_DIMENSION = 4096
MIN_IMAGE_DIMENSION = 200
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_IMAGE_MIME_TYPES = {
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
}

MIN_PRICE = Decimal('0.01')
MAX_PRICE = Decimal('999999999.99')

MIN_DESCRIPTION_LENGTH = 50
MAX_DESCRIPTION_LENGTH = 10000

# Forbidden patterns in property names/descriptions
FORBIDDEN_PATTERNS = [
    r'<script',
    r'javascript:',
    r'on\w+\s*=',  # onclick, onload, etc.
    r'data:text/html',
]


# ============================================================================
# PRICE VALIDATORS
# ============================================================================

def validate_price(value, field_name='price'):
    """
    Validate price field.
    
    Args:
        value: Price value (can be Decimal, float, str, or int)
        field_name: Name of field for error messages
        
    Raises:
        ValidationError: If price is invalid
    """
    if value is None:
        return  # Allow None for optional prices
    
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise ValidationError(
            _('Invalid %(field)s format: %(error)s'),
            code='invalid_price_format',
            params={'field': field_name, 'error': str(e)}
        )
    
    if price < MIN_PRICE:
        raise ValidationError(
            _('%(field)s must be at least %(min)s'),
            code='price_too_low',
            params={'field': field_name, 'min': MIN_PRICE}
        )
    
    if price > MAX_PRICE:
        raise ValidationError(
            _('%(field)s cannot exceed %(max)s'),
            code='price_too_high',
            params={'field': field_name, 'max': MAX_PRICE}
        )
    
    # Ensure max 2 decimal places
    if price.as_tuple().exponent < -2:
        raise ValidationError(
            _('%(field)s cannot have more than 2 decimal places'),
            code='too_many_decimals',
            params={'field': field_name}
        )


def validate_price_range(minimum_price, maximum_price):
    """
    Validate that minimum_price <= maximum_price.
    
    Args:
        minimum_price: Minimum price value
        maximum_price: Maximum price value
        
    Raises:
        ValidationError: If range is invalid
    """
    if minimum_price is None or maximum_price is None:
        return
    
    try:
        min_val = Decimal(str(minimum_price))
        max_val = Decimal(str(maximum_price))
    except (InvalidOperation, ValueError, TypeError):
        return  # Skip range validation if prices are invalid
    
    if min_val > max_val:
        raise ValidationError(
            _('Minimum price (%(min)s) cannot exceed maximum price (%(max)s)'),
            code='invalid_price_range',
            params={'min': min_val, 'max': max_val}
        )


# ============================================================================
# CONTENT VALIDATORS
# ============================================================================

def validate_property_name(name):
    """
    Validate property name for security and quality.
    
    Args:
        name: Property name string
        
    Raises:
        ValidationError: If name is invalid
    """
    if not name or not name.strip():
        raise ValidationError(
            _('Property name is required'),
            code='name_required'
        )
    
    name = name.strip()
    
    if len(name) < 3:
        raise ValidationError(
            _('Property name must be at least 3 characters'),
            code='name_too_short'
        )
    
    if len(name) > 255:
        raise ValidationError(
            _('Property name cannot exceed 255 characters'),
            code='name_too_long'
        )
    
    # Check for forbidden patterns (XSS prevention)
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            raise ValidationError(
                _('Property name contains forbidden content'),
                code='forbidden_content'
            )


def validate_property_description(description):
    """
    Validate property description for quality and security.
    
    Args:
        description: Description text
        
    Raises:
        ValidationError: If description is invalid
    """
    if not description or not description.strip():
        raise ValidationError(
            _('Property description is required'),
            code='description_required'
        )
    
    description = description.strip()
    
    if len(description) < MIN_DESCRIPTION_LENGTH:
        raise ValidationError(
            _('Description must be at least %(min)s characters for quality listings'),
            code='description_too_short',
            params={'min': MIN_DESCRIPTION_LENGTH}
        )
    
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValidationError(
            _('Description cannot exceed %(max)s characters'),
            code='description_too_long',
            params={'max': MAX_DESCRIPTION_LENGTH}
        )
    
    # Check for forbidden patterns
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, description, re.IGNORECASE):
            raise ValidationError(
                _('Description contains forbidden content'),
                code='forbidden_content'
            )


def validate_slug_uniqueness(slug, exclude_pk=None):
    """
    Validate slug uniqueness.
    
    Args:
        slug: Slug string
        exclude_pk: Primary key to exclude from check
        
    Raises:
        ValidationError: If slug is not unique
    """
    from properties.models import Property
    
    queryset = Property.objects.filter(slug=slug)
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    
    if queryset.exists():
        raise ValidationError(
            _('A property with this slug already exists'),
            code='slug_not_unique'
        )


# ============================================================================
# IMAGE VALIDATORS
# ============================================================================

def validate_image_file(image_file):
    """
    Comprehensive image file validation.
    
    Validates:
    - File extension
    - MIME type (magic bytes)
    - File size
    - Image dimensions
    - File corruption
    
    Args:
        image_file: Uploaded file object
        
    Raises:
        ValidationError: If image is invalid
    """
    if not image_file:
        return
    
    # Reset file pointer
    image_file.seek(0)
    
    # Check file extension
    filename = getattr(image_file, 'name', '')
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            _('Invalid file type "%(ext)s". Allowed: %(allowed)s'),
            code='invalid_extension',
            params={'ext': ext, 'allowed': ', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}
        )
    
    # Check file size
    file_size = image_file.size
    max_size_bytes = MAX_IMAGE_SIZE_MB * 1024 * 1024
    if file_size > max_size_bytes:
        raise ValidationError(
            _('Image file too large (%(size).2f MB). Maximum: %(max)s MB'),
            code='file_too_large',
            params={'size': file_size / (1024 * 1024), 'max': MAX_IMAGE_SIZE_MB}
        )
    
    # Validate MIME type using magic bytes (if available)
    if HAS_MAGIC:
        try:
            mime_type = magic.from_buffer(image_file.read(2048), mime=True)
            image_file.seek(0)
            
            if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
                raise ValidationError(
                    _('Invalid image format. Detected: %(mime)s'),
                    code='invalid_mime_type',
                    params={'mime': mime_type}
                )
        except ValidationError:
            raise
        except Exception as e:
            logger.warning(f"Magic MIME detection failed: {e}")
            # Fall back to PIL validation
    else:
        # Magic not available, rely on PIL validation below
        logger.debug("python-magic not installed, skipping MIME detection")
    
    # Validate image integrity and dimensions with PIL
    try:
        image_file.seek(0)
        with Image.open(image_file) as img:
            img.verify()  # Verify image integrity
            
        # Re-open after verify() corrupts file handle
        image_file.seek(0)
        with Image.open(image_file) as img:
            width, height = img.size
            
            if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
                raise ValidationError(
                    _('Image dimensions too large (%(w)sx%(h)s). Maximum: %(max)sx%(max)s'),
                    code='dimensions_too_large',
                    params={'w': width, 'h': height, 'max': MAX_IMAGE_DIMENSION}
                )
            
            if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
                raise ValidationError(
                    _('Image dimensions too small (%(w)sx%(h)s). Minimum: %(min)sx%(min)s'),
                    code='dimensions_too_small',
                    params={'w': width, 'h': height, 'min': MIN_IMAGE_DIMENSION}
                )
                
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(
            _('Invalid or corrupted image file: %(error)s'),
            code='corrupted_image',
            params={'error': str(e)}
        )
    finally:
        image_file.seek(0)


def validate_minimum_images(property_obj, required=MIN_PROPERTY_IMAGES_FOR_SUBMISSION):
    """
    Validate that property has minimum required images for submission.
    
    Args:
        property_obj: Property instance
        required: Minimum required images
        
    Raises:
        ValidationError: If insufficient images
    """
    from properties.models import PropertyImage
    
    image_count = PropertyImage.objects.filter(property=property_obj).count()
    
    if image_count < required:
        raise ValidationError(
            _('At least %(required)s image is required before submission. Currently: %(count)s'),
            code='insufficient_images',
            params={'required': required, 'count': image_count}
        )


# ============================================================================
# LOCATION VALIDATORS
# ============================================================================

def validate_coordinates(latitude, longitude):
    """
    Validate geographic coordinates.
    
    Args:
        latitude: Latitude value
        longitude: Longitude value
        
    Raises:
        ValidationError: If coordinates are invalid
    """
    if latitude is None and longitude is None:
        return  # Both optional
    
    if (latitude is None) != (longitude is None):
        raise ValidationError(
            _('Both latitude and longitude must be provided together'),
            code='incomplete_coordinates'
        )
    
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (ValueError, TypeError):
        raise ValidationError(
            _('Invalid coordinate format'),
            code='invalid_coordinate_format'
        )
    
    if not (-90 <= lat <= 90):
        raise ValidationError(
            _('Latitude must be between -90 and 90'),
            code='invalid_latitude'
        )
    
    if not (-180 <= lng <= 180):
        raise ValidationError(
            _('Longitude must be between -180 and 180'),
            code='invalid_longitude'
        )


# ============================================================================
# YEAR VALIDATORS
# ============================================================================

def validate_year_built(year):
    """
    Validate year built field.
    
    Args:
        year: Year value
        
    Raises:
        ValidationError: If year is invalid
    """
    if year is None:
        return
    
    current_year = timezone.now().year
    
    if year < 1800:
        raise ValidationError(
            _('Year built cannot be earlier than 1800'),
            code='year_too_early'
        )
    
    if year > current_year + 5:
        raise ValidationError(
            _('Year built cannot be more than 5 years in the future'),
            code='year_too_late'
        )


def validate_year_renovated(year_renovated, year_built):
    """
    Validate year renovated relative to year built.
    
    Args:
        year_renovated: Renovation year
        year_built: Construction year
        
    Raises:
        ValidationError: If relationship is invalid
    """
    if year_renovated is None:
        return
    
    current_year = timezone.now().year
    
    if year_renovated < 1800:
        raise ValidationError(
            _('Year renovated cannot be earlier than 1800'),
            code='renovation_year_too_early'
        )
    
    if year_renovated > current_year + 1:
        raise ValidationError(
            _('Year renovated cannot be in the future'),
            code='renovation_year_future'
        )
    
    if year_built and year_renovated < year_built:
        raise ValidationError(
            _('Year renovated cannot be before year built'),
            code='renovation_before_construction'
        )


# ============================================================================
# STATUS VALIDATORS
# ============================================================================

def validate_status_transition(current_status, new_status, user):
    """
    Validate property status transition based on user role.
    
    Args:
        current_status: Current PropertyStatus value
        new_status: New PropertyStatus value
        user: User making the change
        
    Raises:
        ValidationError: If transition is not allowed
    """
    from properties.models import PropertyStatus
    from accounts.models import UserRole
    
    is_admin = user.is_staff or user.is_superuser or user.role == UserRole.ADMIN
    
    # Owners can only transition to specific states
    owner_allowed_transitions = {
        PropertyStatus.DRAFT: {PropertyStatus.PENDING},
        PropertyStatus.PENDING: {PropertyStatus.DRAFT},  # Cancel submission
        PropertyStatus.REJECTED: {PropertyStatus.PENDING, PropertyStatus.DRAFT},  # Resubmit
        PropertyStatus.APPROVED: {PropertyStatus.INACTIVE},  # Deactivate
        PropertyStatus.ACTIVE: {PropertyStatus.INACTIVE},
        PropertyStatus.INACTIVE: {PropertyStatus.ACTIVE, PropertyStatus.PENDING},
    }
    
    # Admins can do any transition
    if is_admin:
        return
    
    allowed = owner_allowed_transitions.get(current_status, set())
    
    if new_status not in allowed:
        raise ValidationError(
            _('Status transition from %(current)s to %(new)s is not allowed'),
            code='invalid_status_transition',
            params={'current': current_status, 'new': new_status}
        )
    
    # Owners cannot approve their own properties
    if new_status in {PropertyStatus.APPROVED, PropertyStatus.ACTIVE}:
        raise ValidationError(
            _('Only administrators can approve properties'),
            code='approval_requires_admin'
        )


# ============================================================================
# COMPREHENSIVE PROPERTY VALIDATOR
# ============================================================================

def validate_property_for_submission(property_obj):
    """
    Comprehensive validation before property can be submitted for review.
    
    Args:
        property_obj: Property instance
        
    Raises:
        ValidationError: If property fails validation
    """
    errors = {}
    
    # Validate required fields
    if not property_obj.name:
        errors['name'] = [_('Property name is required')]
    else:
        try:
            validate_property_name(property_obj.name)
        except ValidationError as e:
            errors['name'] = e.messages
    
    if not property_obj.description:
        errors['description'] = [_('Property description is required')]
    else:
        try:
            validate_property_description(property_obj.description)
        except ValidationError as e:
            errors['description'] = e.messages
    
    # Validate pricing
    try:
        if property_obj.minimum_price:
            validate_price(property_obj.minimum_price, 'minimum price')
        if property_obj.maximum_price:
            validate_price(property_obj.maximum_price, 'maximum price')
        validate_price_range(property_obj.minimum_price, property_obj.maximum_price)
    except ValidationError as e:
        errors['pricing'] = e.messages
    
    # Validate location
    if not property_obj.city:
        errors['city'] = [_('City is required')]
    if not property_obj.country:
        errors['country'] = [_('Country is required')]
    if not property_obj.address:
        errors['address'] = [_('Address is required')]
    
    try:
        validate_coordinates(property_obj.latitude, property_obj.longitude)
    except ValidationError as e:
        errors['coordinates'] = e.messages
    
    # Validate images
    try:
        validate_minimum_images(property_obj)
    except ValidationError as e:
        errors['images'] = e.messages
    
    # Validate owner
    if not property_obj.owner:
        errors['owner'] = [_('Property must have an owner')]
    
    if errors:
        raise ValidationError(errors)