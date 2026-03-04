"""
properties/forms.py - Secure Forms for Property Management

Production-ready forms with:
- Overposting protection (explicit field whitelisting)
- Validation hooks
- Security-focused design
- Status field protection
"""

from django import forms
from django_countries.fields import CountryField
from django_countries.widgets import CountrySelectWidget
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Property, Amenity, PropertyImage


class PropertySearchForm(forms.Form):
    """Form for searching properties."""
    
    location = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Where are you going?'})
    )
    check_in = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    check_out = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    guests = forms.IntegerField(
        required=False,
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'min': 1})
    )


class PropertyCreateForm(forms.ModelForm):
    """
    Secure property creation form.
    
    SECURITY FEATURES:
    - Explicit field whitelist (only these fields can be set)
    - Status is NOT included (forced to PENDING by service layer)
    - Owner is NOT included (set by service layer from authenticated user)
    - No admin-only fields exposed
    
    The service layer handles:
    - Setting owner to request.user
    - Forcing status to DRAFT/PENDING
    - Generating unique slug
    - Triggering notifications
    """
    
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("Select Amenities")
    )
    
    class Meta:
        model = Property
        # SECURITY: Explicit whitelist - only these fields can be submitted
        # Status, owner, slug, approval fields are intentionally EXCLUDED
        fields = [
            'name', 
            'description', 
            'property_type',
            'star_rating',
            'address', 
            'city', 
            'state', 
            'postal_code', 
            'country',
            'latitude',
            'longitude',
            'phone', 
            'email',
            'website', 
            'check_in_time', 
            'check_out_time',
            'earliest_check_in',
            'latest_check_out',
            'minimum_price', 
            'maximum_price',
            'manager_name',
            'manager_phone',
            'manager_email',
            'cancellation_policy',
            'house_rules',
            'special_instructions',
            'total_rooms',
            'year_built',
            'year_renovated',
            'amenities',
            'meta_title',
            'meta_description',
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'E.g. Pine Valley Lodge, Sunrise Resort...',
                'class': 'styled-input',
                'maxlength': '255',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Describe your property in detail. Include unique features, nearby attractions, and what makes it special...',
                'class': 'styled-textarea',
                'minlength': '50',
                'required': True,
            }),
            'address': forms.TextInput(attrs={
                'placeholder': '123 Main Street, Near Central Park',
                'class': 'styled-input',
                'required': True,
            }),
            'city': forms.TextInput(attrs={
                'placeholder': 'City name',
                'class': 'styled-input',
                'required': True,
            }),
            'state': forms.TextInput(attrs={
                'placeholder': 'State/Province',
                'class': 'styled-input',
            }),
            'postal_code': forms.TextInput(attrs={
                'placeholder': 'Postal Code',
                'class': 'styled-input',
            }),
            'country': CountrySelectWidget(attrs={
                'class': 'styled-input',
            }),
            'latitude': forms.NumberInput(attrs={
                'placeholder': 'e.g. 40.7128',
                'class': 'styled-input',
                'step': '0.000001',
            }),
            'longitude': forms.NumberInput(attrs={
                'placeholder': 'e.g. -74.0060',
                'class': 'styled-input',
                'step': '0.000001',
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': '+1 234 567 8900',
                'class': 'styled-input',
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'contact@yourproperty.com',
                'class': 'styled-input',
            }),
            'website': forms.URLInput(attrs={
                'placeholder': 'https://www.yourproperty.com',
                'class': 'styled-input',
            }),
            'check_in_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'styled-input',
            }),
            'check_out_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'styled-input',
            }),
            'earliest_check_in': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'styled-input',
            }),
            'latest_check_out': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'styled-input',
            }),
            'minimum_price': forms.NumberInput(attrs={
                'placeholder': 'Minimum nightly rate',
                'step': '0.01',
                'min': '0',
                'class': 'styled-input',
            }),
            'maximum_price': forms.NumberInput(attrs={
                'placeholder': 'Maximum nightly rate',
                'step': '0.01',
                'min': '0',
                'class': 'styled-input',
            }),
            'manager_name': forms.TextInput(attrs={
                'placeholder': 'Property manager name',
                'class': 'styled-input',
            }),
            'manager_phone': forms.TextInput(attrs={
                'placeholder': 'Manager phone number',
                'class': 'styled-input',
            }),
            'manager_email': forms.EmailInput(attrs={
                'placeholder': 'manager@yourproperty.com',
                'class': 'styled-input',
            }),
            'cancellation_policy': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Describe your cancellation policy...',
                'class': 'styled-textarea',
            }),
            'house_rules': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'List any house rules guests should follow...',
                'class': 'styled-textarea',
            }),
            'special_instructions': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Any special instructions for guests...',
                'class': 'styled-textarea',
            }),
            'total_rooms': forms.NumberInput(attrs={
                'min': '1',
                'max': '10000',
                'class': 'styled-input',
            }),
            'year_built': forms.NumberInput(attrs={
                'placeholder': 'e.g. 2020',
                'min': '1800',
                'class': 'styled-input',
            }),
            'year_renovated': forms.NumberInput(attrs={
                'placeholder': 'e.g. 2023',
                'min': '1800',
                'class': 'styled-input',
            }),
            'star_rating': forms.Select(attrs={
                'class': 'styled-select',
            }),
            'meta_title': forms.TextInput(attrs={
                'placeholder': 'SEO title (optional)',
                'class': 'styled-input',
                'maxlength': '255',
            }),
            'meta_description': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'SEO description (optional)',
                'class': 'styled-textarea',
            }),
        }
    
    def clean_name(self):
        """Validate property name for security."""
        name = self.cleaned_data.get('name', '')
        if not name or len(name.strip()) < 3:
            raise ValidationError(_('Property name must be at least 3 characters.'))
        
        # XSS prevention
        import re
        forbidden_patterns = [r'<script', r'javascript:', r'on\w+\s*=']
        for pattern in forbidden_patterns:
            if re.search(pattern, name, re.IGNORECASE):
                raise ValidationError(_('Property name contains invalid content.'))
        
        return name.strip()
    
    def clean_description(self):
        """Validate description length and content."""
        description = self.cleaned_data.get('description', '')
        if not description or len(description.strip()) < 50:
            raise ValidationError(
                _('Please provide a detailed description (at least 50 characters).')
            )
        
        # XSS prevention
        import re
        forbidden_patterns = [r'<script', r'javascript:', r'on\w+\s*=', r'data:text/html']
        for pattern in forbidden_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                raise ValidationError(_('Description contains invalid content.'))
        
        return description.strip()
    
    def clean(self):
        """Cross-field validation."""
        cleaned_data = super().clean()
        
        # Validate price range
        min_price = cleaned_data.get('minimum_price')
        max_price = cleaned_data.get('maximum_price')
        
        if min_price is not None and max_price is not None:
            if min_price > max_price:
                raise ValidationError({
                    'minimum_price': _('Minimum price cannot exceed maximum price.')
                })
        
        # Validate coordinates pair
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')
        
        if (latitude is not None) != (longitude is not None):
            raise ValidationError({
                'latitude': _('Both latitude and longitude must be provided together.')
            })
        
        # Validate year renovated vs year built
        year_built = cleaned_data.get('year_built')
        year_renovated = cleaned_data.get('year_renovated')
        
        if year_built and year_renovated and year_renovated < year_built:
            raise ValidationError({
                'year_renovated': _('Year renovated cannot be before year built.')
            })
        
        return cleaned_data


class PropertyEditForm(PropertyCreateForm):
    """
    Form for editing existing properties.
    
    Inherits from PropertyCreateForm with same security constraints.
    Status changes must go through PropertyService.
    """
    
    class Meta(PropertyCreateForm.Meta):
        # Same fields as create form - no additional privileged fields
        pass


class PropertyImageUploadForm(forms.Form):
    """
    Form for uploading property images.
    
    Images are handled via custom HTML file input with 'multiple' attribute.
    This form validates the upload data.
    """
    
    caption = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Image caption (optional)',
            'class': 'styled-input',
        })
    )
    
    alt_text = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Alt text for accessibility (optional)',
            'class': 'styled-input',
        })
    )
    
    is_primary = forms.BooleanField(
        required=False,
        label=_('Set as primary image')
    )


class AdminPropertyApprovalForm(forms.Form):
    """
    Admin form for approving/rejecting properties.
    
    Only accessible to admin users via admin views.
    """
    
    ACTION_CHOICES = [
        ('approve', _('Approve')),
        ('reject', _('Reject')),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect,
        required=True
    )
    
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Reason for rejection (required if rejecting)...',
            'class': 'styled-textarea',
        }),
        required=False
    )
    
    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Internal notes (optional)...',
            'class': 'styled-textarea',
        }),
        required=False
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        if action == 'reject' and not rejection_reason:
            raise ValidationError({
                'rejection_reason': _('Rejection reason is required when rejecting a property.')
            })
        
        return cleaned_data
