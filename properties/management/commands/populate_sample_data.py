from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from properties.models import Property, PropertyType, Amenity, AmenityCategory
from bookings.models import Booking
from accounts.models import UserProfile
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate database with sample data'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample data...')

        # Create property types
        hotel_type, _ = PropertyType.objects.get_or_create(
            name='Hotel',
            defaults={'slug': 'hotel', 'description': 'Full-service hotels'}
        )
        lodge_type, _ = PropertyType.objects.get_or_create(
            name='Safari Lodge',
            defaults={'slug': 'safari-lodge', 'description': 'Safari lodges and resorts'}
        )

        # Create amenity categories
        general_cat, _ = AmenityCategory.objects.get_or_create(
            name='General',
            defaults={'slug': 'general'}
        )
        room_cat, _ = AmenityCategory.objects.get_or_create(
            name='Room Amenities',
            defaults={'slug': 'room-amenities'}
        )

        # Create amenities
        amenities_data = [
            ('Wi-Fi', 'wifi', general_cat),
            ('Swimming Pool', 'swimming-pool', general_cat),
            ('Restaurant', 'restaurant', general_cat),
            ('Bar', 'bar', general_cat),
            ('Spa', 'spa', general_cat),
            ('Fitness Center', 'fitness-center', general_cat),
            ('Air Conditioning', 'air-conditioning', room_cat),
            ('Mini Bar', 'mini-bar', room_cat),
            ('Room Service', 'room-service', room_cat),
            ('Safe', 'safe', room_cat),
        ]

        amenities = []
        for name, slug, category in amenities_data:
            amenity, _ = Amenity.objects.get_or_create(
                name=name,
                defaults={'slug': slug, 'category': category}
            )
            amenities.append(amenity)

        # Create sample users
        users_data = [
            ('john@example.com', 'John', 'Doe'),
            ('jane@example.com', 'Jane', 'Smith'),
            ('mike@example.com', 'Mike', 'Johnson'),
            ('sarah@example.com', 'Sarah', 'Williams'),
        ]

        users = []
        for email, first_name, last_name in users_data:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_active': True
                }
            )
            if created:
                user.set_password('password123')
                user.save()
                # Create user profile
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'travel_style': random.choice(['budget', 'luxury', 'adventure']),
                        'preferred_language': 'en',
                        'preferred_currency': 'USD',
                    }
                )
            users.append(user)

        # Create sample properties
        properties_data = [
            {
                'name': 'Safari View Lodge',
                'city': 'Maasai Mara',
                'country_code': 'KE',
                'price': 250,
                'description': 'Experience the ultimate safari adventure at our luxury lodge overlooking the Maasai Mara.',
                'property_type': lodge_type,
            },
            {
                'name': 'Cape Town Harbour Hotel',
                'city': 'Cape Town',
                'country_code': 'ZA',
                'price': 180,
                'description': 'Modern hotel with stunning views of Table Mountain and the Atlantic Ocean.',
                'property_type': hotel_type,
            },
            {
                'name': 'Zanzibar Beach Resort',
                'city': 'Zanzibar',
                'country_code': 'TZ',
                'price': 220,
                'description': 'Paradise resort on the pristine beaches of Zanzibar with world-class amenities.',
                'property_type': hotel_type,
            },
            {
                'name': 'Victoria Falls Safari Lodge',
                'city': 'Victoria Falls',
                'country_code': 'ZW',
                'price': 300,
                'description': 'Luxury safari lodge just steps from the mighty Victoria Falls.',
                'property_type': lodge_type,
            },
            {
                'name': 'Serengeti Plains Hotel',
                'city': 'Serengeti',
                'country_code': 'TZ',
                'price': 275,
                'description': 'Experience the great migration from our comfortable hotel in the heart of the Serengeti.',
                'property_type': hotel_type,
            },
            {
                'name': 'Amboseli Luxury Camp',
                'city': 'Amboseli',
                'country_code': 'KE',
                'price': 350,
                'description': 'Exclusive luxury camp with unparalleled views of Mount Kilimanjaro.',
                'property_type': lodge_type,
            },
        ]

        properties = []
        for prop_data in properties_data:
            property_obj, created = Property.objects.get_or_create(
                name=prop_data['name'],
                defaults={
                    'slug': prop_data['name'].lower().replace(' ', '-'),
                    'description': prop_data['description'],
                    'property_type': prop_data['property_type'],
                    'city': prop_data['city'],
                    'country': prop_data['country_code'],
                    'address': f'123 Main Street, {prop_data["city"]}',
                    'price_per_night': prop_data['price'],
                    'star_rating': random.randint(3, 5),
                    'status': 'active',
                    'is_verified': True,
                    'host': random.choice(users),
                    'average_rating': round(random.uniform(4.0, 5.0), 1),
                    'review_count': random.randint(10, 100),
                }
            )
            if created:
                # Add random amenities
                selected_amenities = random.sample(amenities, random.randint(3, 6))
                property_obj.amenities.set(selected_amenities)
                property_obj.save()
            properties.append(property_obj)

        # Create sample bookings
        import datetime
        for _ in range(20):
            user = random.choice(users)
            property_obj = random.choice(properties)

            # Create booking for future dates
            check_in = timezone.now().date() + datetime.timedelta(days=random.randint(1, 60))
            check_out = check_in + datetime.timedelta(days=random.randint(2, 7))

            Booking.objects.get_or_create(
                user=user,
                property=property_obj,
                check_in_date=check_in,
                check_out_date=check_out,
                defaults={
                    'guests': random.randint(1, 4),
                    'total_amount': Decimal(str(property_obj.price_per_night)) * Decimal(str((check_out - check_in).days)),
                    'status': random.choice(['confirmed', 'pending', 'completed']),
                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created sample data:\n'
                f'- {Property.objects.count()} properties\n'
                f'- {User.objects.count()} users\n'
                f'- {Booking.objects.count()} bookings\n'
                f'- {Amenity.objects.count()} amenities'
            )
        )