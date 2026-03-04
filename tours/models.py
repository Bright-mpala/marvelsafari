from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid
from taggit.managers import TaggableManager

from core.models import SoftDeletableModel, BaseModel, UUIDTaggedItem
from properties.models import Property, PropertyStatus


class TourCategory(models.Model):
    """Tour category."""
    
    name = models.CharField(_('category name'), max_length=100)
    slug = models.SlugField(_('slug'), unique=True)
    description = models.TextField(_('description'), blank=True)
    icon = models.CharField(_('icon'), max_length=50, blank=True)
    
    # Hierarchy
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    
    display_order = models.PositiveIntegerField(_('display order'), default=0)
    is_active = models.BooleanField(_('active'), default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = _('tour category')
        verbose_name_plural = _('tour categories')
        ordering = ['display_order']


class TourOperator(models.Model):
    """Tour operator/company."""
    
    # Owner - the user who manages this operator account
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tour_operators',
        null=True,
        blank=True,
        help_text=_('User who owns/manages this tour operator account')
    )
    
    name = models.CharField(_('operator name'), max_length=255)
    slug = models.SlugField(_('slug'), unique=True)
    description = models.TextField(_('description'), blank=True)
    
    # Contact info
    website = models.URLField(_('website'), blank=True)
    phone = models.CharField(_('phone'), max_length=50, blank=True)
    email = models.EmailField(_('email'), blank=True)
    address = models.TextField(_('address'), blank=True)
    
    # Social media
    facebook = models.URLField(_('Facebook'), blank=True)
    instagram = models.URLField(_('Instagram'), blank=True)
    twitter = models.URLField(_('Twitter'), blank=True)
    
    # Verification
    is_verified = models.BooleanField(_('verified'), default=False)
    years_in_business = models.PositiveSmallIntegerField(
        _('years in business'),
        null=True,
        blank=True
    )
    
    # Ratings
    average_rating = models.DecimalField(
        _('average rating'),
        max_digits=3,
        decimal_places=2,
        default=0
    )
    review_count = models.PositiveIntegerField(_('review count'), default=0)
    
    is_active = models.BooleanField(_('active'), default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = _('tour operator')
        verbose_name_plural = _('tour operators')
        ordering = ['name']


class Tour(SoftDeletableModel):
    """Tour/Activity."""
    
    TOUR_TYPES = (
        ('guided', _('Guided Tour')),
        ('self_guided', _('Self-Guided Tour')),
        ('private', _('Private Tour')),
        ('group', _('Group Tour')),
        ('day_trip', _('Day Trip')),
        ('multi_day', _('Multi-Day Tour')),
        ('adventure', _('Adventure Tour')),
        ('cultural', _('Cultural Tour')),
        ('food', _('Food Tour')),
        ('historical', _('Historical Tour')),
    )
    
    DIFFICULTY_LEVELS = (
        ('easy', _('Easy')),
        ('moderate', _('Moderate')),
        ('difficult', _('Difficult')),
        ('challenging', _('Challenging')),
    )
    
    name = models.CharField(_('tour name'), max_length=255)
    slug = models.SlugField(_('slug'), max_length=300, unique=True)
    description = models.TextField(_('description'))
    
    # Basic info
    operator = models.ForeignKey(
        TourOperator,
        on_delete=models.CASCADE,
        related_name='tours'
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name='tours',
        null=True,
        blank=True,
        help_text=_('Related property – must be approved before tour activation')
    )
    categories = models.ManyToManyField(TourCategory, related_name='tours', blank=True)
    tour_type = models.CharField(
        _('tour type'),
        max_length=50,
        choices=TOUR_TYPES
    )
    
    # Location
    location = models.CharField(_('location'), max_length=255)
    city = models.CharField(_('city'), max_length=100)
    country = models.CharField(_('country'), max_length=100)
    meeting_point = models.TextField(_('meeting point'), blank=True)
    dropoff_point = models.TextField(_('dropoff point'), blank=True)
    
    # Coordinates
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
    
    # Duration
    duration_hours = models.PositiveSmallIntegerField(_('duration (hours)'), default=2)
    duration_days = models.PositiveSmallIntegerField(_('duration (days)'), default=0)
    
    # Difficulty
    difficulty = models.CharField(
        _('difficulty'),
        max_length=20,
        choices=DIFFICULTY_LEVELS,
        default='easy'
    )
    
    # Capacity
    min_participants = models.PositiveSmallIntegerField(_('minimum participants'), default=1)
    max_participants = models.PositiveSmallIntegerField(_('maximum participants'), default=20)
    capacity = models.PositiveSmallIntegerField(_('capacity'), default=0, help_text=_('Hard cap for participants'))
    
    # Age restrictions
    min_age = models.PositiveSmallIntegerField(_('minimum age'), null=True, blank=True)
    max_age = models.PositiveSmallIntegerField(_('maximum age'), null=True, blank=True)
    
    # What's included
    inclusions = models.TextField(_('what\'s included'), blank=True)
    exclusions = models.TextField(_('what\'s not included'), blank=True)
    
    # Requirements
    requirements = models.TextField(_('requirements'), blank=True)
    what_to_bring = models.TextField(_('what to bring'), blank=True)
    
    # Cancellation policy
    cancellation_policy = models.TextField(_('cancellation policy'), blank=True)
    
    # Language
    languages = models.JSONField(
        _('languages'),
        default=list,
        help_text=_('Available languages for the tour')
    )
    
    # Schedule
    schedule = models.JSONField(
        _('schedule'),
        default=list,
        help_text=_('Tour schedule in JSON format')
    )
    schedule_date = models.DateField(_('schedule date'), null=True, blank=True)
    
    # Highlights
    highlights = models.JSONField(
        _('highlights'),
        default=list,
        help_text=_('Tour highlights')
    )
    
    # Pricing
    base_price = models.DecimalField(_('base price'), max_digits=10, decimal_places=2)
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    
    # Discounts
    child_price = models.DecimalField(
        _('child price'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    senior_price = models.DecimalField(
        _('senior price'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    group_discount = models.DecimalField(
        _('group discount'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Percentage discount for groups')
    )
    
    # Status
    is_active = models.BooleanField(_('active'), default=True)
    is_featured = models.BooleanField(_('featured'), default=False)
    
    # Ratings
    average_rating = models.DecimalField(
        _('average rating'),
        max_digits=3,
        decimal_places=2,
        default=0
    )
    review_count = models.PositiveIntegerField(_('review count'), default=0)
    booking_count = models.PositiveIntegerField(_('booking count'), default=0)
    
    # SEO
    meta_title = models.CharField(_('meta title'), max_length=255, blank=True)
    meta_description = models.TextField(_('meta description'), blank=True)
    
    tags = TaggableManager(blank=True, through=UUIDTaggedItem)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = _('tour')
        verbose_name_plural = _('tours')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['city', 'country']),
            models.Index(fields=['is_active', 'is_featured']),
        ]
    
    def clean(self):
        if self.property and self.is_active and self.property.status not in {PropertyStatus.APPROVED, PropertyStatus.ACTIVE}:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('Tour cannot be active unless the linked property is approved.'))

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)

        # Auto-disable tour if property is not approved
        if self.property and self.property.status not in {PropertyStatus.APPROVED, PropertyStatus.ACTIVE}:
            self.is_active = False

        if not self.capacity:
            self.capacity = self.max_participants

        self.full_clean()
        super().save(*args, **kwargs)


class TourImage(BaseModel):
    """Tour images."""
    
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(_('image'), upload_to='tours/')
    caption = models.CharField(_('caption'), max_length=255, blank=True)
    alt_text = models.CharField(_('alt text'), max_length=255, blank=True)
    is_primary = models.BooleanField(_('primary image'), default=False)
    display_order = models.PositiveIntegerField(_('display order'), default=0)
    
    def __str__(self):
        return f"Image for {self.tour.name}"
    
    class Meta:
        verbose_name = _('tour image')
        verbose_name_plural = _('tour images')
        ordering = ['display_order']


class TourSchedule(BaseModel):
    """Specific tour dates and times."""
    
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField(_('date'))
    start_time = models.TimeField(_('start time'))
    end_time = models.TimeField(_('end time'))
    
    # Availability
    available_spots = models.PositiveIntegerField(_('available spots'))
    total_spots = models.PositiveIntegerField(_('total spots'))
    
    # Pricing (can override tour base price)
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Status
    is_available = models.BooleanField(_('available'), default=True)
    is_booked_out = models.BooleanField(_('booked out'), default=False)
    
    # Guide
    guide_name = models.CharField(_('guide name'), max_length=100, blank=True)
    guide_contact = models.CharField(_('guide contact'), max_length=100, blank=True)
    
    # Notes
    notes = models.TextField(_('notes'), blank=True)
    
    def __str__(self):
        return f"{self.tour.name} - {self.date} {self.start_time}"
    
    class Meta:
        verbose_name = _('tour schedule')
        verbose_name_plural = _('tour schedules')
        ordering = ['date', 'start_time']
        unique_together = ['tour', 'date', 'start_time']


class TourBooking(models.Model):
    """Tour booking."""
    
    BOOKING_STATUS = (
        ('pending', _('Pending')),
        ('confirmed', _('Confirmed')),
        ('paid', _('Paid')),
        ('cancelled', _('Cancelled')),
        ('completed', _('Completed')),
        ('no_show', _('No Show')),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_reference = models.CharField(
        _('booking reference'),
        max_length=20,
        unique=True,
        editable=False
    )
    
    # User
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='tour_bookings'
    )
    
    # Tour details
    tour = models.ForeignKey(Tour, on_delete=models.PROTECT, related_name='tour_bookings')
    tour_schedule = models.ForeignKey(
        TourSchedule,
        on_delete=models.PROTECT,
        related_name='tour_bookings',
        null=True,
        blank=True
    )
    
    # Participants
    participant_count = models.PositiveSmallIntegerField(_('participant count'), default=1)
    participants = models.JSONField(
        _('participants'),
        default=list,
        blank=True,
        help_text=_('Participant details in JSON format')
    )
    
    # Contact person
    contact_name = models.CharField(_('contact name'), max_length=255)
    contact_email = models.EmailField(_('contact email'))
    contact_phone = models.CharField(_('contact phone'), max_length=50)
    
    # Pricing
    base_price = models.DecimalField(_('base price'), max_digits=10, decimal_places=2)
    taxes = models.DecimalField(_('taxes'), max_digits=10, decimal_places=2, default=0)
    service_fee = models.DecimalField(_('service fee'), max_digits=10, decimal_places=2, default=0)
    
    # Discounts
    child_discount = models.DecimalField(
        _('child discount'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    senior_discount = models.DecimalField(
        _('senior discount'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    group_discount = models.DecimalField(
        _('group discount'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    coupon_discount = models.DecimalField(
        _('coupon discount'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    coupon_code = models.CharField(_('coupon code'), max_length=50, blank=True)
    
    # Totals
    subtotal = models.DecimalField(_('subtotal'), max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(_('total amount'), max_digits=10, decimal_places=2)
    
    # Currency
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    
    # Payment
    payment_status = models.CharField(
        _('payment status'),
        max_length=20,
        choices=(
            ('pending', _('Pending')),
            ('paid', _('Paid')),
            ('failed', _('Failed')),
            ('refunded', _('Refunded')),
        ),
        default='pending'
    )
    amount_paid = models.DecimalField(
        _('amount paid'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=BOOKING_STATUS,
        default='pending'
    )
    
    # Special requests
    special_requests = models.TextField(_('special requests'), blank=True)
    dietary_restrictions = models.TextField(_('dietary restrictions'), blank=True)
    
    # Business booking
    is_business_booking = models.BooleanField(_('business booking'), default=False)
    business_account = models.ForeignKey(
        'accounts.BusinessAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tour_bookings'
    )
    
    # Attendance
    checked_in = models.BooleanField(_('checked in'), default=False)
    checked_in_at = models.DateTimeField(_('checked in at'), null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('tour booking')
        verbose_name_plural = _('tour bookings')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Tour Booking {self.booking_reference}"
    
    def save(self, *args, **kwargs):
        if not self.booking_reference:
            import random
            import string
            self.booking_reference = 'TOUR-' + ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            )
        
        # Calculate totals
        self.subtotal = self.base_price * self.participant_count
        
        self.total_amount = (
            self.subtotal +
            self.taxes +
            self.service_fee -
            self.child_discount -
            self.senior_discount -
            self.group_discount -
            self.coupon_discount
        )
        
        if self.total_amount < 0:
            self.total_amount = 0
        
        super().save(*args, **kwargs)