"""
accounts/permissions.py - Role-based access control (RBAC) and permissions

Fine-grained permission classes for DRF:
- User can only access their own data
- Property owners can manage their properties
- Admins have full access
- Custom business logic permissions
"""

from rest_framework.permissions import BasePermission, IsAuthenticated
from django.contrib.auth.models import Permission
import logging

from accounts.models import UserRole

logger = logging.getLogger(__name__)


class IsPropertyOwner(IsAuthenticated):
    """
    Permission: User is the owner of a property.
    
    Used for property management endpoints.
    """
    
    def has_object_permission(self, request, view, obj):
        """Check if user owns the property."""
        # obj should have an 'owner' field
        return obj.owner == request.user or request.user.is_staff


class IsBookingOwner(IsAuthenticated):
    """
    Permission: User is the one who made the booking.
    
    Used for booking detail/update/cancel endpoints.
    """
    
    def has_object_permission(self, request, view, obj):
        """Check if user made the booking."""
        return obj.user == request.user or request.user.is_staff


class IsAdmin(IsAuthenticated):
    """
    Permission: User is admin or superuser.
    
    Used for admin-only endpoints.
    """
    
    def has_permission(self, request, view):
        """Check if user is admin."""
        return (
            super().has_permission(request, view)
            and (request.user.is_staff or request.user.is_superuser or getattr(request.user, 'role', None) == UserRole.ADMIN)
        )


class IsRole(IsAuthenticated):
    """Base class to check for a specific user role with admin override."""

    required_role = None

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser or request.user.is_staff:
            return True
        return getattr(request.user, 'role', None) == self.required_role


class IsCustomer(IsRole):
    required_role = UserRole.CUSTOMER


class IsHost(IsRole):
    required_role = UserRole.HOST


class IsCarOwner(IsRole):
    required_role = UserRole.CAR_OWNER


class IsPlatformAdmin(IsRole):
    required_role = UserRole.ADMIN


class IsSuperUser(IsAuthenticated):
    """
    Permission: User is superuser.
    
    Used for critical operations.
    """
    
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_superuser


class IsTermsAccepted(IsAuthenticated):
    """
    Permission: User has accepted terms and conditions.
    
    Added business requirement.
    """
    
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view) and 
            getattr(request.user, 'terms_accepted', False)
        )


class IsBusinessAccount(IsAuthenticated):
    """
    Permission: User has a business account.
    
    For B2B features.
    """
    
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view) and 
            request.user.is_business_account
        )


class HasBookingPermission(IsAuthenticated):
    """
    Complex permission for booking operations.
    
    - GET: Can view own bookings + property owners can view bookings for their properties + admins
    - POST: Must be authenticated
    - PUT/DELETE: Must be booking owner or admin
    """
    
    def has_permission(self, request, view):
        """Check basic permission to access endpoint."""
        return super().has_permission(request, view)
    
    def has_object_permission(self, request, view, obj):
        """Check permission for specific booking."""
        if request.user.is_staff:
            return True  # Admins can do anything
        
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            # Can view own bookings or bookings for own property
            return (
                obj.user == request.user or
                (hasattr(obj.property, 'owner') and obj.property.owner == request.user)
            )
        
        # For modifications, must be booking owner
        return obj.user == request.user


class HasSearchPermission(IsAuthenticated):
    """
    Permission for search endpoints.
    
    - Guests can view public searches
    - Authenticated users can save searches
    - Rate limited by tier
    """
    
    def has_permission(self, request, view):
        """Check search access."""
        # GET (search): allowed for all
        if request.method == 'GET':
            return True
        
        # POST (save search): only authenticated
        return super().has_permission(request, view)


class IsEmailVerified(IsAuthenticated):
    """
    Permission: User has verified email address.
    
    Required for booking operations.
    """
    
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view) and 
            request.user.is_email_verified
        )


class HasPermissionOrReadOnly(IsAuthenticated):
    """
    Permission: Read public data or write own data.
    
    - Anyone: GET
    - Authenticated: POST to create own resources
    - Owner/Admin: PUT/DELETE
    """
    
    def has_permission(self, request, view):
        """Allow GET for everyone, POST/etc for authenticated."""
        return (
            request.method == 'GET' or 
            super().has_permission(request, view)
        )
    
    def has_object_permission(self, request, view, obj):
        """For modifications, must be creator/admin."""
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        if request.user.is_staff:
            return True
        
        # Check if user created this object
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


# Shorthand combinations

read_only_permission = (
    lambda: [IsAuthenticated]
)

admin_only_permission = (
    lambda: [IsAdmin]
)

property_management_permission = (
    lambda: [IsAuthenticated, IsPropertyOwner]
)

booking_permission = (
    lambda: [IsAuthenticated, IsEmailVerified, HasBookingPermission]
)
