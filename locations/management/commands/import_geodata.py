import csv
import tempfile
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple
from urllib.request import urlretrieve

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from locations.models import City, Country

COUNTRY_INFO_URL = "http://download.geonames.org/export/dump/countryInfo.txt"
DATASET_URLS = {
    "cities500": "http://download.geonames.org/export/dump/cities500.zip",
    "cities5000": "http://download.geonames.org/export/dump/cities5000.zip",
    "cities15000": "http://download.geonames.org/export/dump/cities15000.zip",
}


class Command(BaseCommand):
    help = "Import countries and cities (ISO + GeoNames) into the locations app"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dataset",
            choices=sorted(DATASET_URLS.keys()),
            default="cities500",
            help="GeoNames dataset to use (larger dataset = more cities)",
        )
        parser.add_argument(
            "--max-cities",
            type=int,
            default=0,
            help="Optional hard cap on number of city rows to import (0 = all)",
        )
        parser.add_argument(
            "--min-pop",
            type=int,
            default=0,
            help="Minimum population for a city to be imported",
        )
        parser.add_argument(
            "--country",
            nargs="*",
            dest="countries",
            help="Optional list of ISO2 country codes to include",
        )

    def handle(self, *args, **options):
        dataset_key: str = options["dataset"]
        max_cities: int = options["max_cities"]
        min_pop: int = options["min_pop"]
        country_filter: Optional[Iterable[str]] = options.get("countries")
        country_filter_set = {c.upper() for c in country_filter} if country_filter else None

        self.stdout.write(self.style.NOTICE(f"Dataset: {dataset_key}, min_pop={min_pop}, max={max_cities or 'all'}"))

        tmpdir = Path(tempfile.mkdtemp())
        country_map, capitals = self._load_countries(tmpdir, country_filter_set)
        created_countries = len(country_map)
        self.stdout.write(self.style.SUCCESS(f"Countries ready: {created_countries}"))

        cities_created, cities_updated = self._load_cities(
            tmpdir=tmpdir,
            dataset_key=dataset_key,
            country_map=country_map,
            capitals=capitals,
            country_filter=country_filter_set,
            min_pop=min_pop,
            max_cities=max_cities,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Cities imported: created={cities_created}, updated={cities_updated}, dataset={dataset_key}"
            )
        )

    def _load_countries(
        self,
        tmpdir: Path,
        country_filter: Optional[Iterable[str]],
    ) -> Tuple[Dict[str, Country], Dict[str, str]]:
        info_path = tmpdir / "countryInfo.txt"
        urlretrieve(COUNTRY_INFO_URL, info_path)

        country_map: Dict[str, Country] = {}
        capitals: Dict[str, str] = {}

        with open(info_path, encoding="utf-8") as fh:
            reader = csv.reader(fh, delimiter="\t")
            for row in reader:
                if not row or row[0].startswith("#"):
                    continue
                if len(row) < 19:
                    continue
                (
                    iso2,
                    iso3,
                    iso_numeric,
                    fips,
                    name,
                    capital,
                    area,
                    population,
                    continent,
                    tld,
                    currency_code,
                    currency_name,
                    phone,
                    postal_format,
                    postal_regex,
                    languages,
                    geoname_id,
                    neighbours,
                    equivalent_fips,
                ) = row[:19]

                iso2_code = (iso2 or "").upper()
                if country_filter and iso2_code not in country_filter:
                    continue

                try:
                    population_val = int(population)
                except ValueError:
                    population_val = 0

                obj, _ = Country.objects.update_or_create(
                    iso2=iso2_code,
                    defaults={
                        "iso3": (iso3 or "").upper(),
                        "name": name,
                        "official_name": name,
                        "continent_code": continent,
                        "currency_code": (currency_code or "").upper(),
                        "population": population_val,
                    },
                )
                country_map[iso2_code] = obj
                if capital:
                    capitals[iso2_code] = capital

        return country_map, capitals

    def _load_cities(
        self,
        tmpdir: Path,
        dataset_key: str,
        country_map: Dict[str, Country],
        capitals: Dict[str, str],
        country_filter: Optional[Iterable[str]],
        min_pop: int,
        max_cities: int,
    ) -> Tuple[int, int]:
        dataset_url = DATASET_URLS[dataset_key]
        zip_path = tmpdir / f"{dataset_key}.zip"
        urlretrieve(dataset_url, zip_path)

        created = 0
        updated = 0
        processed = 0

        with zipfile.ZipFile(zip_path, "r") as zf:
            txt_name = next((n for n in zf.namelist() if n.endswith(".txt")), None)
            if not txt_name:
                raise RuntimeError("City dataset not found inside archive")

            with zf.open(txt_name) as fh:
                reader = csv.reader((line.decode("utf-8") for line in fh), delimiter="\t")
                for row in reader:
                    if len(row) < 19:
                        continue
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

                    country_code = (country_code or "").upper()
                    if country_filter and country_code not in country_filter:
                        continue
                    country_obj = country_map.get(country_code)
                    if not country_obj:
                        continue

                    try:
                        population_val = int(population)
                    except ValueError:
                        population_val = 0
                    if population_val < min_pop:
                        continue

                    try:
                        geoname_int = int(geonameid)
                    except ValueError:
                        continue

                    is_capital = False
                    capital_name = capitals.get(country_code)
                    if capital_name:
                        cmp_left = (asciiname or name or "").lower()
                        is_capital = cmp_left == capital_name.lower()

                    defaults = {
                        "name": name,
                        "ascii_name": asciiname or name,
                        "country": country_obj,
                        "admin1_code": admin1,
                        "admin1_name": "",  # GeoNames admin names not in this dataset
                        "admin2_code": admin2,
                        "admin2_name": "",
                        "latitude": Decimal(latitude),
                        "longitude": Decimal(longitude),
                        "timezone": timezone,
                        "population": population_val,
                        "feature_class": feature_class,
                        "feature_code": feature_code,
                        "is_capital": is_capital,
                    }

                    with transaction.atomic():
                        obj, created_flag = City.objects.update_or_create(
                            geoname_id=geoname_int,
                            defaults=defaults,
                        )
                    created += int(created_flag)
                    updated += int(not created_flag)
                    processed += 1

                    if max_cities and processed >= max_cities:
                        break

        return created, updated
