"""Enterprise-grade pagination for APIs"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from collections import OrderedDict
from django.utils import timezone


class EnterprisePageNumberPagination(PageNumberPagination):
    """Standard page number pagination with enterprise features."""
    
    page_size = 25
    page_size_query_param = 'page_size'
    page_size_query_description = 'Number of results per page'
    max_page_size = 100
    page_query_description = 'Page number'
    
    def get_paginated_response(self, data):
        """Return paginated response with metadata."""
        return Response(OrderedDict([
            ('success', True),
            ('data', data),
            ('pagination', OrderedDict([
                ('count', self.page.paginator.count),
                ('next', self.get_next_link()),
                ('previous', self.get_previous_link()),
                ('page_size', self.get_page_size(self.request)),
                ('page', self.request.query_params.get(self.page_query_param, 1)),
                ('total_pages', self.page.paginator.num_pages),
            ])),
            ('timestamp', timezone.now().isoformat()),
        ]))


class BookingSafePageNumberPagination(EnterprisePageNumberPagination):
    """Booking-specific pagination with strict limits."""
    page_size = 20
    max_page_size = 50


class PropertySearchPagination(EnterprisePageNumberPagination):
    """Search result pagination optimized for property listings."""
    page_size = 30
    max_page_size = 100
