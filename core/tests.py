"""Tests for core app"""

from django.test import TestCase,RequestFactory
from rest_framework.test import APITestCase
from rest_framework import status
from core.views import health_check_live, health_check_ready


class HealthCheckTests(APITestCase):
    """Test health check endpoints"""
    
    def setUp(self):
        self.factory = RequestFactory()
    
    def test_liveness_probe(self):
        """Test /health/live endpoint"""
        request = self.factory.get('/health/live')
        response = health_check_live(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'alive')
    
    def test_readiness_probe(self):
        """Test /health/ready endpoint"""
        request = self.factory.get('/health/ready')
        response = health_check_ready(request)
        # Should be 200 if all checks pass
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])
        self.assertIn(response.data['status'], ['ready', 'not_ready'])
