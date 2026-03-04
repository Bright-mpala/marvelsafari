from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, PasswordChangeForm
from django.utils.translation import gettext_lazy as _
from .models import User, UserProfile, BusinessAccount
from locations.models import Country
from django_countries import countries as django_countries_list
from phonenumber_field.formfields import PhoneNumberField
import re


class CustomUserCreationForm(UserCreationForm):
    """Custom user registration form with email verification."""
    
    email = forms.EmailField(
        label=_('Email Address'),
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003580] focus:border-transparent transition-colors',
            'placeholder': _('Enter your email'),
        })
    )
    first_name = forms.CharField(
        max_length=30,
        label=_('First Name'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003580] focus:border-transparent transition-colors',
            'placeholder': _('First name'),
        })
    )
    last_name = forms.CharField(
        max_length=30,
        label=_('Last Name'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003580] focus:border-transparent transition-colors',
            'placeholder': _('Last name'),
        })
    )
    phone_number = PhoneNumberField(
        required=False,
        label=_('Phone Number'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003580] focus:border-transparent transition-colors',
            'placeholder': _('+1234567890 (optional)'),
        })
    )
    date_of_birth = forms.DateField(
        required=False,
        label=_('Date of Birth'),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003580] focus:border-transparent transition-colors',
        })
    )
    country = forms.ChoiceField(
        required=False,
        label=_('Country'),
        choices=(),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003580] focus:border-transparent transition-colors',
        })
    )
    
    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003580] focus:border-transparent transition-colors pr-10',
            'placeholder': _('Create a password'),
            'id': 'password1',
        }),
        help_text=_("At least 8 characters, mix of letters and numbers")
    )
    password2 = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003580] focus:border-transparent transition-colors pr-10',
            'placeholder': _('Confirm your password'),
            'id': 'password2',
        })
    )
    
    terms_accepted = forms.BooleanField(
        required=True,
        label=_('I agree to the Terms of Service and Privacy Policy'),
        widget=forms.CheckboxInput(attrs={
            'class': 'rounded text-[#003580] focus:ring-[#003580]',
        })
    )
    
    marketing_opt_in = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Receive special offers and travel tips'),
        widget=forms.CheckboxInput(attrs={
            'class': 'rounded text-[#003580] focus:ring-[#003580]',
        })
    )

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone_number', 'date_of_birth', 'country')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate country dropdown; fallback to django_countries if reference table is empty
        country_qs = list(Country.objects.order_by('name').values_list('iso2', 'name'))
        if not country_qs:
            country_qs = list(django_countries_list)
        self.fields['country'].choices = [('', 'Select Country')] + [(code, name) for code, name in country_qs]

    def clean_email(self):
        """Validate email is unique."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_('This email is already registered.'))
        return email
    
    def clean_password1(self):
        """Validate password strength."""
        password = self.cleaned_data.get('password1')
        
        if len(password) < 8:
            raise forms.ValidationError(_('Password must be at least 8 characters long.'))
        
        if not re.search(r'[A-Z]', password):
            raise forms.ValidationError(_('Password must contain at least one uppercase letter.'))
        
        if not re.search(r'[a-z]', password):
            raise forms.ValidationError(_('Password must contain at least one lowercase letter.'))
        
        if not re.search(r'\d', password):
            raise forms.ValidationError(_('Password must contain at least one number.'))
        
        if not re.search(r'[@$!%*?&#]', password):
            raise forms.ValidationError(_('Password must contain at least one special character (@$!%*?&#).'))
        
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.phone_number = self.cleaned_data.get('phone_number')
        user.date_of_birth = self.cleaned_data.get('date_of_birth')
        user.country = self.cleaned_data.get('country') or ''
        user.marketing_opt_in = self.cleaned_data.get('marketing_opt_in', True)
        
        if commit:
            user.save()
            # Create user profile
            UserProfile.objects.get_or_create(user=user)
        return user


class EmailVerificationForm(forms.Form):
    """Form for email verification code."""
    code = forms.CharField(
        max_length=6,
        min_length=6,
        label=_('Verification Code'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003580] focus:border-transparent transition-colors text-center text-2xl tracking-widest',
            'placeholder': '• • • • • •',
            'autocomplete': 'off',
            'maxlength': '6',
        })
    )


class ResendVerificationForm(forms.Form):
    """Form to resend verification email."""
    email = forms.EmailField(
        label=_('Email Address'),
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003580] focus:border-transparent transition-colors',
            'placeholder': _('Enter your email'),
        })
    )


class CustomUserChangeForm(UserChangeForm):
    """Custom user profile change form."""

    password = None  # Remove password field

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone_number', 'date_of_birth', 'country', 'profile_picture')
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'country': forms.Select(attrs={'class': 'form-control'}),
            'profile_picture': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class UserProfileForm(forms.ModelForm):
    """User profile preferences form."""

    class Meta:
        model = UserProfile
        fields = [
            'travel_style', 'accommodation_preferences', 'flight_preferences',
            'frequent_flyer_numbers', 'passport_number', 'passport_expiry',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship'
        ]
        widgets = {
            'travel_style': forms.Select(attrs={'class': 'form-control'}),
            'accommodation_preferences': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Your preferred accommodation types and amenities (optional)')
            }),
            'flight_preferences': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Your preferred airlines, seat types, etc. (optional)')
            }),
            'frequent_flyer_numbers': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('JSON format: {"airline": "number"} (optional)')
            }),
            'passport_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('(optional)')
            }),
            'passport_expiry': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
            }),
            'emergency_contact_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('(optional)')
            }),
            'emergency_contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('(optional)')
            }),
            'emergency_contact_relationship': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., Spouse, Parent (optional)')
            }),
        }


class BusinessAccountForm(forms.ModelForm):
    """Business account setup form."""

    class Meta:
        model = BusinessAccount
        fields = [
            'company_name', 'company_registration_number', 'company_vat_number',
            'company_size', 'industry', 'company_address', 'company_phone',
            'company_email', 'billing_address', 'payment_terms', 'spending_limit',
            'travel_policy'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'company_vat_number': forms.TextInput(attrs={'class': 'form-control'}),
            'company_size': forms.Select(attrs={'class': 'form-control'}),
            'industry': forms.TextInput(attrs={'class': 'form-control'}),
            'company_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
            }),
            'company_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'company_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'billing_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
            }),
            'payment_terms': forms.Select(attrs={'class': 'form-control'}),
            'spending_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
            }),
            'travel_policy': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Company travel policy and restrictions')
            }),
        }


class UserPasswordChangeForm(PasswordChangeForm):
    """Custom password change form."""
    
    old_password = forms.CharField(
        label=_("Current Password"),
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password1 = forms.CharField(
        label=_("New Password"),
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password2 = forms.CharField(
        label=_("Confirm New Password"),
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )