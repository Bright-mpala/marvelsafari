from django.apps import AppConfig


class CarRentalsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'car_rentals'

    def ready(self):  # pragma: no cover - signals wiring
        from . import signals  # noqa: F401
