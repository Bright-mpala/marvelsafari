from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.authentication import CustomTokenObtainPairSerializer
from accounts.models import UserRole


class TokenSerializerTests(TestCase):
	"""Ensure JWT serializers emit role information."""

	def setUp(self):
		self.User = get_user_model()
		self.user = self.User.objects.create_user(
			email='host@example.com', password='pass1234', role=UserRole.HOST, is_email_verified=True
		)

	def test_token_obtain_includes_role_and_user(self):
		serializer = CustomTokenObtainPairSerializer(data={'email': self.user.email, 'password': 'pass1234'})
		self.assertTrue(serializer.is_valid(), serializer.errors)

		data = serializer.validated_data
		self.assertIn('access', data)
		self.assertIn('refresh', data)
		self.assertEqual(data.get('role'), UserRole.HOST)

		user_payload = data.get('user', {})
		self.assertEqual(user_payload.get('id'), str(self.user.id))
		self.assertEqual(user_payload.get('role'), UserRole.HOST)
