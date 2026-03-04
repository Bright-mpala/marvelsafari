"""Enterprise exception handling and error responses"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging
import uuid

logger = logging.getLogger(__name__)


class EnterpriseAPIException(Exception):
    """Base exception for enterprise API errors"""
    
    default_code = 'error'
    default_message = 'An error occurred'
    default_status_code = status.HTTP_400_BAD_REQUEST
    
    def __init__(self, message=None, code=None, status_code=None, details=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.status_code = status_code or self.default_status_code
        self.details = details or {}
        self.error_id = str(uuid.uuid4())
        super().__init__(self.message)


class NonRecoverableBookingError(EnterpriseAPIException):
    """Error that cannot be recovered (e.g., double booking, expired booking)"""
    default_code = 'booking_error'
    default_message = 'Booking operation failed and cannot be retried'
    default_status_code = status.HTTP_409_CONFLICT


class ConcurrencyError(EnterpriseAPIException):
    """Concurrency/race condition error"""
    default_code = 'concurrency_error'
    default_message = 'Resource was modified by another request'
    default_status_code = status.HTTP_409_CONFLICT


class ServiceUnavailableError(EnterpriseAPIException):
    """Service temporarily unavailable"""
    default_code = 'service_unavailable'
    default_message = 'Service temporarily unavailable'
    default_status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class InvalidDataError(EnterpriseAPIException):
    """Invalid or malformed data"""
    default_code = 'invalid_data'
    default_message = 'Invalid data provided'
    default_status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class PermissionError(EnterpriseAPIException):
    """Permission denied"""
    default_code = 'permission_denied'
    default_message = 'Permission denied'
    default_status_code = status.HTTP_403_FORBIDDEN


def enterprise_exception_handler(exc, context):
    """
    Custom exception handler with enterprise features:
    - Error tracking IDs
    - Structured error responses
    - Request tracing
    - Proper HTTP status codes
    """
    
    # Generate unique error ID for tracking
    error_id = str(uuid.uuid4())
    request = context.get('request')
    request_id = getattr(request, 'id', 'unknown') if request else 'unknown'
    
    # Handle rest_framework exceptions
    response = exception_handler(exc, context)
    
    if response is not None:
        # REST framework exception already handled
        error_detail = response.data
        
        # Ensure proper structure
        structured_response = {
            'success': False,
            'error': {
                'error_id': error_id,
                'request_id': request_id,
                'message': str(error_detail.get('detail', 'An error occurred')),
            },
            'data': None,
            'timestamp': __import__('django.utils.timezone', fromlist=['now']).now().isoformat(),
        }
        
        # Add validation errors if present
        if isinstance(error_detail, dict) and 'detail' not in error_detail:
            structured_response['errors'] = error_detail
        
        response.data = structured_response
        
        # Log the error
        log_level = 'warning' if 400 <= response.status_code < 500 else 'error'
        getattr(logger, log_level)(
            f"API error: {error_id}",
            extra={
                'error_id': error_id,
                'request_id': request_id,
                'status_code': response.status_code,
                'error': str(exc),
            }
        )
    
    elif isinstance(exc, EnterpriseAPIException):
        # Handle custom enterprise exceptions
        response_data = {
            'success': False,
            'error': {
                'error_id': exc.error_id,
                'request_id': request_id,
                'code': exc.code,
                'message': exc.message,
            },
            'data': None,
            'timestamp': __import__('django.utils.timezone', fromlist=['now']).now().isoformat(),
        }
        
        if exc.details:
            response_data['details'] = exc.details
        
        response = Response(response_data, status=exc.status_code)
        
        # Log the error
        logger.warning(
            f"Enterprise API error: {exc.error_id}",
            extra={
                'error_id': exc.error_id,
                'request_id': request_id,
                'code': exc.code,
                'message': exc.message,
            }
        )
    
    else:
        # Unhandled exception
        logger.error(
            f"Unhandled exception: {error_id}",
            exc_info=True,
            extra={
                'error_id': error_id,
                'request_id': request_id,
            }
        )
        
        response_data = {
            'success': False,
            'error': {
                'error_id': error_id,
                'request_id': request_id,
                'message': 'An unexpected error occurred',
            },
            'data': None,
            'timestamp': __import__('django.utils.timezone', fromlist=['now']).now().isoformat(),
        }
        
        response = Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response
