from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid


class UserRole(models.TextChoices):
    """Platform-wide roles for coarse-grained access control."""
    CUSTOMER = "customer", _("Customer")
    HOST = "host", _("Host")
    CAR_OWNER = "car_owner", _("Car Owner")
    ADMIN = "admin", _("Admin")


class UserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('role', UserRole.CUSTOMER)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class EmailVerification(models.Model):
    """Email verification codes for user authentication."""
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='email_verification')
    code = models.CharField(max_length=6, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"Verification for {self.user.email} - {self.code}"

    def is_valid(self):
        """Check if verification code is still valid."""
        return not self.is_used and timezone.now() < self.expires_at

    class Meta:
        verbose_name = _('email verification')
        verbose_name_plural = _('email verifications')


class User(AbstractUser):
    """Custom User model with email as unique identifier."""
    
    username = None
    email = models.EmailField(_('email address'), unique=True)
    
    # Personal Information
    phone_number = PhoneNumberField(_('phone number'), blank=True)
    date_of_birth = models.DateField(_('date of birth'), null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    role = models.CharField(
        _('role'),
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
        help_text=_('Determines platform permissions such as host or admin')
    )
    
    # Address Information
    address = models.CharField(_('address'), max_length=255, blank=True)
    city = models.CharField(_('city'), max_length=100, blank=True)
    state = models.CharField(_('state/province'), max_length=100, blank=True)
    postal_code = models.CharField(_('postal code'), max_length=20, blank=True)
    country = CountryField(_('country'), blank=True)
    
    # Preferences
    preferred_language = models.CharField(
        _('preferred language'),
        max_length=10,
        default='en',
        choices=[
            ('en', 'English'),
            ('es', 'Spanish'),
            ('fr', 'French'),
            ('de', 'German'),
        ]
    )
    preferred_currency = models.CharField(
        _('preferred currency'),
        max_length=3,
        default='USD',
        choices=[
            ('USD', 'US Dollar'),
            ('EUR', 'Euro'),
            ('GBP', 'British Pound'),
        ]
    )
    
    # Account settings
    is_email_verified = models.BooleanField(_('email verified'), default=False)
    is_phone_verified = models.BooleanField(_('phone verified'), default=False)
    marketing_opt_in = models.BooleanField(_('marketing opt-in'), default=True)
    
    # Business account flag
    is_business_account = models.BooleanField(_('business account'), default=False)
    
    # Timestamps
    email_verified_at = models.DateTimeField(_('email verified at'), null=True, blank=True)
    phone_verified_at = models.DateTimeField(_('phone verified at'), null=True, blank=True)
    last_activity = models.DateTimeField(_('last activity'), auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    def __str__(self):
        return self.email
    
    @property
    def full_name(self):
        """Return the full name of the user."""
        return f"{self.first_name} {self.last_name}".strip()

    # Role helpers for RBAC checks
    @property
    def is_customer(self):
        return self.role == UserRole.CUSTOMER

    @property
    def is_host(self):
        return self.role == UserRole.HOST

    @property
    def is_car_owner(self):
        return self.role == UserRole.CAR_OWNER

    @property
    def is_platform_admin(self):
        return self.role == UserRole.ADMIN or self.is_superuser
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')


class UserProfile(models.Model):
    """Extended user profile information."""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Travel preferences
    travel_style = models.CharField(
        _('travel style'),
        max_length=50,
        blank=True,
        choices=[
            ('budget', 'Budget Traveler'),
            ('luxury', 'Luxury Traveler'),
            ('business', 'Business Traveler'),
            ('family', 'Family Traveler'),
            ('adventure', 'Adventure Seeker'),
            ('relaxation', 'Relaxation Seeker'),
        ]
    )
    
    accommodation_preferences = models.JSONField(
        _('accommodation preferences'),
        default=dict,
        blank=True,
        help_text=_('Preferred accommodation types and amenities')
    )
    
    flight_preferences = models.JSONField(
        _('flight preferences'),
        default=dict,
        blank=True,
        help_text=_('Preferred airlines, seat types, etc.')
    )
    
    # Loyalty programs
    frequent_flyer_numbers = models.JSONField(
        _('frequent flyer numbers'),
        default=dict,
        blank=True,
        help_text=_('Airline loyalty program numbers')
    )
    
    # Documents (for verification)
    passport_number = models.CharField(_('passport number'), max_length=50, blank=True)
    passport_expiry = models.DateField(_('passport expiry date'), null=True, blank=True)
    id_document = models.FileField(_('ID document'), upload_to='id_documents/', blank=True, null=True)
    
    # Emergency contact
    emergency_contact_name = models.CharField(_('emergency contact name'), max_length=100, blank=True)
    emergency_contact_phone = PhoneNumberField(_('emergency contact phone'), blank=True)
    emergency_contact_relationship = models.CharField(
        _('relationship'),
        max_length=50,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile for {self.user.email}"
    
    class Meta:
        verbose_name = _('user profile')
        verbose_name_plural = _('user profiles')


class BusinessAccount(models.Model):
    """Business account for corporate travel."""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='business_account')
    company_name = models.CharField(_('company name'), max_length=255)
    company_registration_number = models.CharField(_('registration number'), max_length=100, blank=True)
    company_vat_number = models.CharField(_('VAT number'), max_length=100, blank=True)
    
    # Company details
    company_size = models.CharField(
        _('company size'),
        max_length=50,
        choices=[
            ('1-10', '1-10 employees'),
            ('11-50', '11-50 employees'),
            ('51-200', '51-200 employees'),
            ('201-500', '201-500 employees'),
            ('501-1000', '501-1000 employees'),
            ('1000+', '1000+ employees'),
        ]
    )
    
    industry = models.CharField(_('industry'), max_length=100, blank=True)
    company_address = models.TextField(_('company address'), blank=True)
    company_phone = PhoneNumberField(_('company phone'), blank=True)
    company_email = models.EmailField(_('company email'), blank=True)
    
    # Billing information
    billing_address = models.TextField(_('billing address'), blank=True)
    payment_terms = models.CharField(
        _('payment terms'),
        max_length=50,
        default='net30',
        choices=[
            ('prepaid', 'Prepaid'),
            ('net15', 'Net 15'),
            ('net30', 'Net 30'),
            ('net60', 'Net 60'),
        ]
    )
    
    # Settings
    approval_required = models.BooleanField(
        _('approval required'),
        default=False,
        help_text=_('Whether bookings require approval')
    )
    
    spending_limit = models.DecimalField(
        _('monthly spending limit'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    travel_policy = models.TextField(_('travel policy'), blank=True)
    
    # Verification
    is_verified = models.BooleanField(_('verified'), default=False)
    verified_at = models.DateTimeField(_('verified at'), null=True, blank=True)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_business_accounts'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.company_name} - {self.user.email}"
    
    class Meta:
        verbose_name = _('business account')
        verbose_name_plural = _('business accounts')