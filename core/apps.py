"""
Core App - Shared Infrastructure and Utilities

This app provides cross-cutting concerns and utilities used across all services:
- Pagination
- Exception handling
- Health checks
- Logging
- Metrics
- Error responses
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Core Infrastructure'

    def ready(self):
        """Initialize monitoring and logging when app is ready."""
        # Setup monitoring hooks if enabled
        if hasattr(settings := __import__('django.conf', fromlist=['settings']).settings, 'ENABLE_METRICS'):
            if settings.ENABLE_METRICS:
                try:
                    from core.monitoring import setup_metrics
                    setup_metrics()
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to setup metrics: {e}")
