#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from decouple import config


def main():
    """Run administrative tasks."""
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
    
    print(f"[INFO] Using settings module: {settings_module}")
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
