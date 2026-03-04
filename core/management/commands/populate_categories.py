"""
Management command to populate car categories and property amenity categories.
Run with: python manage.py populate_categories
"""

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from car_rentals.models import CarCategory
from properties.models import AmenityCategory, Amenity, PropertyType


class Command(BaseCommand):
    help = "Populate car categories and property amenity categories with real data"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting to populate categories..."))
        
        self._create_property_types()
        self._create_car_categories()
        self._create_amenity_categories()
        self._create_amenities()
        
        self.stdout.write(self.style.SUCCESS("Successfully populated all categories!"))

    def _create_property_types(self):
        """Create property types."""
        
        property_types = [
            {'name': 'Lodge', 'slug': 'lodge', 'icon': 'fa-campground', 'description': 'Safari lodges and wilderness camps'},
            {'name': 'Hotel', 'slug': 'hotel', 'icon': 'fa-hotel', 'description': 'Traditional hotels and city accommodations'},
            {'name': 'Resort', 'slug': 'resort', 'icon': 'fa-umbrella-beach', 'description': 'Beach resorts and spa retreats'},
            {'name': 'Homestay', 'slug': 'homestay', 'icon': 'fa-home', 'description': 'Local homes and guesthouses'},
            {'name': 'Apartment', 'slug': 'apartment', 'icon': 'fa-building', 'description': 'Serviced apartments and self-catering units'},
            {'name': 'Villa', 'slug': 'villa', 'icon': 'fa-home-lg', 'description': 'Private villas and vacation homes'},
            {'name': 'Camp', 'slug': 'camp', 'icon': 'fa-tent', 'description': 'Tented camps and glamping sites'},
            {'name': 'Boutique Hotel', 'slug': 'boutique-hotel', 'icon': 'fa-gem', 'description': 'Unique boutique hotels with character'},
            {'name': 'Guesthouse', 'slug': 'guesthouse', 'icon': 'fa-door-open', 'description': 'Cozy guesthouses and B&Bs'},
            {'name': 'Treehouse', 'slug': 'treehouse', 'icon': 'fa-tree', 'description': 'Unique treehouse accommodations'},
            {'name': 'Houseboat', 'slug': 'houseboat', 'icon': 'fa-ship', 'description': 'Floating accommodations and houseboats'},
            {'name': 'Eco-Lodge', 'slug': 'eco-lodge', 'icon': 'fa-leaf', 'description': 'Environmentally sustainable lodges'},
        ]
        
        created_count = 0
        updated_count = 0
        
        for pt_data in property_types:
            pt, created = PropertyType.objects.update_or_create(
                slug=pt_data['slug'],
                defaults=pt_data
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f"Property Types: {created_count} created, {updated_count} updated")
        )

    def _create_car_categories(self):
        """Create realistic car rental categories."""
        
        car_categories = [
            {
                'name': 'Economy',
                'code': 'ECON',
                'description': 'Perfect for budget-conscious travelers. Compact, fuel-efficient vehicles ideal for city driving and short trips.',
                'icon': 'fa-car-side',
                'typical_cars': 'Toyota Yaris, Suzuki Swift, Hyundai i10, Kia Picanto, Nissan March',
                'passenger_capacity': 4,
                'luggage_capacity': 2,
                'fuel_type': 'petrol',
                'transmission': 'manual',
                'display_order': 1,
            },
            {
                'name': 'Compact',
                'code': 'COMP',
                'description': 'Small but comfortable cars with better features than economy class. Great for couples or small families.',
                'icon': 'fa-car',
                'typical_cars': 'Toyota Corolla, Honda Fit, Mazda 3, Volkswagen Polo, Hyundai i20',
                'passenger_capacity': 5,
                'luggage_capacity': 2,
                'fuel_type': 'petrol',
                'transmission': 'automatic',
                'display_order': 2,
            },
            {
                'name': 'Midsize',
                'code': 'MIDS',
                'description': 'Comfortable sedans with ample space for passengers and luggage. Ideal for family trips and business travel.',
                'icon': 'fa-car',
                'typical_cars': 'Toyota Camry, Honda Accord, Mazda 6, Hyundai Sonata, Nissan Altima',
                'passenger_capacity': 5,
                'luggage_capacity': 3,
                'fuel_type': 'petrol',
                'transmission': 'automatic',
                'display_order': 3,
            },
            {
                'name': 'Full-size',
                'code': 'FULL',
                'description': 'Spacious sedans with premium features and extra legroom. Perfect for long road trips and executive travel.',
                'icon': 'fa-car',
                'typical_cars': 'Toyota Avalon, Chevrolet Impala, Chrysler 300, Nissan Maxima, Ford Taurus',
                'passenger_capacity': 5,
                'luggage_capacity': 4,
                'fuel_type': 'petrol',
                'transmission': 'automatic',
                'display_order': 4,
            },
            {
                'name': 'SUV Compact',
                'code': 'SUVC',
                'description': 'Small sport utility vehicles combining car-like handling with extra cargo space and higher seating.',
                'icon': 'fa-truck',
                'typical_cars': 'Toyota RAV4, Honda CR-V, Mazda CX-5, Hyundai Tucson, Nissan Rogue',
                'passenger_capacity': 5,
                'luggage_capacity': 3,
                'fuel_type': 'petrol',
                'transmission': 'automatic',
                'display_order': 5,
            },
            {
                'name': 'SUV Midsize',
                'code': 'SUVM',
                'description': 'Larger SUVs with third-row seating option. Great for families and groups needing extra space.',
                'icon': 'fa-truck',
                'typical_cars': 'Toyota Highlander, Ford Explorer, Chevrolet Traverse, Honda Pilot, Nissan Pathfinder',
                'passenger_capacity': 7,
                'luggage_capacity': 4,
                'fuel_type': 'petrol',
                'transmission': 'automatic',
                'display_order': 6,
            },
            {
                'name': 'SUV Full-size',
                'code': 'SUVF',
                'description': 'Full-size SUVs with maximum space and power. Perfect for large groups and safari adventures.',
                'icon': 'fa-truck',
                'typical_cars': 'Toyota Land Cruiser, Chevrolet Suburban, Ford Expedition, Nissan Armada, GMC Yukon',
                'passenger_capacity': 8,
                'luggage_capacity': 5,
                'fuel_type': 'diesel',
                'transmission': 'automatic',
                'display_order': 7,
            },
            {
                'name': '4x4 Off-Road',
                'code': '4WD',
                'description': 'Rugged 4-wheel drive vehicles built for off-road adventures, safari drives, and challenging terrain.',
                'icon': 'fa-mountain',
                'typical_cars': 'Toyota Land Cruiser Prado, Jeep Wrangler, Land Rover Defender, Toyota Hilux, Mitsubishi Pajero',
                'passenger_capacity': 5,
                'luggage_capacity': 4,
                'fuel_type': 'diesel',
                'transmission': 'automatic',
                'display_order': 8,
            },
            {
                'name': 'Luxury Sedan',
                'code': 'LUXS',
                'description': 'Premium luxury sedans with top-tier comfort, advanced features, and prestigious brands.',
                'icon': 'fa-star',
                'typical_cars': 'Mercedes-Benz E-Class, BMW 5 Series, Audi A6, Lexus ES, Jaguar XF',
                'passenger_capacity': 5,
                'luggage_capacity': 3,
                'fuel_type': 'petrol',
                'transmission': 'automatic',
                'display_order': 9,
            },
            {
                'name': 'Luxury SUV',
                'code': 'LUXU',
                'description': 'Premium SUVs combining luxury amenities with off-road capability. Ultimate comfort for safari tours.',
                'icon': 'fa-gem',
                'typical_cars': 'Range Rover, Mercedes-Benz GLE, BMW X5, Lexus LX, Porsche Cayenne',
                'passenger_capacity': 5,
                'luggage_capacity': 4,
                'fuel_type': 'petrol',
                'transmission': 'automatic',
                'display_order': 10,
            },
            {
                'name': 'Minivan',
                'code': 'MINV',
                'description': 'Spacious passenger vans perfect for families and groups. Easy loading and comfortable seating.',
                'icon': 'fa-shuttle-van',
                'typical_cars': 'Toyota Sienna, Honda Odyssey, Chrysler Pacifica, Kia Carnival, Hyundai Staria',
                'passenger_capacity': 7,
                'luggage_capacity': 5,
                'fuel_type': 'petrol',
                'transmission': 'automatic',
                'display_order': 11,
            },
            {
                'name': 'Passenger Van',
                'code': 'PVAN',
                'description': 'Large vans for group travel and airport transfers. Ideal for tour groups and corporate shuttles.',
                'icon': 'fa-bus',
                'typical_cars': 'Toyota HiAce, Mercedes Sprinter, Ford Transit, Nissan Urvan, Hyundai H-1',
                'passenger_capacity': 12,
                'luggage_capacity': 8,
                'fuel_type': 'diesel',
                'transmission': 'automatic',
                'display_order': 12,
            },
            {
                'name': 'Convertible',
                'code': 'CONV',
                'description': 'Open-top vehicles for scenic drives and special occasions. Feel the wind and enjoy the views.',
                'icon': 'fa-wind',
                'typical_cars': 'Ford Mustang Convertible, BMW 4 Series Convertible, Audi A3 Cabriolet, Mazda MX-5, Mercedes C-Class Cabriolet',
                'passenger_capacity': 4,
                'luggage_capacity': 1,
                'fuel_type': 'petrol',
                'transmission': 'automatic',
                'display_order': 13,
            },
            {
                'name': 'Sports Car',
                'code': 'SPRT',
                'description': 'High-performance vehicles for driving enthusiasts. Experience speed, handling, and excitement.',
                'icon': 'fa-flag-checkered',
                'typical_cars': 'Porsche 911, BMW M4, Mercedes AMG GT, Ford Mustang GT, Chevrolet Corvette',
                'passenger_capacity': 2,
                'luggage_capacity': 1,
                'fuel_type': 'petrol',
                'transmission': 'automatic',
                'display_order': 14,
            },
            {
                'name': 'Electric',
                'code': 'ELEC',
                'description': 'Zero-emission electric vehicles for eco-conscious travelers. Modern tech and quiet operation.',
                'icon': 'fa-bolt',
                'typical_cars': 'Tesla Model 3, Tesla Model Y, Nissan Leaf, Hyundai Kona Electric, BMW iX3',
                'passenger_capacity': 5,
                'luggage_capacity': 3,
                'fuel_type': 'electric',
                'transmission': 'automatic',
                'display_order': 15,
            },
            {
                'name': 'Pickup Truck',
                'code': 'PICK',
                'description': 'Versatile trucks with open cargo beds. Great for moving gear, camping trips, and rugged terrain.',
                'icon': 'fa-truck-pickup',
                'typical_cars': 'Toyota Hilux, Ford Ranger, Nissan Navara, Isuzu D-Max, Mitsubishi L200',
                'passenger_capacity': 5,
                'luggage_capacity': 2,
                'fuel_type': 'diesel',
                'transmission': 'manual',
                'display_order': 16,
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for cat_data in car_categories:
            cat, created = CarCategory.objects.update_or_create(
                code=cat_data['code'],
                defaults=cat_data
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f"Car Categories: {created_count} created, {updated_count} updated")
        )

    def _create_amenity_categories(self):
        """Create property amenity categories."""
        
        categories = [
            {'name': 'Room Essentials', 'slug': 'room-essentials', 'icon': 'fa-bed', 'description': 'Basic room features and furnishings'},
            {'name': 'Bathroom', 'slug': 'bathroom', 'icon': 'fa-bath', 'description': 'Bathroom facilities and toiletries'},
            {'name': 'Kitchen', 'slug': 'kitchen', 'icon': 'fa-utensils', 'description': 'Kitchen and dining facilities'},
            {'name': 'Entertainment', 'slug': 'entertainment', 'icon': 'fa-tv', 'description': 'TV, games, and entertainment options'},
            {'name': 'Connectivity', 'slug': 'connectivity', 'icon': 'fa-wifi', 'description': 'Internet and communication'},
            {'name': 'Climate Control', 'slug': 'climate-control', 'icon': 'fa-snowflake', 'description': 'Heating, cooling, and ventilation'},
            {'name': 'Safety & Security', 'slug': 'safety-security', 'icon': 'fa-shield-alt', 'description': 'Safety features and security'},
            {'name': 'Outdoor', 'slug': 'outdoor', 'icon': 'fa-tree', 'description': 'Outdoor spaces and views'},
            {'name': 'Wellness & Spa', 'slug': 'wellness-spa', 'icon': 'fa-spa', 'description': 'Spa, fitness, and wellness'},
            {'name': 'Pool & Beach', 'slug': 'pool-beach', 'icon': 'fa-swimming-pool', 'description': 'Swimming and beach access'},
            {'name': 'Family & Kids', 'slug': 'family-kids', 'icon': 'fa-child', 'description': 'Family-friendly amenities'},
            {'name': 'Business', 'slug': 'business', 'icon': 'fa-briefcase', 'description': 'Business and work facilities'},
            {'name': 'Parking & Transport', 'slug': 'parking-transport', 'icon': 'fa-parking', 'description': 'Parking and transportation'},
            {'name': 'Dining', 'slug': 'dining', 'icon': 'fa-concierge-bell', 'description': 'On-site dining options'},
            {'name': 'Accessibility', 'slug': 'accessibility', 'icon': 'fa-wheelchair', 'description': 'Accessibility features'},
            {'name': 'Services', 'slug': 'services', 'icon': 'fa-hands-helping', 'description': 'Guest services'},
        ]
        
        created_count = 0
        updated_count = 0
        
        for cat_data in categories:
            cat, created = AmenityCategory.objects.update_or_create(
                slug=cat_data['slug'],
                defaults=cat_data
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f"Amenity Categories: {created_count} created, {updated_count} updated")
        )

    def _create_amenities(self):
        """Create property amenities under each category."""
        
        amenities_data = {
            'room-essentials': [
                ('Air Conditioning', 'air-conditioning', 'fa-snowflake'),
                ('Heating', 'heating', 'fa-fire'),
                ('Wardrobe', 'wardrobe', 'fa-door-closed'),
                ('Desk', 'desk', 'fa-chair'),
                ('Ironing Facilities', 'ironing', 'fa-tshirt'),
                ('Sofa', 'sofa', 'fa-couch'),
                ('Blackout Curtains', 'blackout-curtains', 'fa-moon'),
                ('Soundproofing', 'soundproofing', 'fa-volume-mute'),
                ('Mosquito Net', 'mosquito-net', 'fa-bug'),
                ('Fan', 'fan', 'fa-fan'),
                ('Extra Pillows & Blankets', 'extra-bedding', 'fa-bed'),
                ('Alarm Clock', 'alarm-clock', 'fa-clock'),
            ],
            'bathroom': [
                ('Private Bathroom', 'private-bathroom', 'fa-bath'),
                ('Shower', 'shower', 'fa-shower'),
                ('Bathtub', 'bathtub', 'fa-bath'),
                ('Hairdryer', 'hairdryer', 'fa-wind'),
                ('Free Toiletries', 'toiletries', 'fa-pump-soap'),
                ('Towels', 'towels', 'fa-scroll'),
                ('Bathrobes', 'bathrobes', 'fa-tshirt'),
                ('Slippers', 'slippers', 'fa-shoe-prints'),
                ('Bidet', 'bidet', 'fa-toilet'),
                ('Hot Water', 'hot-water', 'fa-temperature-high'),
            ],
            'kitchen': [
                ('Kitchen', 'kitchen', 'fa-utensils'),
                ('Kitchenette', 'kitchenette', 'fa-utensils'),
                ('Refrigerator', 'refrigerator', 'fa-ice-cream'),
                ('Microwave', 'microwave', 'fa-microchip'),
                ('Coffee Machine', 'coffee-machine', 'fa-coffee'),
                ('Electric Kettle', 'electric-kettle', 'fa-mug-hot'),
                ('Toaster', 'toaster', 'fa-bread-slice'),
                ('Dishwasher', 'dishwasher', 'fa-sink'),
                ('Cookware', 'cookware', 'fa-utensil-spoon'),
                ('Dining Table', 'dining-table', 'fa-chair'),
                ('Minibar', 'minibar', 'fa-wine-bottle'),
            ],
            'entertainment': [
                ('Flat-screen TV', 'flat-screen-tv', 'fa-tv'),
                ('Smart TV', 'smart-tv', 'fa-tv'),
                ('Cable Channels', 'cable-channels', 'fa-satellite-dish'),
                ('Netflix', 'netflix', 'fa-play-circle'),
                ('Streaming Services', 'streaming-services', 'fa-video'),
                ('DVD Player', 'dvd-player', 'fa-compact-disc'),
                ('Sound System', 'sound-system', 'fa-volume-up'),
                ('Books & Library', 'library', 'fa-book'),
                ('Board Games', 'board-games', 'fa-chess'),
                ('Video Games', 'video-games', 'fa-gamepad'),
            ],
            'connectivity': [
                ('Free WiFi', 'free-wifi', 'fa-wifi'),
                ('High-speed Internet', 'high-speed-internet', 'fa-tachometer-alt'),
                ('Wired Internet', 'wired-internet', 'fa-ethernet'),
                ('USB Charging Ports', 'usb-ports', 'fa-plug'),
                ('International Adapter', 'adapter', 'fa-plug'),
                ('Telephone', 'telephone', 'fa-phone'),
                ('Fax', 'fax', 'fa-fax'),
            ],
            'climate-control': [
                ('Central Air Conditioning', 'central-ac', 'fa-snowflake'),
                ('Individual Climate Control', 'climate-control', 'fa-thermometer-half'),
                ('Central Heating', 'central-heating', 'fa-fire'),
                ('Fireplace', 'fireplace', 'fa-fire-alt'),
                ('Ceiling Fan', 'ceiling-fan', 'fa-fan'),
                ('Portable Fan', 'portable-fan', 'fa-fan'),
            ],
            'safety-security': [
                ('Safe Deposit Box', 'safe', 'fa-lock'),
                ('Smoke Detectors', 'smoke-detectors', 'fa-bell'),
                ('Fire Extinguisher', 'fire-extinguisher', 'fa-fire-extinguisher'),
                ('First Aid Kit', 'first-aid', 'fa-medkit'),
                ('Security Alarm', 'security-alarm', 'fa-shield-alt'),
                ('CCTV', 'cctv', 'fa-video'),
                ('24-hour Security', '24hr-security', 'fa-user-shield'),
                ('Key Card Access', 'key-card', 'fa-id-card'),
                ('Carbon Monoxide Detector', 'co-detector', 'fa-exclamation-triangle'),
            ],
            'outdoor': [
                ('Balcony', 'balcony', 'fa-door-open'),
                ('Terrace', 'terrace', 'fa-umbrella-beach'),
                ('Garden', 'garden', 'fa-seedling'),
                ('Patio', 'patio', 'fa-chair'),
                ('BBQ Facilities', 'bbq', 'fa-fire'),
                ('Outdoor Furniture', 'outdoor-furniture', 'fa-couch'),
                ('Sun Loungers', 'sun-loungers', 'fa-umbrella-beach'),
                ('Mountain View', 'mountain-view', 'fa-mountain'),
                ('Ocean View', 'ocean-view', 'fa-water'),
                ('City View', 'city-view', 'fa-city'),
                ('Garden View', 'garden-view', 'fa-leaf'),
            ],
            'wellness-spa': [
                ('Spa', 'spa', 'fa-spa'),
                ('Sauna', 'sauna', 'fa-hot-tub'),
                ('Steam Room', 'steam-room', 'fa-cloud'),
                ('Hot Tub', 'hot-tub', 'fa-hot-tub'),
                ('Massage Services', 'massage', 'fa-hands'),
                ('Fitness Center', 'fitness-center', 'fa-dumbbell'),
                ('Yoga Studio', 'yoga-studio', 'fa-pray'),
                ('Gym Equipment', 'gym-equipment', 'fa-dumbbell'),
            ],
            'pool-beach': [
                ('Outdoor Pool', 'outdoor-pool', 'fa-swimming-pool'),
                ('Indoor Pool', 'indoor-pool', 'fa-swimming-pool'),
                ('Infinity Pool', 'infinity-pool', 'fa-swimming-pool'),
                ('Private Pool', 'private-pool', 'fa-swimming-pool'),
                ('Pool Towels', 'pool-towels', 'fa-scroll'),
                ('Beach Access', 'beach-access', 'fa-umbrella-beach'),
                ('Private Beach', 'private-beach', 'fa-umbrella-beach'),
                ('Beach Towels', 'beach-towels', 'fa-scroll'),
                ('Water Sports', 'water-sports', 'fa-swimmer'),
            ],
            'family-kids': [
                ('Baby Cot', 'baby-cot', 'fa-baby'),
                ('High Chair', 'high-chair', 'fa-chair'),
                ('Kids Club', 'kids-club', 'fa-child'),
                ('Playground', 'playground', 'fa-futbol'),
                ('Babysitting', 'babysitting', 'fa-baby-carriage'),
                ('Kids Pool', 'kids-pool', 'fa-water'),
                ('Family Rooms', 'family-rooms', 'fa-users'),
                ('Kids Menu', 'kids-menu', 'fa-utensils'),
                ('Baby Bath', 'baby-bath', 'fa-baby'),
            ],
            'business': [
                ('Business Center', 'business-center', 'fa-building'),
                ('Meeting Rooms', 'meeting-rooms', 'fa-chalkboard'),
                ('Conference Facilities', 'conference', 'fa-users'),
                ('Printer', 'printer', 'fa-print'),
                ('Scanner', 'scanner', 'fa-scanner'),
                ('Projector', 'projector', 'fa-video'),
                ('Work Desk', 'work-desk', 'fa-desktop'),
            ],
            'parking-transport': [
                ('Free Parking', 'free-parking', 'fa-parking'),
                ('On-site Parking', 'onsite-parking', 'fa-parking'),
                ('Secure Parking', 'secure-parking', 'fa-car'),
                ('Valet Parking', 'valet-parking', 'fa-car-side'),
                ('Electric Vehicle Charging', 'ev-charging', 'fa-bolt'),
                ('Airport Shuttle', 'airport-shuttle', 'fa-plane-departure'),
                ('Shuttle Service', 'shuttle-service', 'fa-shuttle-van'),
                ('Car Rental', 'car-rental', 'fa-car'),
                ('Bicycle Rental', 'bicycle-rental', 'fa-bicycle'),
            ],
            'dining': [
                ('Restaurant', 'restaurant', 'fa-utensils'),
                ('Bar', 'bar', 'fa-glass-martini'),
                ('Room Service', 'room-service', 'fa-concierge-bell'),
                ('Breakfast Included', 'breakfast-included', 'fa-coffee'),
                ('Breakfast Available', 'breakfast-available', 'fa-bread-slice'),
                ('Lunch Available', 'lunch-available', 'fa-hamburger'),
                ('Dinner Available', 'dinner-available', 'fa-utensils'),
                ('All-inclusive', 'all-inclusive', 'fa-infinity'),
                ('Halal Options', 'halal', 'fa-check'),
                ('Vegetarian Options', 'vegetarian', 'fa-leaf'),
                ('Vegan Options', 'vegan', 'fa-seedling'),
            ],
            'accessibility': [
                ('Wheelchair Accessible', 'wheelchair-accessible', 'fa-wheelchair'),
                ('Elevator Access', 'elevator', 'fa-sort'),
                ('Accessible Bathroom', 'accessible-bathroom', 'fa-blind'),
                ('Ground Floor Available', 'ground-floor', 'fa-layer-group'),
                ('Hearing Loop', 'hearing-loop', 'fa-assistive-listening-systems'),
                ('Braille Signs', 'braille', 'fa-braille'),
            ],
            'services': [
                ('24-hour Front Desk', '24hr-front-desk', 'fa-clock'),
                ('Concierge', 'concierge', 'fa-concierge-bell'),
                ('Luggage Storage', 'luggage-storage', 'fa-suitcase'),
                ('Laundry Service', 'laundry', 'fa-tshirt'),
                ('Dry Cleaning', 'dry-cleaning', 'fa-tshirt'),
                ('Daily Housekeeping', 'housekeeping', 'fa-broom'),
                ('Express Check-in/out', 'express-checkin', 'fa-tachometer-alt'),
                ('Tour Desk', 'tour-desk', 'fa-map-marked-alt'),
                ('Currency Exchange', 'currency-exchange', 'fa-money-bill-wave'),
                ('Wake-up Service', 'wake-up-service', 'fa-bell'),
                ('Pets Allowed', 'pets-allowed', 'fa-paw'),
            ],
        }
        
        created_count = 0
        updated_count = 0
        
        for category_slug, amenities in amenities_data.items():
            try:
                category = AmenityCategory.objects.get(slug=category_slug)
            except AmenityCategory.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Category not found: {category_slug}"))
                continue
            
            for name, slug, icon in amenities:
                amenity, created = Amenity.objects.update_or_create(
                    slug=slug,
                    defaults={
                        'name': name,
                        'icon': icon,
                        'category': category,
                        'is_active': True,
                    }
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f"Amenities: {created_count} created, {updated_count} updated")
        )
