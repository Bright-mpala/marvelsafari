import random
import string
import uuid
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import User, UserRole
from properties.models import Property, PropertyType, PropertyStatus
from car_rentals.models import (
    Car,
    CarCategory,
    CarRentalCompany,
    CarStatus,
    OperationalStatus,
)
from tours.models import Tour, TourCategory, TourOperator
from blog.models import BlogPost


class Command(BaseCommand):
    help = "Seed demo data for users, properties, cars, tours, and blog posts."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=1000, help="Number of users to create")
        parser.add_argument("--properties", type=int, default=200, help="Number of properties to create")
        parser.add_argument("--cars", type=int, default=200, help="Number of cars to create")
        parser.add_argument("--tours", type=int, default=200, help="Number of tours to create")
        parser.add_argument("--blogs", type=int, default=200, help="Number of blog posts to create")
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Batch size for bulk_create (reduce if you hit memory issues)",
        )

    # --------------------
    # Helpers
    # --------------------

    def _rand_slug(self, base: str) -> str:
        return f"{slugify(base)}-{uuid.uuid4().hex[:8]}"

    def _rand_plate(self) -> str:
        letters = "".join(random.choices(string.ascii_uppercase, k=3))
        digits = "".join(random.choices(string.digits, k=3))
        return f"{letters}-{digits}-{random.randint(10, 99)}"

    def _choice(self, items):
        return random.choice(items)

    # --------------------
    # Seeders
    # --------------------

    def _seed_users(self, total: int, batch_size: int):
        if total <= 0:
            return
        password_hash = make_password("Password123!")
        countries = ["US", "GB", "FR", "DE", "KE", "NG", "ZA", "AE", "CA", "BR"]
        first_names = ["Alex", "Jamie", "Taylor", "Jordan", "Morgan", "Riley", "Casey", "Sam"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
        created = 0
        base_index = User.objects.count()
        for start in range(0, total, batch_size):
            size = min(batch_size, total - start)
            users = []
            for i in range(size):
                idx = base_index + start + i
                first = self._choice(first_names)
                last = self._choice(last_names)
                email = f"user{idx}@example.com"
                users.append(
                    User(
                        email=email,
                        first_name=first,
                        last_name=last,
                        password=password_hash,
                        role=UserRole.CUSTOMER,
                        preferred_currency="USD",
                        preferred_language="en",
                        country=self._choice(countries),
                        is_active=True,
                        is_email_verified=True,
                    )
                )
            User.objects.bulk_create(users, batch_size=batch_size, ignore_conflicts=True)
            created += len(users)
            self.stdout.write(self.style.SUCCESS(f"Users created so far: {created}/{total}"))

    def _seed_property_types(self):
        seeds = [
            ("Hotel", "hotel"),
            ("Apartment", "apartment"),
            ("Resort", "resort"),
            ("Hostel", "hostel"),
            ("Villa", "villa"),
        ]
        for name, slug in seeds:
            PropertyType.objects.get_or_create(slug=slug, defaults={"name": name})
        return list(PropertyType.objects.filter(slug__in=[s for _, s in seeds]))

    def _seed_properties(self, total: int, batch_size: int, owners):
        if total <= 0:
            return
        property_types = self._seed_property_types()
        cities = ["Nairobi", "Mombasa", "Lagos", "Cairo", "Cape Town", "London", "New York", "Dubai"]
        countries = ["KE", "NG", "EG", "ZA", "GB", "US", "AE"]
        streets = ["Main St", "High St", "Market Rd", "Coastal Ave", "Park Lane", "Sunset Blvd"]
        created = 0
        for start in range(0, total, batch_size):
            size = min(batch_size, total - start)
            props = []
            for i in range(size):
                name = f"Property {start + i + 1}"
                props.append(
                    Property(
                        name=name,
                        slug=self._rand_slug(name),
                        description="Comfortable stay with great amenities.",
                        property_type=self._choice(property_types),
                        address=f"{random.randint(1, 999)} {self._choice(streets)}",
                        city=self._choice(cities),
                        state="",
                        postal_code=str(random.randint(10000, 99999)),
                        country=self._choice(countries),
                        phone="+254700000000",
                        email="bookings@example.com",
                        website="https://example.com",
                        owner=self._choice(owners) if owners else None,
                        cancellation_policy="Free cancellation within 24 hours.",
                        house_rules="No smoking inside rooms.",
                        total_rooms=random.randint(10, 200),
                        status=PropertyStatus.APPROVED,
                        is_verified=True,
                        is_featured=False,
                        published_at=timezone.now(),
                        view_count=random.randint(0, 5000),
                        booking_count=random.randint(0, 500),
                        average_rating=Decimal("4.%d" % random.randint(0, 9)),
                        review_count=random.randint(0, 400),
                        commission_rate=Decimal("15.00"),
                        minimum_price=Decimal(str(random.randint(50, 150))),
                        maximum_price=Decimal(str(random.randint(200, 600))),
                    )
                )
            Property.objects.bulk_create(props, batch_size=batch_size, ignore_conflicts=True)
            created += len(props)
            self.stdout.write(self.style.SUCCESS(f"Properties created so far: {created}/{total}"))

    def _seed_car_categories(self):
        seeds = [
            ("Economy", "ECO"),
            ("SUV", "SUV"),
            ("Luxury", "LUX"),
            ("Van", "VAN"),
        ]
        for name, code in seeds:
            CarCategory.objects.get_or_create(code=code, defaults={"name": name})
        return list(CarCategory.objects.filter(code__in=[c for _, c in seeds]))

    def _seed_companies(self):
        seeds = [
            ("Marvel Mobility", "MMOB"),
            ("Safari Cars", "SCAR"),
            ("City Wheels", "CWHE"),
        ]
        companies = []
        for name, code in seeds:
            company, _ = CarRentalCompany.objects.get_or_create(
                code=code,
                defaults={"name": name, "offers_rental": True, "offers_taxi": True},
            )
            companies.append(company)
        return companies

    def _seed_cars(self, total: int, batch_size: int, owners):
        if total <= 0:
            return
        categories = self._seed_car_categories()
        companies = self._seed_companies()
        makes = ["Toyota", "Nissan", "Honda", "Mazda", "BMW", "Mercedes", "Audi", "Hyundai"]
        models = ["Corolla", "Civic", "Camry", "CX-5", "X5", "C-Class", "A4", "Tucson"]
        colors = ["White", "Black", "Silver", "Blue", "Red", "Grey"]
        created = 0
        for start in range(0, total, batch_size):
            size = min(batch_size, total - start)
            cars = []
            for i in range(size):
                make = self._choice(makes)
                model = self._choice(models)
                plate = self._rand_plate()
                cars.append(
                    Car(
                        company=self._choice(companies),
                        category=self._choice(categories),
                        owner=self._choice(owners) if owners else None,
                        slug=self._rand_slug(f"{make}-{model}"),
                        make=make,
                        model=model,
                        year=random.randint(2015, 2024),
                        license_plate=plate,
                        color=self._choice(colors),
                        service_type=self._choice(["rental", "taxi", "both"]),
                        seats=random.randint(4, 7),
                        doors=random.randint(3, 5),
                        has_ac=True,
                        has_gps=random.choice([True, False]),
                        has_bluetooth=True,
                        has_usb=True,
                        has_child_seat=random.choice([True, False]),
                        has_wifi=random.choice([True, False]),
                        has_dashcam=random.choice([True, False]),
                        taxi_rate_per_km=Decimal("%.2f" % random.uniform(0.5, 2.5)),
                        taxi_base_fare=Decimal("%.2f" % random.uniform(2.0, 8.0)),
                        taxi_per_hour=Decimal("%.2f" % random.uniform(5.0, 25.0)),
                        status=OperationalStatus.AVAILABLE,
                        moderation_status=CarStatus.APPROVED,
                        mileage=Decimal(random.randint(1000, 150000)),
                        daily_price=Decimal(random.randint(30, 250)),
                        is_featured=random.choice([True, False]),
                    )
                )
            Car.objects.bulk_create(cars, batch_size=batch_size, ignore_conflicts=True)
            created += len(cars)
            self.stdout.write(self.style.SUCCESS(f"Cars created so far: {created}/{total}"))

    def _seed_tour_taxonomies(self):
        categories = [
            ("Wildlife", "wildlife"),
            ("City", "city"),
            ("Beach", "beach"),
            ("Cultural", "cultural"),
            ("Adventure", "adventure"),
        ]
        operators = [
            ("Marvel Tours", "marvel-tours"),
            ("Safari Adventures", "safari-adventures"),
            ("Urban Explorers", "urban-explorers"),
        ]
        for name, slug in categories:
            TourCategory.objects.get_or_create(slug=slug, defaults={"name": name})
        for name, slug in operators:
            TourOperator.objects.get_or_create(slug=slug, defaults={"name": name})
        return list(TourCategory.objects.filter(slug__in=[s for _, s in categories])), list(
            TourOperator.objects.filter(slug__in=[s for _, s in operators])
        )

    def _seed_tours(self, total: int, batch_size: int, properties):
        if total <= 0:
            return
        categories, operators = self._seed_tour_taxonomies()
        cities = ["Nairobi", "Maasai Mara", "Mombasa", "Cape Town", "Victoria Falls", "Cairo", "Accra"]
        countries = ["Kenya", "South Africa", "Egypt", "Ghana", "Tanzania", "Uganda"]
        created = 0
        for start in range(0, total, batch_size):
            size = min(batch_size, total - start)
            tours = []
            for i in range(size):
                name = f"Tour {start + i + 1}"
                operator = self._choice(operators)
                tour = Tour(
                    name=name,
                    slug=self._rand_slug(name),
                    description="Memorable experience with local guides.",
                    operator=operator,
                    property=random.choice(properties) if properties else None,
                    tour_type=self._choice([c[0] for c in Tour.TOUR_TYPES]),
                    location=self._choice(cities),
                    city=self._choice(cities),
                    country=self._choice(countries),
                    meeting_point="Hotel lobby",
                    dropoff_point="City center",
                    duration_hours=random.randint(2, 8),
                    duration_days=random.choice([0, 1, 2, 3]),
                    difficulty=self._choice([c[0] for c in Tour.DIFFICULTY_LEVELS]),
                    min_participants=1,
                    max_participants=random.randint(5, 30),
                    capacity=random.randint(10, 40),
                    base_price=Decimal(random.randint(30, 500)),
                    currency="USD",
                    is_active=True,
                    is_featured=random.choice([True, False]),
                    average_rating=Decimal("4.%d" % random.randint(0, 9)),
                    review_count=random.randint(0, 300),
                    booking_count=random.randint(0, 800),
                )
                tours.append(tour)
            Tour.objects.bulk_create(tours, batch_size=batch_size, ignore_conflicts=True)
            # attach categories in a second step to avoid m2m during bulk_create
            created += len(tours)
            self.stdout.write(self.style.SUCCESS(f"Tours created so far: {created}/{total}"))
        # Attach categories
        tour_qs = Tour.objects.order_by("-id")[: total]
        all_categories = list(TourCategory.objects.all())
        for tour in tour_qs:
            tour.categories.add(*random.sample(all_categories, k=min(len(all_categories), 2)))

    def _seed_blogs(self, total: int, batch_size: int, authors):
        if total <= 0:
            return
        created = 0
        for start in range(0, total, batch_size):
            size = min(batch_size, total - start)
            posts = []
            for i in range(size):
                title = f"Travel Story {start + i + 1}"
                posts.append(
                    BlogPost(
                        title=title,
                        slug=self._rand_slug(title),
                        excerpt="A short overview of the journey.",
                        content="Detailed experience, highlights, and tips for fellow travelers.",
                        author=self._choice(authors) if authors else None,
                        is_published=True,
                        published_at=timezone.now() - timedelta(days=random.randint(0, 365)),
                    )
                )
            BlogPost.objects.bulk_create(posts, batch_size=batch_size, ignore_conflicts=True)
            created += len(posts)
            self.stdout.write(self.style.SUCCESS(f"Blog posts created so far: {created}/{total}"))

    # --------------------
    # Entry point
    # --------------------

    def handle(self, *args, **options):
        users_count = options["users"]
        properties_count = options["properties"]
        cars_count = options["cars"]
        tours_count = options["tours"]
        blogs_count = options["blogs"]
        batch_size = options["batch_size"]

        if users_count > 2_000_000:
            raise CommandError("Refusing to create more than 2,000,000 users in one go. Use a smaller batch.")

        self.stdout.write(self.style.WARNING("Starting demo data seeding..."))

        self._seed_users(users_count, batch_size)

        owner_pool_ids = list(
            User.objects.order_by("id").values_list("id", flat=True)[: max(2000, min(users_count, 5000))]
        )
        owners = list(User.objects.filter(id__in=owner_pool_ids))

        self._seed_properties(properties_count, batch_size, owners)

        property_pool = list(Property.objects.order_by("-id")[: max(2000, properties_count)])

        self._seed_cars(cars_count, batch_size, owners)

        self._seed_tours(tours_count, batch_size, property_pool)

        self._seed_blogs(blogs_count, batch_size, owners)

        self.stdout.write(self.style.SUCCESS("Seeding complete."))
