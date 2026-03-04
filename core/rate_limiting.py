"""
core/rate_limiting.py - Enterprise rate limiting

Protect API with:
- Per-user rate limits
- Per-IP rate limits  
- Tiered rate limits (free/premium/admin)
- Sliding window algorithm
"""

from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle
from rest_framework.exceptions import Throttled
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class UserBasedThrottle(UserRateThrottle):
    """
    Rate limit per authenticated user.
    
    Different limits by user tier.
    """
    
    def get_rate(self):
        """Determine rate limit based on user type."""
        if not self.request.user or not self.request.user.is_authenticated:
            return None  # Allow unlimited for unauthenticated (other throttles apply)
        
        # Admin: no limit
        if self.request.user.is_staff or self.request.user.is_superuser:
            return '10000/hour'
        
        # Business account: premium tier
        if getattr(self.request.user, 'is_business_account', False):
            return '5000/hour'
        
        # Regular user: standard tier
        return '1000/hour'


class IPBasedThrottle(SimpleRateThrottle):
    """
    Rate limit per IP address.
    
    Global limit to prevent abuse from single IP.
    """
    
    scope = 'ip_based'
    
    def get_client_ip(self, request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_ident(self, request):
        """Use IP as identifier."""
        return self.get_client_ip(request)
    
    def get_rate(self):
        """Get rate for IP-based throttling."""
        return '10000/hour'  # High limit, mainly for DoS


class AnonymousUserThrottle(SimpleRateThrottle):
    """
    Rate limit for unauthenticated users.
    
    Prevents API abuse without account.
    """
    
    scope = 'anonymous'
    
    def get_ident(self, request):
        """Get client identifier."""
        return request.META.get('REMOTE_ADDR', '')
    
    def get_rate(self):
        """Lower limit for unauthenticated."""
        return '100/hour'
    
    def throttle_success(self):
        """Override to apply rate limit only to non-GET requests."""
        if self.request.method == 'GET':
            return True  # Don't limit GET for unauthenticated
        return super().throttle_success()


class SearchThrottle(UserRateThrottle):
    """
    Special throttle for search endpoints.
    
    Allow more generous search limits.
    """
    
    scope = 'search'
    
    def get_rate(self):
        """Get rate for search operations."""
        if not self.request.user or not self.request.user.is_authenticated:
            return '1000/hour'
        
        if self.request.user.is_staff:
            return '50000/hour'
        
        if getattr(self.request.user, 'is_business_account', False):
            return '10000/hour'
        
        return '2000/hour'


class BookingThrottle(UserRateThrottle):
    """
    Special throttle for booking operations.
    
    Prevent rapid-fire booking attempts (double-booking attempts, bot attacks).
    """
    
    scope = 'booking'
    history_key_func = 'user_bookings'
    
    def get_rate(self):
        """Get rate for booking operations."""
        if not self.request.user or not self.request.user.is_authenticated:
            return '5/hour'
        
        if self.request.user.is_staff:
            return '1000/hour'
        
        # Limited to prevent abuse
        return '50/hour'
    
    def allow_request(self, request):
        """
        Custom logic: warn if user creates too many bookings too fast.
        """
        if request.method != 'POST':
            return True
        
        allowed = super().allow_request(request)
        
        if not allowed:
            logger.warning(
                f"Booking throttle exceeded for user {request.user.email}",
                extra={'user_id': str(request.user.id)}
            )
        
        return allowed


class SMSThrottle(UserRateThrottle):
    """
    Throttle for SMS/phone verification.
    
    Prevent abuse of SMS sending.
    """
    
    scope = 'sms'
    
    def get_rate(self):
        """Very strict limit for SMS."""
        if not self.request.user or not self.request.user.is_authenticated:
            return '3/hour'
        
        if self.request.user.is_staff:
            return '100/hour'
        
        return '10/hour'


class EmailThrottle(UserRateThrottle):
    """
    Throttle for email operations.
    
    Prevent email spam.
    """
    
    scope = 'email'
    
    def get_rate(self):
        """Limit email operations."""
        if not self.request.user or not self.request.user.is_authenticated:
            return '5/hour'
        
        if self.request.user.is_staff:
            return '500/hour'
        
        return '50/hour'


class SlidingWindowRateLimiter:
    """
    Sliding window algorithm for more accurate rate limiting.
    
    Better than fixed windows for high-traffic scenarios.
    """
    
    def __init__(self, key, limit, window_seconds=3600):
        """
        Initialize rate limiter.
        
        Args:
            key: Unique identifier (e.g., user_id, IP)
            limit: Max requests in window
            window_seconds: Time window (default 1 hour)
        """
        self.key = key
        self.limit = limit
        self.window = window_seconds
    
    def is_allowed(self):
        """
        Check if request is allowed.
        
        Returns:
            (allowed, remaining_requests)
        """
        import time
        
        cache_key = f'ratelimit:{self.key}'
        current_time = time.time()
        
        # Get existing requests
        requests = cache.get(cache_key, [])
        
        # Remove old requests outside window
        requests = [
            req_time for req_time in requests
            if current_time - req_time < self.window
        ]
        
        # Check limit
        if len(requests) >= self.limit:
            cache.set(cache_key, requests, self.window)
            remaining = 0
            return False, remaining
        
        # Add new request
        requests.append(current_time)
        cache.set(cache_key, requests, self.window)
        
        remaining = self.limit - len(requests)
        return True, remaining


# Shorthand throttle classes for common endpoints

class DefaultThrottles:
    """Default throttle for most endpoints."""
    user = UserBasedThrottle
    ip = IPBasedThrottle


class SearchThrottles:
    """Throttles for search endpoints."""
    user = SearchThrottle
    ip = IPBasedThrottle


class BookingThrottles:
    """Throttles for booking endpoints."""
    user = BookingThrottle
    ip = IPBasedThrottle


class PublicThrottles:
    """Throttles for public endpoints."""
    anonymous = AnonymousUserThrottle
    ip = IPBasedThrottle
