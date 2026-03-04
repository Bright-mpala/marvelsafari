"""
properties/permissions.py - DRF Permission Classes for Properties

Production-ready permissions for API endpoints:
- IsPropertyOwnerOrAdmin: Property owner or admin access
- CanCreateProperty: HOST role required
- CanApproveProperty: Admin only
- IsPublicProperty: Read access to published properties
"""

from rest_framework.permissions import BasePermission, IsAuthenticated
from accounts.models import UserRole


class IsPropertyOwner(IsAuthenticated):
    """
    Permission: User owns the property.
    
    Checks:
    - User is authenticated
    - User is the property owner OR is admin
    
    Usage:
        permission_classes = [IsPropertyOwner]
    """
    
    message = 'You do not have permission to access this property.'
    
    def has_object_permission(self, request, view, obj):
        """Check if user owns the property or is admin."""
        user = request.user
        
        # Admins have full access
        if user.is_staff or user.is_superuser or user.role == UserRole.ADMIN:
            return True
        
        # Check ownership
        return obj.owner_id == user.id


class CanCreateProperty(IsAuthenticated):
    """
    Permission: User can create properties (requires HOST role).
    
    Checks:
    - User is authenticated
    - User has HOST or ADMIN role, OR is staff/superuser
    
    Usage:
        permission_classes = [CanCreateProperty]
    """
    
    message = 'Only hosts can create property listings. Please upgrade your account.'
    
    def has_permission(self, request, view):
        """Check if user can create properties."""
        if not super().has_permission(request, view):
            return False
        
        user = request.user
        
        # Allow admins and superusers
        if user.is_staff or user.is_superuser:
            return True
        
        # Require HOST or ADMIN role
        return user.role in {UserRole.HOST, UserRole.ADMIN}


class CanEditProperty(IsAuthenticated):
    """
    Permission: User can edit the property.
    
    Checks:
    - User owns the property OR is admin
    - Property is in an editable status (for non-admins)
    
    Usage:
        permission_classes = [CanEditProperty]
    """
    
    message = 'You cannot edit this property.'
    
    def has_object_permission(self, request, view, obj):
        """Check if user can edit property."""
        user = request.user
        
        # Admins have full access
        if user.is_staff or user.is_superuser or user.role == UserRole.ADMIN:
            return True
        
        # Must own the property
        if obj.owner_id != user.id:
            return False
        
        # Check if property can be edited
        return obj.can_be_edited_by(user)


class CanApproveProperty(IsAuthenticated):
    """
    Permission: User can approve/reject properties (admin only).
    
    Checks:
    - User is staff, superuser, or ADMIN role
    
    Usage:
        permission_classes = [CanApproveProperty]
    """
    
    message = 'Only administrators can approve or reject properties.'
    
    def has_permission(self, request, view):
        """Check if user can approve properties."""
        if not super().has_permission(request, view):
            return False
        
        user = request.user
        return user.is_staff or user.is_superuser or user.role == UserRole.ADMIN


class IsPublicProperty(BasePermission):
    """
    Permission: Property is publicly viewable.
    
    For read operations, checks that property is:
    - Status is APPROVED or ACTIVE
    - is_active is True
    - is_deleted is False
    
    For authenticated users who own the property,
    access is always granted.
    
    Usage:
        permission_classes = [IsPublicProperty]
    """
    
    message = 'This property is not available for viewing.'
    
    def has_object_permission(self, request, view, obj):
        """Check if property is publicly viewable."""
        # Allow if property is public
        if obj.is_publicly_visible():
            return True
        
        # Allow if user is the owner
        if request.user.is_authenticated:
            if obj.owner_id == request.user.id:
                return True
            
            # Allow admins
            if request.user.is_staff or request.user.is_superuser:
                return True
            if request.user.role == UserRole.ADMIN:
                return True
        
        return False


class CanDeleteProperty(IsAuthenticated):
    """
    Permission: User can delete (soft-delete) property.
    
    Checks:
    - User owns the property OR is admin
    - Property is not already deleted
    
    Usage:
        permission_classes = [CanDeleteProperty]
    """
    
    message = 'You cannot delete this property.'
    
    def has_object_permission(self, request, view, obj):
        """Check if user can delete property."""
        user = request.user
        
        # Can't delete already deleted
        if obj.is_deleted:
            return False
        
        # Admins can delete any
        if user.is_staff or user.is_superuser or user.role == UserRole.ADMIN:
            return True
        
        # Must own the property
        return obj.owner_id == user.id


class CanManagePropertyImages(IsAuthenticated):
    """
    Permission: User can manage property images.
    
    Checks:
    - User owns the property OR is admin
    
    Usage:
        permission_classes = [CanManagePropertyImages]
    """
    
    message = 'You cannot manage images for this property.'
    
    def has_object_permission(self, request, view, obj):
        """Check if user can manage property images."""
        user = request.user
        
        # Admins have full access
        if user.is_staff or user.is_superuser or user.role == UserRole.ADMIN:
            return True
        
        # For PropertyImage objects, check the parent property
        property_obj = getattr(obj, 'property', obj)
        
        return property_obj.owner_id == user.id
