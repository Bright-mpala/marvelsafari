from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserRole
from properties.models import Property, PropertyType, PropertyStatus
from bookings.models import Booking


class BookingRBACTests(APITestCase):
	"""Regression tests for booking RBAC and scoping."""

	def setUp(self):
		self.User = get_user_model()

		# Users
		self.customer = self.User.objects.create_user(
			email='customer@example.com', password='pass', role=UserRole.CUSTOMER, is_email_verified=True
		)
		self.other_customer = self.User.objects.create_user(
			email='other@example.com', password='pass', role=UserRole.CUSTOMER, is_email_verified=True
		)
		self.host = self.User.objects.create_user(
			email='host@example.com', password='pass', role=UserRole.HOST, is_email_verified=True
		)
		self.admin = self.User.objects.create_user(
			email='admin@example.com', password='pass', role=UserRole.ADMIN, is_staff=True, is_superuser=True, is_email_verified=True
		)

		# Listing prerequisites
		self.property_type = PropertyType.objects.create(name='Hotel', slug='hotel')

		self.property_one = Property.objects.create(
			name='Safari Lodge',
			slug='safari-lodge',
			description='Nice place',
			property_type=self.property_type,
			address='123 Street',
			city='Nairobi',
			postal_code='00100',
			country='KE',
			owner=self.host,
			status=PropertyStatus.APPROVED,
			is_verified=True,
			minimum_price=Decimal('100.00'),
		)

		self.property_two = Property.objects.create(
			name='Beach Resort',
			slug='beach-resort',
			description='Sea views',
			property_type=self.property_type,
			address='456 Beach',
			city='Mombasa',
			postal_code='80100',
			country='KE',
			owner=self.host,
			status=PropertyStatus.APPROVED,
			is_verified=True,
			minimum_price=Decimal('150.00'),
		)

		self.check_in = date.today() + timedelta(days=7)
		self.check_out = self.check_in + timedelta(days=2)

		# Seed bookings
		self.booking_customer = Booking.objects.create(
			user=self.customer,
			property=self.property_one,
			check_in_date=self.check_in,
			check_out_date=self.check_out,
			price_per_night=Decimal('100.00'),
			total_amount=Decimal('200.00'),
			status=Booking.BookingStatus.PENDING,
		)

		self.booking_other = Booking.objects.create(
			user=self.other_customer,
			property=self.property_two,
			check_in_date=self.check_in,
			check_out_date=self.check_out,
			price_per_night=Decimal('150.00'),
			total_amount=Decimal('300.00'),
			status=Booking.BookingStatus.PENDING,
		)

		self.list_url = reverse('api_v1:booking-list')

	def _extract_results(self, response_json):
		"""Normalize paginated/flat responses and validate shape."""
		data = response_json
		if isinstance(data, dict):
			data = data.get('results') or data.get('data') or data
		if isinstance(data, dict):
			data = [data]
		if not isinstance(data, list):
			self.fail(f"Unexpected payload shape: {response_json}")
		for item in data:
			if not isinstance(item, dict) or 'id' not in item:
				self.fail(f"Missing id in payload item: {response_json}")
		return data

	def test_customer_sees_only_their_bookings(self):
		"""Regular users should only see their own bookings in the API."""
		self.client.force_authenticate(self.customer)
		resp = self.client.get(self.list_url)
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		results = self._extract_results(resp.json())
		ids = {str(b['id']) for b in results}
		self.assertIn(str(self.booking_customer.id), ids)
		self.assertNotIn(str(self.booking_other.id), ids)

	def test_admin_sees_all_bookings(self):
		"""Admins can list all bookings."""
		self.client.force_authenticate(self.admin)
		resp = self.client.get(self.list_url)
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		results = self._extract_results(resp.json())
		ids = {str(b['id']) for b in results}
		self.assertIn(str(self.booking_customer.id), ids)
		self.assertIn(str(self.booking_other.id), ids)

	def test_create_booking_forces_authenticated_user(self):
		"""Booking creation should ignore payload user and assign the requester."""
		self.client.force_authenticate(self.customer)
		payload = {
			'user': str(self.other_customer.id),  # should be ignored by perform_create
			'property': str(self.property_two.id),
			'check_in_date': (self.check_in + timedelta(days=5)).isoformat(),
			'check_out_date': (self.check_in + timedelta(days=7)).isoformat(),
			'price_per_night': '150.00',
			'total_amount': '300.00',
			'status': Booking.BookingStatus.PENDING,
		}

		resp = self.client.post(self.list_url, payload, format='json')
		self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
		booking_id = resp.json()['id']
		created = Booking.objects.get(id=booking_id)
		self.assertEqual(created.user, self.customer)
		self.assertEqual(created.property, self.property_two)
