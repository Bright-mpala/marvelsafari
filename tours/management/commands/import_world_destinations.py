import csv
import random
import tempfile
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Optional
from urllib.request import urlretrieve

from django.core.management.base import BaseCommand, CommandParser
from django.utils.text import slugify

from tours.models import Tour, TourCategory, TourOperator

GEONAMES_URL = "http://download.geonames.org/export/dump/cities5000.zip"
# GeoNames data is provided under CC BY 4.0: https://www.geonames.org/export/


class Command(BaseCommand):
    help = "Import real-world city destinations into tours from GeoNames (cities5000)"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--max",
            type=int,
            dest="max_cities",
            default=1000,
            help="Maximum number of cities to import (default: 1000). Use 0 for no limit.",
        )
        parser.add_argument(
            "--min-pop",
            type=int,
            dest="min_population",
            default=300000,
            help="Minimum population to include a city (default: 300000).",
        )
        parser.add_argument(
            "--country",
            nargs="*",
            dest="countries",
            help="Optional list of ISO country codes to include (e.g., US GB CA).",
        )

    def handle(self, *args, **options):
        max_cities: int = options["max_cities"]
        min_pop: int = options["min_population"]
        countries: Optional[Iterable[str]] = options.get("countries")
        country_filter = {c.upper() for c in countries} if countries else None

        self.stdout.write(
            self.style.NOTICE(
                f"Downloading GeoNames cities5000 (min_pop >= {min_pop}, max={max_cities or 'all'})..."
            )
        )
        csv_path = self._download_geonames()

        category = TourCategory.objects.get_or_create(
            slug="city",
            defaults={"name": "City", "description": "City destinations"},
        )[0]
        operator = TourOperator.objects.get_or_create(
            slug="global-tours",
            defaults={
                "name": "Global Tours",
                "description": "Auto-imported global destinations",
                "website": "https://example.com",
                "is_verified": True,
            },
        )[0]

        created, updated = 0, 0
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh, delimiter="\t")
            for row_idx, row in enumerate(reader, start=1):
                if len(row) < 19:
                    continue  # malformed row
                (
                    geonameid,
                    name,
                    asciiname,
                    alternatenames,
                    latitude,
                    longitude,
                    feature_class,
                    feature_code,
                    country_code,
                    cc2,
                    admin1,
                    admin2,
                    admin3,
                    admin4,
                    population,
                    elevation,
                    dem,
                    timezone,
                    modification_date,
                ) = row[:19]

                try:
                    population_int = int(population)
                except ValueError:
                    population_int = 0

                if population_int < min_pop:
                    continue
                if country_filter and country_code.upper() not in country_filter:
                    continue

                slug = slugify(f"{asciiname or name}-{country_code}-{geonameid}")
                base_price = self._price_from_population(population_int)

                defaults = {
                    "name": f"{name} City Experience",
                    "description": f"Discover the highlights of {name} with a local expert.",
                    "operator": operator,
                    "property": None,
                    "tour_type": "guided",
                    "location": name,
                    "city": name,
                    "country": country_code,
                    "meeting_point": f"Central {name}",
                    "dropoff_point": f"Central {name}",
                    "latitude": Decimal(latitude) if latitude else None,
                    "longitude": Decimal(longitude) if longitude else None,
                    "duration_hours": random.choice([3, 4, 5, 6]),
                    "duration_days": 0,
                    "difficulty": "easy",
                    "min_participants": 1,
                    "max_participants": 20,
                    "capacity": 20,
                    "languages": ["en"],
                    "schedule": ["daily"],
                    "highlights": ["Local guide", "Small group"],
                    "base_price": base_price,
                    "currency": "USD",
                    "child_price": None,
                    "senior_price": None,
                    "group_discount": None,
                    "is_active": True,
                    "is_featured": False,
                    "average_rating": Decimal("4.6"),
                    "review_count": 0,
                    "booking_count": 0,
                }

                obj, created_flag = Tour.objects.update_or_create(slug=slug, defaults=defaults)
                obj.categories.set([category])
                created += int(created_flag)
                updated += int(not created_flag)

                if max_cities and created + updated >= max_cities:
                    break

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete: created {created}, updated {updated}, min_pop={min_pop}, max={max_cities or 'all'}"
            )
        )

    def _download_geonames(self) -> Path:
        tmpdir = Path(tempfile.mkdtemp())
        zip_path = tmpdir / "cities5000.zip"
        urlretrieve(GEONAMES_URL, zip_path)
        with zipfile.ZipFile(zip_path, "r") as zf:
            name = next((n for n in zf.namelist() if n.endswith(".txt")), None)
            if not name:
                raise RuntimeError("cities5000.txt not found in archive")
            zf.extract(name, tmpdir)
            return tmpdir / name

    @staticmethod
    def _price_from_population(population: int) -> Decimal:
        # Simple heuristic to make larger cities slightly pricier
        base = Decimal("40.00")
        bonus = Decimal(min(population / 5_000_000, 1.5)).quantize(Decimal("0.01"))
        price = base + bonus * Decimal("20.00")
        return price.quantize(Decimal("0.01"))
