import logging

from django.db import models
from django_countries.fields import CountryField
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from taggit.managers import TaggableManager
from mptt.models import MPTTModel, TreeForeignKey
from phonenumber_field.modelfields import PhoneNumberField

from core.models import SoftDeletableModel, BaseModel, UUIDTaggedItem


logger = logging.getLogger(__name__)


class PropertyType(models.Model):
    """Property type classification."""
    
    name = models.CharField(_('name'), max_length=100)
    slug = models.SlugField(_('slug'), unique=True)
    description = models.TextField(_('description'), blank=True)
    icon = models.CharField(_('icon'), max_length=50, blank=True)
    is_active = models.BooleanField(_('active'), default=True)
    
    # Hierarchy
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = _('property type')
        verbose_name_plural = _('property types')
        ordering = ['name']


class AmenityCategory(MPTTModel):
    """Amenity category with hierarchy."""
    
    name = models.CharField(_('name'), max_length=100)
    slug = models.SlugField(_('slug'), unique=True)
    description = models.TextField(_('description'), blank=True)
    icon = models.CharField(_('icon'), max_length=50, blank=True)
    
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    
    class MPTTMeta:
        order_insertion_by = ['name']
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = _('amenity category')
        verbose_name_plural = _('amenity categories')


class Amenity(models.Model):
    """Property amenity."""
    
    name = models.CharField(_('name'), max_length=100)
    slug = models.SlugField(_('slug'), unique=True)
    description = models.TextField(_('description'), blank=True)
    icon = models.CharField(_('icon'), max_length=50, blank=True)
    category = models.ForeignKey(
        AmenityCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='amenities'
    )
    is_chargeable = models.BooleanField(_('chargeable'), default=False)
    charge_amount = models.DecimalField(
        _('charge amount'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    is_active = models.BooleanField(_('active'), default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = _('amenity')
        verbose_name_plural = _('amenities')
        ordering = ['name']


class PropertyStatus(models.TextChoices):
    """Moderation and lifecycle states for a property."""

    DRAFT = 'draft', _('Draft')
    PENDING = 'pending', _('Pending Review')
    ACTIVE = 'active', _('Active')
    APPROVED = 'approved', _('Approved')
    REJECTED = 'rejected', _('Rejected')
    INACTIVE = 'inactive', _('Inactive')

    @classmethod
    def public_statuses(cls):
        """Statuses that allow public visibility."""
        return {cls.APPROVED, cls.ACTIVE}
    
    @classmethod
    def editable_by_owner(cls):
        """Statuses that allow owner editing."""
        return {cls.DRAFT, cls.PENDING, cls.REJECTED}
    
    @classmethod
    def submittable_statuses(cls):
        """Statuses from which submission is allowed."""
        return {cls.DRAFT, cls.REJECTED}


class Property(SoftDeletableModel):
    """Main property model (hotel, apartment, etc.)."""
    
    name = models.CharField(_('property name'), max_length=255)
    slug = models.SlugField(_('slug'), max_length=300, unique=True)
    description = models.TextField(_('description'))
    
    # Basic Information
    property_type = models.ForeignKey(
        PropertyType,
        on_delete=models.PROTECT,
        related_name='properties'
    )
    star_rating = models.PositiveSmallIntegerField(
        _('star rating'),
        null=True,
        blank=True,
        choices=[(i, f'{i} Stars') for i in range(1, 6)],
        validators=[MaxValueValidator(5)]
    )
    
    # Location Information
    address = models.TextField(_('address'))
    city = models.CharField(_('city'), max_length=100)
    state = models.CharField(_('state/province'), max_length=100, blank=True)
    postal_code = models.CharField(_('postal code'), max_length=20)
    country = CountryField(_('country'))
    latitude = models.DecimalField(
        _('latitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        _('longitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    
    # Contact Information
    phone = PhoneNumberField(_('phone number'), blank=True)
    email = models.EmailField(_('email address'), blank=True)
    website = models.URLField(_('website'), blank=True)
    
    # Owner/Host Information
    owner = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='owned_properties',
        help_text=_('Listing owner/host'),
        null=True,
        blank=True
    )
    manager_name = models.CharField(_('manager name'), max_length=100, blank=True)
    manager_phone = PhoneNumberField(_('manager phone'), blank=True)
    manager_email = models.EmailField(_('manager email'), blank=True)
    
    # Property Details
    check_in_time = models.TimeField(_('check-in time'), default='14:00')
    check_out_time = models.TimeField(_('check-out time'), default='12:00')
    earliest_check_in = models.TimeField(_('earliest check-in'), default='12:00')
    latest_check_out = models.TimeField(_('latest check-out'), default='15:00')
    
    # Policies
    cancellation_policy = models.TextField(_('cancellation policy'), blank=True)
    house_rules = models.TextField(_('house rules'), blank=True)
    special_instructions = models.TextField(_('special instructions'), blank=True)
    
    # Amenities
    amenities = models.ManyToManyField(Amenity, related_name='properties', blank=True)
    
    # Statistics
    total_rooms = models.PositiveIntegerField(_('total rooms'), default=1, validators=[MaxValueValidator(10000)])
    year_built = models.PositiveIntegerField(_('year built'), null=True, blank=True, validators=[MinValueValidator(1800), MaxValueValidator(2100)])
    year_renovated = models.PositiveIntegerField(_('year renovated'), null=True, blank=True, validators=[MinValueValidator(1800), MaxValueValidator(2100)])
    
    # Status and Verification
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=PropertyStatus.choices,
        default=PropertyStatus.PENDING
    )
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_properties'
    )
    approved_at = models.DateTimeField(_('approved at'), null=True, blank=True)
    rejection_reason = models.TextField(_('rejection reason'), blank=True)
    is_featured = models.BooleanField(_('featured'), default=False)
    is_verified = models.BooleanField(_('verified'), default=False)
    verification_date = models.DateTimeField(_('verification date'), null=True, blank=True)
    
    # SEO and Marketing
    meta_title = models.CharField(_('meta title'), max_length=255, blank=True)
    meta_description = models.TextField(_('meta description'), blank=True)
    meta_keywords = models.TextField(_('meta keywords'), blank=True)
    
    # Performance Metrics
    view_count = models.PositiveIntegerField(_('view count'), default=0, validators=[MaxValueValidator(999999999)])
    booking_count = models.PositiveIntegerField(_('booking count'), default=0, validators=[MaxValueValidator(999999999)])
    average_rating = models.DecimalField(
        _('average rating'),
        max_digits=3,
        decimal_places=2,
        default=0
    )
    review_count = models.PositiveIntegerField(_('review count'), default=0, validators=[MaxValueValidator(999999999)])
    
    # Commission and Pricing
    commission_rate = models.DecimalField(
        _('commission rate'),
        max_digits=5,
        decimal_places=2,
        default=Decimal('15.00'),
        help_text=_('Commission percentage')
    )
    minimum_price = models.DecimalField(
        _('minimum price'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    maximum_price = models.DecimalField(
        _('maximum price'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Timestamps
    published_at = models.DateTimeField(_('published at'), null=True, blank=True)
    
    tags = TaggableManager(blank=True, through=UUIDTaggedItem)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = _('property')
        verbose_name_plural = _('properties')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_featured']),
            models.Index(fields=['city', 'country', 'status']),
            models.Index(fields=['minimum_price', 'maximum_price']),
            models.Index(fields=['latitude', 'longitude']),
            # Production indexes for common queries
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['status', 'is_active', 'is_deleted']),
            models.Index(fields=['country', 'city']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['is_verified', 'status']),
        ]
        constraints = [
            # Ensure minimum_price <= maximum_price when both are set
            models.CheckConstraint(
                check=models.Q(minimum_price__isnull=True) | 
                      models.Q(maximum_price__isnull=True) | 
                      models.Q(minimum_price__lte=models.F('maximum_price')),
                name='property_price_range_valid'
            ),
            # Ensure prices are non-negative
            models.CheckConstraint(
                check=models.Q(minimum_price__isnull=True) | models.Q(minimum_price__gte=0),
                name='property_min_price_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(maximum_price__isnull=True) | models.Q(maximum_price__gte=0),
                name='property_max_price_non_negative'
            ),
            # Commission rate between 0 and 100
            models.CheckConstraint(
                check=models.Q(commission_rate__gte=0) & models.Q(commission_rate__lte=100),
                name='property_commission_rate_valid'
            ),
        ]
    
    def clean(self):
        """
        Comprehensive model validation.
        
        Validates:
        - Price range consistency
        - Year built/renovated logic
        - Coordinates validity
        - Required fields for submission
        """
        from django.core.exceptions import ValidationError
        from decimal import Decimal
        from django.utils import timezone
        
        errors = {}
        
        # Validate price range
        if self.minimum_price is not None and self.maximum_price is not None:
            if self.minimum_price > self.maximum_price:
                errors['minimum_price'] = _('Minimum price cannot exceed maximum price.')
        
        # Validate prices are positive
        if self.minimum_price is not None and self.minimum_price < Decimal('0'):
            errors['minimum_price'] = _('Price cannot be negative.')
        if self.maximum_price is not None and self.maximum_price < Decimal('0'):
            errors['maximum_price'] = _('Price cannot be negative.')
        
        # Validate year built
        current_year = timezone.now().year
        if self.year_built:
            if self.year_built < 1800:
                errors['year_built'] = _('Year built cannot be earlier than 1800.')
            elif self.year_built > current_year + 5:
                errors['year_built'] = _('Year built cannot be more than 5 years in the future.')
        
        # Validate year renovated
        if self.year_renovated:
            if self.year_renovated < 1800:
                errors['year_renovated'] = _('Year renovated cannot be earlier than 1800.')
            elif self.year_renovated > current_year + 1:
                errors['year_renovated'] = _('Year renovated cannot be in the future.')
            elif self.year_built and self.year_renovated < self.year_built:
                errors['year_renovated'] = _('Year renovated cannot be before year built.')
        
        # Validate coordinates
        if self.latitude is not None or self.longitude is not None:
            if self.latitude is None or self.longitude is None:
                errors['latitude'] = _('Both latitude and longitude must be provided.')
            else:
                if not (-90 <= float(self.latitude) <= 90):
                    errors['latitude'] = _('Latitude must be between -90 and 90.')
                if not (-180 <= float(self.longitude) <= 180):
                    errors['longitude'] = _('Longitude must be between -180 and 180.')
        
        # Validate commission rate
        if self.commission_rate is not None:
            if self.commission_rate < 0 or self.commission_rate > 100:
                errors['commission_rate'] = _('Commission rate must be between 0 and 100.')
        
        # Validate star rating
        if self.star_rating is not None:
            if self.star_rating < 1 or self.star_rating > 5:
                errors['star_rating'] = _('Star rating must be between 1 and 5.')
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        # Run clean validation
        self.full_clean(exclude=['slug'])  # Exclude slug as it may not be set yet
        
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def can_be_submitted(self):
        """Check if property can be submitted for review."""
        return self.status in PropertyStatus.submittable_statuses()
    
    def can_be_edited_by(self, user):
        """Check if user can edit this property."""
        if user.is_staff or user.is_superuser:
            return True
        if self.owner_id != user.id:
            return False
        return self.status in PropertyStatus.editable_by_owner()
    
    def is_publicly_visible(self):
        """Check if property should be visible to public."""
        return (
            self.status in PropertyStatus.public_statuses()
            and self.is_active
            and not self.is_deleted
        )
    
    def get_primary_image(self):
        """Return the primary image, prioritizing prefetched data when available."""
        cached = getattr(self, '_primary_image_cache', None)
        if cached is not None:
            return cached

        prefetched = getattr(self, '_prefetched_objects_cache', {})
        images = prefetched.get('images') if prefetched else None

        image = None
        if images:
            image = next((img for img in images if getattr(img, 'is_primary', False)), images[0])
        else:
            image = self.images.filter(is_primary=True).first() or self.images.first()

        self._primary_image_cache = image
        return image

    def get_primary_image_url(self):
        """Return the best display URL for the primary image (or ``None``)."""
        image = self.get_primary_image()
        if not image:
            return None
        return image.get_thumbnail_url()
    
    @property
    def location(self):
        return f"{self.city}, {self.country.name}"
    
    @property
    def is_available(self):
        return (
            self.status in {PropertyStatus.APPROVED, PropertyStatus.ACTIVE}
            and self.is_verified
            and self.is_active
            and not self.is_deleted
        )

    @property
    def host(self):
        # Backwards-compatible alias for legacy code
        return self.owner

    @host.setter
    def host(self, value):
        self.owner = value


class RoomType(models.Model):
    """Room type within a property."""
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='room_types'
    )
    name = models.CharField(_('room type name'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    
    # Pricing
    base_price = models.DecimalField(
        _('base price per night'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Price per night in USD')
    )
    
    # Quantity available
    quantity_available = models.PositiveSmallIntegerField(
        _('quantity available'),
        default=1,
        validators=[MaxValueValidator(1000)],
        help_text=_('Number of rooms of this type available')
    )
    
    # Capacity
    max_adults = models.PositiveSmallIntegerField(_('maximum adults'), default=2, validators=[MaxValueValidator(50)])
    max_children = models.PositiveSmallIntegerField(_('maximum children'), default=2, validators=[MaxValueValidator(50)])
    max_occupancy = models.PositiveSmallIntegerField(_('maximum occupancy'), default=4, validators=[MaxValueValidator(100)])
    
    # Room Features
    room_size = models.DecimalField(
        _('room size'),
        max_digits=8,
        decimal_places=2,
        help_text=_('Size in square meters'),
        null=True,
        blank=True
    )
    bed_type = models.CharField(_('bed type'), max_length=100, blank=True)
    bed_count = models.PositiveSmallIntegerField(_('bed count'), default=1, validators=[MaxValueValidator(20)])
    bathroom_count = models.PositiveSmallIntegerField(_('bathroom count'), default=1, validators=[MaxValueValidator(10)])
    
    # Amenities specific to this room type
    amenities = models.ManyToManyField(Amenity, related_name='room_types', blank=True)
    
    # Images
    main_image = models.ImageField(
        _('main image'),
        upload_to='room_types/',
        null=True,
        blank=True
    )
    
    # Display order
    display_order = models.PositiveIntegerField(_('display order'), default=0, validators=[MaxValueValidator(999)])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.property.name} - {self.name}"
    
    class Meta:
        verbose_name = _('room type')
        verbose_name_plural = _('room types')
        ordering = ['display_order', 'name']


def room_type_image_upload_path(instance, filename):
    """Generate upload path for room type images."""
    import uuid
    import os
    
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
    if ext not in {'jpg', 'jpeg', 'png', 'gif', 'webp'}:
        ext = 'jpg'
    
    safe_filename = f"{uuid.uuid4().hex}.{ext}"
    property_id = instance.room_type.property_id if instance.room_type else 'unknown'
    room_type_id = instance.room_type_id if instance.room_type_id else 'unknown'
    
    return f"room_types/{property_id}/{room_type_id}/{safe_filename}"


class RoomTypeImage(models.Model):
    """
    Images for room types - allows multiple photos per room type.
    
    Guests need to see:
    - Room layout/bed configuration
    - Bathroom facilities  
    - View from room
    - Room amenities (TV, desk, etc.)
    - Any special features
    """
    
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(
        _('image'),
        upload_to=room_type_image_upload_path,
        help_text=_('Room photo. Supported formats: JPG, PNG, WebP. Max 5MB.')
    )
    caption = models.CharField(
        _('caption'),
        max_length=255,
        blank=True,
        help_text=_('e.g., "Bedroom view", "En-suite bathroom", "Balcony overlooking garden"')
    )
    is_primary = models.BooleanField(
        _('primary image'),
        default=False,
        db_index=True,
        help_text=_('Main photo shown in room listings')
    )
    display_order = models.PositiveIntegerField(
        _('display order'),
        default=0,
        validators=[MaxValueValidator(99)]
    )
    
    # Image metadata
    width = models.PositiveIntegerField(_('width'), null=True, blank=True, editable=False)
    height = models.PositiveIntegerField(_('height'), null=True, blank=True, editable=False)
    file_size = models.PositiveIntegerField(_('file size'), null=True, blank=True, editable=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.room_type.name} - Image {self.display_order + 1}"
    
    class Meta:
        verbose_name = _('room type image')
        verbose_name_plural = _('room type images')
        ordering = ['-is_primary', 'display_order', 'created_at']
        indexes = [
            models.Index(fields=['room_type', 'is_primary']),
            models.Index(fields=['room_type', 'display_order']),
        ]
    
    def save(self, *args, **kwargs):
        # Auto-populate image metadata
        if self.image and not self.file_size:
            try:
                self.file_size = self.image.size
            except Exception:
                pass
        
        if self.image and (not self.width or not self.height):
            try:
                from PIL import Image
                self.image.seek(0)
                img = Image.open(self.image)
                self.width, self.height = img.size
                self.image.seek(0)
            except Exception:
                pass
        
        super().save(*args, **kwargs)
        
        # Ensure only one primary image per room type
        if self.is_primary:
            RoomTypeImage.objects.filter(
                room_type=self.room_type,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)


class PropertyActivity(models.Model):
    """Activity or tour offered at a property."""
    
    ACTIVITY_TYPES = (
        ('tour', _('Guided Tour')),
        ('safari', _('Safari')),
        ('hiking', _('Hiking/Trekking')),
        ('water', _('Water Activity')),
        ('cultural', _('Cultural Experience')),
        ('wildlife', _('Wildlife Viewing')),
        ('dining', _('Dining Experience')),
        ('spa', _('Spa/Wellness')),
        ('adventure', _('Adventure Activity')),
        ('other', _('Other')),
    )
    
    DIFFICULTY_LEVELS = (
        ('easy', _('Easy (All ages)')),
        ('moderate', _('Moderate')),
        ('challenging', _('Challenging')),
        ('extreme', _('Extreme')),
    )
    
    AVAILABILITY_CHOICES = (
        ('daily', _('Daily')),
        ('weekdays', _('Weekdays Only')),
        ('weekends', _('Weekends Only')),
        ('on_request', _('On Request')),
    )
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='property_activities'
    )
    name = models.CharField(_('activity name'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    activity_type = models.CharField(
        _('activity type'),
        max_length=50,
        choices=ACTIVITY_TYPES,
        default='tour'
    )
    
    # Pricing
    price_per_person = models.DecimalField(
        _('price per person'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Price per person in USD')
    )
    
    # Duration
    duration = models.CharField(
        _('duration'),
        max_length=100,
        blank=True,
        help_text=_('e.g., 3 hours, Half-day, Full day')
    )
    
    # Participants
    min_participants = models.PositiveSmallIntegerField(
        _('minimum participants'),
        default=1,
        validators=[MaxValueValidator(100)]
    )
    max_participants = models.PositiveSmallIntegerField(
        _('maximum participants'),
        null=True,
        blank=True,
        validators=[MaxValueValidator(500)]
    )
    
    # Availability
    availability = models.CharField(
        _('availability'),
        max_length=20,
        choices=AVAILABILITY_CHOICES,
        default='daily'
    )
    
    # Difficulty
    difficulty = models.CharField(
        _('difficulty level'),
        max_length=20,
        choices=DIFFICULTY_LEVELS,
        default='moderate'
    )
    
    # What's included
    included = models.TextField(
        _("what's included"),
        blank=True,
        help_text=_('e.g., Guide, refreshments, equipment...')
    )
    
    # Display order
    display_order = models.PositiveIntegerField(_('display order'), default=0)
    is_active = models.BooleanField(_('active'), default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.property.name} - {self.name}"
    
    class Meta:
        verbose_name = _('property activity')
        verbose_name_plural = _('property activities')
        ordering = ['display_order', 'name']


class Room(models.Model):
    """Individual room within a property."""
    
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.CASCADE,
        related_name='rooms'
    )
    room_number = models.CharField(_('room number'), max_length=50)
    floor = models.PositiveSmallIntegerField(_('floor'), null=True, blank=True, validators=[MaxValueValidator(200)])
    
    # Room Status
    is_available = models.BooleanField(_('available'), default=True)
    maintenance_notes = models.TextField(_('maintenance notes'), blank=True)
    
    # Features
    has_balcony = models.BooleanField(_('has balcony'), default=False)
    has_view = models.BooleanField(_('has view'), default=False)
    view_description = models.CharField(_('view description'), max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.room_type.property.name} - {self.room_type.name} - {self.room_number}"
    
    class Meta:
        verbose_name = _('room')
        verbose_name_plural = _('rooms')
        unique_together = [['room_type', 'room_number']]
        ordering = ['room_type', 'room_number']


def property_image_upload_path(instance, filename):
    """
    Generate secure, CDN-ready upload path for property images.
    
    Structure: properties/{owner_id}/{property_id}/{uuid}_{filename}
    This structure supports:
    - Easy CDN purging by property
    - Owner-based access control
    - Safe filenames
    """
    import uuid
    import os
    
    # Get safe extension
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
    if ext not in {'jpg', 'jpeg', 'png', 'gif', 'webp'}:
        ext = 'jpg'
    
    # Generate unique filename
    safe_filename = f"{uuid.uuid4().hex}.{ext}"
    
    # Get owner ID (fallback to 'anonymous')
    owner_id = 'anonymous'
    if instance.property and instance.property.owner_id:
        owner_id = str(instance.property.owner_id)
    
    # Get property ID
    property_id = str(instance.property_id) if instance.property_id else 'temp'
    
    return f"properties/{owner_id}/{property_id}/{safe_filename}"


class PropertyImage(BaseModel):
    """
    Property images with CDN-ready paths and optimization support.
    
    Features:
    - Owner-based folder structure for security
    - Primary image logic with constraint
    - Thumbnail generation ready
    - CDN purging support
    """
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(
        _('image'), 
        upload_to=property_image_upload_path,
        help_text=_('Supported formats: JPG, PNG, GIF, WebP. Max 5MB.')
    )
    caption = models.CharField(_('caption'), max_length=255, blank=True)
    alt_text = models.CharField(_('alt text'), max_length=255, blank=True)
    is_primary = models.BooleanField(_('primary image'), default=False, db_index=True)
    display_order = models.PositiveIntegerField(
        _('display order'), 
        default=0, 
        validators=[MaxValueValidator(999)],
        db_index=True
    )
    
    # Image metadata (populated after upload/processing)
    width = models.PositiveIntegerField(_('width'), null=True, blank=True, editable=False)
    height = models.PositiveIntegerField(_('height'), null=True, blank=True, editable=False)
    file_size = models.PositiveIntegerField(_('file size'), null=True, blank=True, editable=False)
    
    # Thumbnail URL (populated by CDN/processing service)
    thumbnail_url = models.URLField(_('thumbnail URL'), blank=True, editable=False)
    
    # Processing status
    is_processed = models.BooleanField(_('processed'), default=False)
    processing_error = models.TextField(_('processing error'), blank=True)
    
    def __str__(self):
        return f"Image for {self.property.name}" if self.property else "Property Image"
    
    class Meta:
        verbose_name = _('property image')
        verbose_name_plural = _('property images')
        ordering = ['-is_primary', 'display_order', 'created_at']
        indexes = [
            models.Index(fields=['property', 'is_primary']),
            models.Index(fields=['property', 'display_order']),
        ]
    
    def save(self, *args, **kwargs):
        # Auto-populate image metadata
        if self.image and not self.file_size:
            try:
                self.file_size = self.image.size
            except Exception:
                pass
        
        if self.image and (not self.width or not self.height):
            try:
                from PIL import Image
                self.image.seek(0)
                img = Image.open(self.image)
                self.width, self.height = img.size
                self.image.seek(0)
            except Exception:
                pass
        
        super().save(*args, **kwargs)
        
        # Ensure only one primary image per property
        if self.is_primary:
            PropertyImage.objects.filter(
                property_id=self.property_id,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
    
    def _file_exists(self):
        """Check if the underlying file exists in storage."""
        if not self.image:
            return False
        storage = getattr(self.image, 'storage', None)
        if not storage:
            return False
        try:
            return storage.exists(self.image.name)
        except Exception:
            logger.warning("Failed to verify existence for property image %s", self.pk, exc_info=True)
            return False

    def get_cdn_url(self):
        """Get CDN URL for this image (for future CDN integration)."""
        from django.conf import settings
        cdn_base = getattr(settings, 'CDN_BASE_URL', None)
        
        if not self._file_exists():
            return None
        
        if cdn_base:
            return f"{cdn_base.rstrip('/')}/{self.image.name}"
        
        try:
            return self.image.url
        except Exception:
            logger.warning("Missing URL for property image %s", self.pk, exc_info=True)
            return None
    
    def get_thumbnail_url(self, size='thumb'):
        """
        Get thumbnail URL (for future thumbnail service).
        
        Args:
            size: 'thumb' (150px), 'small' (300px), 'medium' (600px), 'large' (1200px)
        """
        if self.thumbnail_url:
            return self.thumbnail_url
        
        # Fallback to original
        return self.get_cdn_url()


class PropertyAvailability(BaseModel):
    """Date-based availability and pricing for properties."""

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='availabilities'
    )
    date = models.DateField(_('date'), db_index=True)
    is_available = models.BooleanField(_('available'), default=True)
    price_override = models.DecimalField(
        _('price override'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Optional price override for this date')
    )

    class Meta:
        verbose_name = _('property availability')
        verbose_name_plural = _('property availability')
        unique_together = ['property', 'date']
        indexes = [
            models.Index(fields=['property', 'date']),
            models.Index(fields=['property', 'date', 'is_available']),
        ]

    def __str__(self):
        return f"{self.property.name} {self.date}"


class PricePlan(models.Model):
    """Dynamic pricing plans for room types."""
    
    CURRENCY_CHOICES = (
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('JPY', 'Japanese Yen'),
        ('CAD', 'Canadian Dollar'),
        ('AUD', 'Australian Dollar'),
    )
    
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.CASCADE,
        related_name='price_plans'
    )
    name = models.CharField(_('plan name'), max_length=100)
    
    # Pricing
    base_price = models.DecimalField(_('base price'), max_digits=10, decimal_places=2)
    currency = models.CharField(
        _('currency'),
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='USD'
    )
    
    # Conditions
    min_nights = models.PositiveSmallIntegerField(_('minimum nights'), default=1, validators=[MaxValueValidator(365)])
    max_nights = models.PositiveSmallIntegerField(_('maximum nights'), null=True, blank=True, validators=[MaxValueValidator(365)])
    
    # Cancellation Policy
    cancellation_days = models.PositiveSmallIntegerField(
        _('free cancellation days'),
        default=0,
        help_text=_('Days before check-in for free cancellation'),
        validators=[MaxValueValidator(365)]
    )
    
    # Additional Charges
    extra_person_charge = models.DecimalField(
        _('extra person charge'),
        max_digits=8,
        decimal_places=2,
        default=0
    )
    breakfast_included = models.BooleanField(_('breakfast included'), default=False)
    taxes_included = models.BooleanField(_('taxes included'), default=False)
    
    # Availability
    is_active = models.BooleanField(_('active'), default=True)
    start_date = models.DateField(_('start date'))
    end_date = models.DateField(_('end date'))
    
    # Dynamic Pricing Rules
    weekday_multiplier = models.DecimalField(
        _('weekday multiplier'),
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.0')
    )
    weekend_multiplier = models.DecimalField(
        _('weekend multiplier'),
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.2')
    )
    holiday_multiplier = models.DecimalField(
        _('holiday multiplier'),
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.5')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.room_type} - {self.name}"
    
    class Meta:
        verbose_name = _('price plan')
        verbose_name_plural = _('price plans')
        ordering = ['start_date', 'name']


class Availability(models.Model):
    """Room availability by date."""
    
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='availabilities')
    date = models.DateField(_('date'))
    
    # Availability Status
    is_available = models.BooleanField(_('available'), default=True)
    price = models.DecimalField(_('price'), max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Restrictions
    min_stay = models.PositiveSmallIntegerField(_('minimum stay'), default=1, validators=[MaxValueValidator(365)])
    max_stay = models.PositiveSmallIntegerField(_('maximum stay'), null=True, blank=True, validators=[MaxValueValidator(365)])
    
    # Dynamic Pricing
    dynamic_price = models.DecimalField(
        _('dynamic price'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Inventory
    available_rooms = models.PositiveIntegerField(_('available rooms'), default=1, validators=[MaxValueValidator(10000)])
    total_rooms = models.PositiveIntegerField(_('total rooms'), default=1, validators=[MaxValueValidator(10000)])
    
    # Notes
    notes = models.TextField(_('notes'), blank=True)
    
    class Meta:
        verbose_name = _('availability')
        verbose_name_plural = _('availabilities')
        unique_together = [['room', 'date']]
        indexes = [
            models.Index(fields=['date', 'is_available']),
            models.Index(fields=['room', 'date']),
        ]
    
    def __str__(self):
        return f"{self.room} - {self.date} - Available: {self.is_available}"


class PropertyDocument(models.Model):
    """Legal documents for properties."""
    
    DOCUMENT_TYPES = (
        ('license', _('Business License')),
        ('permit', _('Operating Permit')),
        ('insurance', _('Insurance Certificate')),
        ('tax', _('Tax Registration')),
        ('safety', _('Safety Certificate')),
        ('other', _('Other')),
    )
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(
        _('document type'),
        max_length=50,
        choices=DOCUMENT_TYPES
    )
    document_file = models.FileField(
        _('document file'),
        upload_to='property_documents/'
    )
    document_number = models.CharField(_('document number'), max_length=100, blank=True)
    expiry_date = models.DateField(_('expiry date'), null=True, blank=True)
    is_verified = models.BooleanField(_('verified'), default=False)
    verified_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_documents'
    )
    verified_at = models.DateTimeField(_('verified at'), null=True, blank=True)
    notes = models.TextField(_('notes'), blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.property.name} - {self.get_document_type_display()}"
    
    class Meta:
        verbose_name = _('property document')
        verbose_name_plural = _('property documents')