from django.db import models
from django.utils.translation import gettext_lazy as _


class Country(models.Model):
    """Country reference data with ISO codes."""

    iso2 = models.CharField(_('ISO2 code'), max_length=2, unique=True)
    iso3 = models.CharField(_('ISO3 code'), max_length=3, unique=True, blank=True)
    name = models.CharField(_('country name'), max_length=200)
    official_name = models.CharField(_('official name'), max_length=255, blank=True)
    continent_code = models.CharField(_('continent code'), max_length=2, blank=True)
    currency_code = models.CharField(_('currency code'), max_length=3, blank=True)
    population = models.BigIntegerField(_('population'), default=0)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['iso2']),
            models.Index(fields=['iso3']),
        ]
        verbose_name = _('country')
        verbose_name_plural = _('countries')

    def __str__(self) -> str:  # pragma: no cover - convenience
        return f"{self.name} ({self.iso2})"


class City(models.Model):
    """City reference data linked to Country (GeoNames-backed)."""

    geoname_id = models.BigIntegerField(_('GeoNames ID'), unique=True)
    name = models.CharField(_('name'), max_length=200)
    ascii_name = models.CharField(_('ASCII name'), max_length=200, blank=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='cities')
    admin1_code = models.CharField(_('admin1 code'), max_length=50, blank=True)
    admin1_name = models.CharField(_('admin1 name'), max_length=150, blank=True)
    admin2_code = models.CharField(_('admin2 code'), max_length=50, blank=True)
    admin2_name = models.CharField(_('admin2 name'), max_length=150, blank=True)
    latitude = models.DecimalField(_('latitude'), max_digits=9, decimal_places=6)
    longitude = models.DecimalField(_('longitude'), max_digits=9, decimal_places=6)
    timezone = models.CharField(_('timezone'), max_length=50, blank=True)
    population = models.BigIntegerField(_('population'), default=0)
    feature_class = models.CharField(_('feature class'), max_length=1, blank=True)
    feature_code = models.CharField(_('feature code'), max_length=10, blank=True)
    is_capital = models.BooleanField(_('capital city'), default=False)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['country', 'name']),
            models.Index(fields=['population']),
            models.Index(fields=['timezone']),
            models.Index(fields=['feature_code']),
        ]
        verbose_name = _('city')
        verbose_name_plural = _('cities')

    def __str__(self) -> str:  # pragma: no cover - convenience
        return f"{self.name}, {self.country.iso2}"
