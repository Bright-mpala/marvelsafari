from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

from bookings.models import Booking


class Review(models.Model):
    """Guest reviews for properties."""
    
    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='review'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    property = models.ForeignKey(
        'properties.Property',
        on_delete=models.CASCADE,
        related_name='reviews'
    )

    verified_booking = models.BooleanField(_('verified booking'), default=False)
    
    # Ratings
    overall_rating = models.DecimalField(
        _('overall rating'),
        max_digits=2,
        decimal_places=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    cleanliness = models.PositiveSmallIntegerField(
        _('cleanliness'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    comfort = models.PositiveSmallIntegerField(
        _('comfort'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    location = models.PositiveSmallIntegerField(
        _('location'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    facilities = models.PositiveSmallIntegerField(
        _('facilities'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    staff = models.PositiveSmallIntegerField(
        _('staff'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    value_for_money = models.PositiveSmallIntegerField(
        _('value for money'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    
    # Review Content
    title = models.CharField(_('review title'), max_length=200)
    comment = models.TextField(_('comment'))
    positive_comment = models.TextField(_('what you liked'), blank=True)
    negative_comment = models.TextField(_('what could be improved'), blank=True)
    
    # Status
    is_verified = models.BooleanField(_('verified'), default=False)
    is_featured = models.BooleanField(_('featured'), default=False)
    is_published = models.BooleanField(_('published'), default=True)
    
    # Helpfulness
    helpful_count = models.PositiveIntegerField(_('helpful count'), default=0)
    not_helpful_count = models.PositiveIntegerField(_('not helpful count'), default=0)
    
    # Response
    owner_response = models.TextField(_('owner response'), blank=True)
    owner_response_date = models.DateTimeField(
        _('response date'),
        null=True,
        blank=True
    )
    
    # Metadata
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.TextField(_('user agent'), blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('review')
        verbose_name_plural = _('reviews')
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['booking', 'user'], name='unique_booking_review_per_user'),
            models.UniqueConstraint(fields=['user', 'property'], name='unique_property_review_per_user'),
        ]
        indexes = [
            models.Index(fields=['property', 'is_published']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"Review for {self.property.name} by {self.user.email}"

    def clean(self):
        """Model-level validation ensuring review is tied to a valid booking.

        Use booking_id instead of the related booking object to avoid
        triggering RelatedObjectDoesNotExist when the FK hasn't been
        assigned yet (e.g. during ModelForm validation).
        """
        # Skip cross-object validation until relations are attached in the view.
        # The review_create view ensures booking, user, and property are set
        # correctly before saving, and database constraints enforce uniqueness.
        if not self.booking_id or not self.user_id or not self.property_id:
            return

        booking = self.booking

        if booking.status != Booking.BookingStatus.COMPLETED:
            raise ValidationError(_('Only completed bookings can be reviewed.'))
        if booking.user_id != self.user_id:
            raise ValidationError(_('You can only review your own bookings.'))
        if booking.property_id != self.property_id:
            raise ValidationError(_('Booking does not match the reviewed property.'))
    
    def save(self, *args, **kwargs):
        # Calculate average if sub-ratings are provided
        sub_ratings = [
            self.cleanliness,
            self.comfort,
            self.location,
            self.facilities,
            self.staff,
            self.value_for_money,
        ]
        valid_ratings = [r for r in sub_ratings if r is not None]
        
        if valid_ratings:
            self.overall_rating = sum(valid_ratings) / len(valid_ratings)

        # Mark review as verified when linked booking is completed
        if self.booking:
            self.verified_booking = self.booking.status == Booking.BookingStatus.COMPLETED
        
        super().save(*args, **kwargs)
        
        # Update property average rating
        self.update_property_rating()
    
    def update_property_rating(self):
        """Update property's average rating and review count."""
        property_reviews = Review.objects.filter(
            property=self.property,
            is_published=True
        )
        
        if property_reviews.exists():
            avg_rating = property_reviews.aggregate(
                models.Avg('overall_rating')
            )['overall_rating__avg']
            
            self.property.average_rating = round(avg_rating, 2)
            self.property.review_count = property_reviews.count()
            self.property.save()


class ReviewImage(models.Model):
    """Images attached to reviews."""
    
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(_('image'), upload_to='review_images/')
    caption = models.CharField(_('caption'), max_length=255, blank=True)
    is_primary = models.BooleanField(_('primary image'), default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Image for review {self.review.id}"
    
    class Meta:
        verbose_name = _('review image')
        verbose_name_plural = _('review images')


class ReviewHelpful(models.Model):
    """Track which users found reviews helpful."""
    
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='helpful_votes'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='helpful_votes'
    )
    is_helpful = models.BooleanField(_('helpful'))
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('review helpful vote')
        verbose_name_plural = _('review helpful votes')
        unique_together = ['review', 'user']
    
    def __str__(self):
        return f"{self.user.email} - {'Helpful' if self.is_helpful else 'Not Helpful'}"


class ReviewReport(models.Model):
    """Report inappropriate reviews."""
    
    REVIEW_REPORT_REASONS = (
        ('spam', _('Spam')),
        ('inappropriate', _('Inappropriate Content')),
        ('fake', _('Fake Review')),
        ('offensive', _('Offensive Language')),
        ('irrelevant', _('Irrelevant')),
        ('other', _('Other')),
    )
    
    REPORT_STATUS = (
        ('pending', _('Pending')),
        ('reviewed', _('Reviewed')),
        ('dismissed', _('Dismissed')),
        ('action_taken', _('Action Taken')),
    )
    
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='reports'
    )
    reported_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='review_reports'
    )
    reason = models.CharField(
        _('reason'),
        max_length=50,
        choices=REVIEW_REPORT_REASONS
    )
    description = models.TextField(_('description'), blank=True)
    
    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=REPORT_STATUS,
        default='pending'
    )
    reviewed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_reports'
    )
    review_notes = models.TextField(_('review notes'), blank=True)
    action_taken = models.TextField(_('action taken'), blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(_('reviewed at'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('review report')
        verbose_name_plural = _('review reports')
        unique_together = ['review', 'reported_by']
    
    def __str__(self):
        return f"Report for review {self.review.id} by {self.reported_by.email}"