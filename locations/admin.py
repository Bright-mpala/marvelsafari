from django.contrib import admin

from .models import City, Country


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'iso2', 'iso3', 'continent_code', 'currency_code', 'population')
    search_fields = ('name', 'iso2', 'iso3', 'currency_code')
    list_filter = ('continent_code',)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'timezone', 'population', 'feature_code', 'is_capital')
    search_fields = ('name', 'ascii_name', 'country__name', 'country__iso2', 'geoname_id')
    list_filter = ('country', 'timezone', 'is_capital')
    ordering = ('name',)
