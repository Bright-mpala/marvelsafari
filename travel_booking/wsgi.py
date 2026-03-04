"""
WSGI config for travel_booking project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
from decouple import config

from django.core.wsgi import get_wsgi_application

# Load environment variable, default to development
environment = config('ENVIRONMENT', default='development')

# Map environment to settings module
settings_modules = {
    'development': 'travel_booking.settings.development',
    'staging': 'travel_booking.settings.staging',
    'production': 'travel_booking.settings.production',
}

settings_module = settings_modules.get(environment, 'travel_booking.settings.development')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

application = get_wsgi_application()

