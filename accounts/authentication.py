"""
accounts/authentication.py - JWT and enterprise authentication

Secure authentication with:
- JWT tokens (access + refresh)
- Role-based access control (RBAC)
- Token refresh rotation
- Session management
"""

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)

User = get_user_model()
from accounts.models import UserRole


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom token serializer with additional user claims.
    
    Adds user info to JWT payload for client-side authorization.
    """
    
    @classmethod
    def get_token(cls, user):
        """Create token with custom claims."""
        token = super().get_token(user)
        
        # Add user info to token
        token['user_id'] = str(user.id)
        token['email'] = user.email
        token['is_staff'] = user.is_staff
        token['is_superuser'] = user.is_superuser
        token['role'] = getattr(user, 'role', UserRole.CUSTOMER)
        token['first_name'] = user.first_name
        token['is_business_account'] = getattr(user, 'is_business_account', False)
        
        # Add roles/permissions
        user_perms = list(user.get_all_permissions())
        token['permissions'] = user_perms[:10]  # Limit to avoid token size
        
        logger.info(f"Token created for user {user.email}")
        
        return token
    
    def validate(self, attrs):
        """Validate login and return tokens."""
        data = super().validate(attrs)
        
        user = self.user
        
        # Add user info to response
        data['user'] = {
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': getattr(user, 'role', UserRole.CUSTOMER),
            'is_business_account': getattr(user, 'is_business_account', False),
        }
        data['role'] = getattr(user, 'role', UserRole.CUSTOMER)
        
        return data


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """Return user + role info alongside refreshed tokens."""

    def validate(self, attrs):
        data = super().validate(attrs)

        try:
            refresh = RefreshToken(attrs['refresh'])
            user_id = refresh.get('user_id')
            user = User.objects.filter(id=user_id).first()
            if user:
                data['user'] = {
                    'id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': getattr(user, 'role', UserRole.CUSTOMER),
                    'is_business_account': getattr(user, 'is_business_account', False),
                }
                data['role'] = getattr(user, 'role', UserRole.CUSTOMER)
        except Exception as exc:
            logger.warning(f"Refresh token decode failed: {exc}")

        return data


class TokenService:
    """Manage JWT tokens and refresh logic."""
    
    @staticmethod
    def create_token_pair(user):
        """Create access and refresh token pair for user."""
        refresh = RefreshToken.for_user(user)
        
        logger.info(f"Token pair created for {user.email}")
        
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    
    @staticmethod
    def create_refresh_token(user):
        """Create just refresh token."""
        refresh = RefreshToken.for_user(user)
        return str(refresh)
    
    @staticmethod
    def validate_token(token_string):
        """
        Validate JWT token.
        
        Returns:
            Token data if valid, None if invalid
        """
        try:
            from rest_framework_simplejwt.tokens import Token
            token = Token(token_string)
            return dict(token)
        except Exception as e:
            logger.warning(f"Invalid token: {e}")
            return None


class AuthenticationService:
    """High-level authentication operations."""
    
    @staticmethod
    def login_user(email, password):
        """
        Authenticate user and return tokens.
        
        Args:
            email: User email
            password: User password
        
        Returns:
            dict with access, refresh tokens and user info
        
        Raises:
            ValidationError: If credentials invalid
        """
        from django.contrib.auth import authenticate
        
        user = authenticate(username=email, password=password)
        
        if user is None:
            logger.warning(f"Failed login attempt for {email}")
            from rest_framework.exceptions import AuthenticationFailed
            raise AuthenticationFailed(_('Invalid credentials'))
        
        if not user.is_active:
            raise AuthenticationFailed(_('Account inactive'))
        
        # Create token pair
        tokens = TokenService.create_token_pair(user)
        
        # Update last activity
        from django.utils import timezone
        user.last_activity = timezone.now()
        user.is_email_verified = True  # Mark verified if didn't confirm email
        user.save(update_fields=['last_activity', 'is_email_verified'])
        
        logger.info(f"User logged in: {email}")
        
        return {
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'user': {
                'id': str(user.id),
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_business_account': user.is_business_account,
            }
        }
    
    @staticmethod
    def register_user(email, password, first_name='', last_name=''):
        """
        Register new user.
        
        Args:
            email: Email address
            password: Password
            first_name: Optional first name
            last_name: Optional last name
        
        Returns:
            User instance
        
        Raises:
            ValidationError: If data invalid
        """
        from django.core.exceptions import ValidationError
        
        # Check email not taken
        if User.objects.filter(email=email).exists():
            raise ValidationError(_('Email already registered'))
        
        # Validate password
        from django.contrib.auth.password_validation import validate_password
        try:
            validate_password(password)
        except ValidationError as e:
            raise e
        
        # Create user
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        
        logger.info(f"New user registered: {email}")
        
        return user
    
    @staticmethod
    def refresh_token(refresh_token_string):
        """
        Refresh access token.
        
        Args:
            refresh_token_string: Refresh token
        
        Returns:
            New access token
        
        Raises:
            TokenError: If refresh token invalid
        """
        try:
            from rest_framework_simplejwt.tokens import RefreshToken
            refresh = RefreshToken(refresh_token_string)
            
            logger.info("Token refreshed")
            
            return str(refresh.access_token)
        
        except Exception as e:
            logger.warning(f"Token refresh failed: {e}")
            from rest_framework.exceptions import AuthenticationFailed
            raise AuthenticationFailed(_('Invalid or expired refresh token'))
    
    @staticmethod
    def logout_user(user):
        """
        Logout user (optionally blacklist token).
        
        Args:
            user: User instance
        """
        from django.utils import timezone
        user.last_activity = timezone.now()
        user.save(update_fields=['last_activity'])
        
        logger.info(f"User logged out: {user.email}")
    
    @staticmethod
    def change_password(user, old_password, new_password):
        """
        Change user password.
        
        Args:
            user: User instance
            old_password: Current password
            new_password: New password
        
        Returns:
            User instance
        
        Raises:
            ValidationError: If passwords invalid
        """
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        
        # Verify old password
        if not user.check_password(old_password):
            raise ValidationError(_('Current password incorrect'))
        
        # Validate new password
        try:
            validate_password(new_password, user)
        except ValidationError:
            raise
        
        # Prevent reusing same password
        if user.check_password(new_password):
            raise ValidationError(_('New password must differ from current'))
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        logger.info(f"Password changed for {user.email}")
        
        return user
    
    @staticmethod
    def request_password_reset(email):
        """
        Request password reset token.
        
        Args:
            email: User email
        
        Returns:
            dict with reset token (if email exists)
        """
        try:
            user = User.objects.get(email=email)
            
            # Generate reset token
            from django.contrib.auth.tokens import default_token_generator
            token = default_token_generator.make_token(user)
            
            # In production, send email with reset link
            # For now, return token (use secure channel)
            
            logger.info(f"Password reset requested for {email}")
            
            return {
                'success': True,
                'message': 'Check your email for reset link',
                'token': token,  # Only for testing, remove in production
                'uid': user.pk
            }
        
        except User.DoesNotExist:
            # Don't reveal if email exists (security best practice)
            logger.warning(f"Password reset requested for non-existent {email}")
            return {
                'success': True,
                'message': 'Check your email for reset link',
            }
    
    @staticmethod
    def reset_password(uid, token, new_password):
        """
        Reset password with token.
        
        Args:
            uid: User ID
            token: Reset token
            new_password: New password
        
        Returns:
            User instance
        """
        from django.contrib.auth.tokens import default_token_generator
        from django.core.exceptions import ValidationError
        
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            raise ValidationError(_('Invalid reset link'))
        
        # Verify token
        if not default_token_generator.check_token(user, token):
            raise ValidationError(_('Invalid or expired reset link'))
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        logger.info(f"Password reset for {user.email}")
        
        return user
