"""
settings/staging.py - Staging environment settings
"""

from .base import *
import logging

ENVIRONMENT = 'staging'
DEBUG = False
SECRET_KEY = config('SECRET_KEY', default='change-me-in-staging')

ALLOWED_HOSTS = [
    host.strip()
    for host in config('ALLOWED_HOSTS', default='staging.marvelsafari.com').split(',')
    if host.strip()
]

# ==============================
# DATABASE (PostgreSQL with connection pooling)
# ==============================

DATABASES['default'] = dj_database_url.config(
    default='postgresql://user:password@postgres:5432/marvelsafari_staging',
    conn_max_age=600,
    conn_health_checks=True,
)

# Enable atomic requests for safety
DATABASES['default']['ATOMIC_REQUESTS'] = True

# ==============================
# CACHING (Redis)
# ==============================

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://redis:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,  # Continue on Redis failure
        },
        'TIMEOUT': 600,  # 10 minutes
        'KEY_PREFIX': 'marvelsafari_staging',
        'VERSION': 1,
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# ==============================
# CELERY (Real broker in staging)
# ==============================

CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://redis:6379/1')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://redis:6379/2')
CELERY_TASK_ALWAYS_EAGER = False

# ==============================
# EMAIL (Real SMTP)
# ==============================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# ==============================
# SECURITY (Production-like)
# ==============================

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False  # Set to True after testing

CSRF_TRUSTED_ORIGINS = [
    'https://staging.marvelsafari.com',
]

# ==============================
# LOGGING
# ==============================

LOGGING['loggers']['django']['level'] = 'INFO'
LOGGING['loggers']['bookings']['level'] = 'INFO'
LOGGING['loggers']['api']['level'] = 'INFO'

# ==============================
# CORS
# ==============================

CORS_ALLOWED_ORIGINS = [
    'https://staging.marvelsafari.com',
    'https://app.staging.marvelsafari.com',
]
CORS_ALLOW_ALL_ORIGINS = False

# ==============================
# MONITORING & SENTRY
# ==============================

ENABLE_METRICS = True

try:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=config('SENTRY_DSN', default=''),
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
        ],
        traces_sample_rate=0.1,  # 10% of transactions
        send_default_pii=False,
        environment='staging',
    )
except Exception as e:
    logging.warning(f"Sentry initialization failed: {e}")

# ==============================
# RATE LIMITING
# ==============================

RATELIMIT_ENABLE = True
# Disable whitelist in staging to test rate limiting
RATELIMIT_WHITELIST = []

# ==============================
# DEBUG (Disabled)
# ==============================

DEBUG = False
