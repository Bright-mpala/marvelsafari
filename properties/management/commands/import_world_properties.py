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

from properties.models import Property, PropertyStatus, PropertyType

GEONAMES_URL = "http://download.geonames.org/export/dump/cities5000.zip"
# GeoNames data is provided under CC BY 4.0: https://www.geonames.org/export/


class Command(BaseCommand):
    help = "Import real-world properties per city using GeoNames cities5000"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--max-cities",
            type=int,
            dest="max_cities",
            default=0,
            help="Maximum number of cities to process (0 = all)",
        )
        parser.add_argument(
            "--per-city",
            type=int,
            dest="per_city",
            default=3,
            help="Number of properties to create per city (default: 3)",
        )
        parser.add_argument(
            "--min-pop",
            type=int,
            dest="min_population",
            default=300000,
            help="Minimum population to include a city (default: 300000)",
        )
        parser.add_argument(
            "--country",
            nargs="*",
            dest="countries",
            help="Optional list of ISO country codes to include (e.g., US GB CA)",
        )

    def handle(self, *args, **options):
        max_cities: int = options["max_cities"]
        per_city: int = options["per_city"]
        min_pop: int = options["min_population"]
        countries: Optional[Iterable[str]] = options.get("countries")
        country_filter = {c.upper() for c in countries} if countries else None

        if per_city < 1:
            self.stderr.write("per-city must be >= 1")
            return

        self.stdout.write(
            self.style.NOTICE(
                f"Downloading GeoNames cities5000 (min_pop >= {min_pop}, cities={max_cities or 'all'}, per_city={per_city})..."
            )
        )
        csv_path = self._download_geonames()

        property_type = PropertyType.objects.get_or_create(
            slug="hotel",
            defaults={"name": "Hotel", "description": "Hotels and stays"},
        )[0]

        created_props = 0
        updated_props = 0
        processed_cities = 0

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

                processed_cities += 1
                if max_cities and processed_cities > max_cities:
                    break

                lat = Decimal(latitude) if latitude else None
                lon = Decimal(longitude) if longitude else None
                base_price = self._price_from_population(population_int)

                for idx in range(1, per_city + 1):
                    prop_name = f"{name} Stay {idx}" if per_city > 1 else f"{name} Stay"
                    slug = slugify(f"{asciiname or name}-{geonameid}-{idx}")
                    price = base_price + Decimal(idx - 1) * Decimal("5.00")

                    defaults = {
                        "name": prop_name,
                        "description": f"Comfortable stay in {name}, {country_code} with easy access to local highlights.",
                        "property_type": property_type,
                        "address": f"Central {name}",
                        "city": name,
                        "state": admin1 or "",
                        "postal_code": str(geonameid),
                        "country": country_code,
                        "latitude": lat,
                        "longitude": lon,
                        "star_rating": random.randint(3, 5),
                        "status": PropertyStatus.APPROVED,
                        "is_verified": True,
                        "is_featured": (idx % 5 == 0),
                        "total_rooms": random.randint(40, 200),
                        "average_rating": Decimal("4.5"),
                        "review_count": random.randint(5, 120),
                        "booking_count": random.randint(10, 300),
                        "minimum_price": price,
                        "maximum_price": price + Decimal("80.00"),
                    }

                    obj, created_flag = Property.objects.update_or_create(slug=slug, defaults=defaults)
                    created_props += int(created_flag)
                    updated_props += int(not created_flag)

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete: cities processed {processed_cities}, properties created {created_props}, updated {updated_props}"
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
        base = Decimal("60.00")
        bonus = Decimal(min(population / 5_000_000, 2)).quantize(Decimal("0.01"))
        price = base + bonus * Decimal("30.00")
        return price.quantize(Decimal("0.01"))
