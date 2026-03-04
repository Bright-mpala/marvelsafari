from __future__ import annotations

import uuid
import json
import logging
from django.conf import settings
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('django')


class StrictHttpVersionMiddleware:
    """Return a branded 505 page whenever the client uses an unsupported HTTP version."""

    def __init__(self, get_response):
        self.get_response = get_response
        allowed = getattr(settings, 'SUPPORTED_HTTP_PROTOCOLS', None)
        if not allowed:
            allowed = {'HTTP/1.1'}
        self.allowed_protocols = {protocol.upper() for protocol in allowed}
        self.enforce_validation = getattr(settings, 'STRICT_HTTP_VERSION_ENABLED', True)

    def __call__(self, request):
        if self.enforce_validation:
            protocol = request.META.get('SERVER_PROTOCOL', 'HTTP/1.1').upper()
            if protocol and protocol not in self.allowed_protocols:
                # Surface the dedicated 505 template instead of failing silently.
                return render(request, '505.html', status=505)
        return self.get_response(request)


class RequestTrackingMiddleware(MiddlewareMixin):
    """
    Add unique request ID and track request metadata for distributed tracing.
    """

    def process_request(self, request):
        """Add request ID and tracking info."""
        # Generate unique request ID
        request.id = request.META.get('HTTP_X_REQUEST_ID', str(uuid.uuid4()))
        request.META['HTTP_X_REQUEST_ID'] = request.id
        
        # Store start time for duration calculation
        import time
        request._start_time = time.time()
        
        return None

    def process_response(self, request, response):
        """Add tracking info to response headers."""
        if hasattr(request, 'id'):
            response['X-Request-ID'] = request.id
        
        # Add duration header if start time was recorded
        if hasattr(request, '_start_time'):
            import time
            duration = time.time() - request._start_time
            response['X-Response-Time'] = f"{duration:.3f}s"
        
        return response


class HealthCheckMiddleware(MiddlewareMixin):
    """
    Fast-track health check endpoints to avoid full request processing.
    """

    def process_request(self, request):
        """Fast-track health check requests."""
        if request.path.startswith('/health/'):
            # Import here to avoid circular imports
            from core.views import health_check
            return health_check(request)
        
        return None

