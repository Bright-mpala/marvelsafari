"""
settings/production.py - Production environment settings
"""

from .base import *
import logging

ENVIRONMENT = 'production'
DEBUG = False
SECRET_KEY = config('SECRET_KEY')  # Must be set in environment

ALLOWED_HOSTS = [
    host.strip()
    for host in config('ALLOWED_HOSTS', default='marvelsafari.com,www.marvelsafari.com').split(',')
    if host.strip()
]

# ==============================
# DATABASE (PostgreSQL with replication)
# ==============================

# Primary database
PRIMARY_DATABASE_URL = config('DATABASE_URL', default='postgresql://localhost/marvelsafari')
DATABASES['default'] = dj_database_url.config(
    default=PRIMARY_DATABASE_URL,
    conn_max_age=600,
    conn_health_checks=True,
)

# Enable atomic requests for safety
DATABASES['default']['ATOMIC_REQUESTS'] = True

# Read replica for analytics/reporting
REPLICA_DATABASE_URL = config('DATABASE_REPLICA_URL', default=PRIMARY_DATABASE_URL)
DATABASES['replica'] = dj_database_url.config(
    default=REPLICA_DATABASE_URL,
    conn_max_age=600,
    conn_health_checks=True,
)

# Database optimization for production
for db_config in DATABASES.values():
    db_config.setdefault('CONN_MAX_AGE', 600)
    engine = db_config.get('ENGINE', '')
    if 'postgresql' in engine:
        db_config.setdefault('OPTIONS', {})
        db_config['OPTIONS'].setdefault('connect_timeout', 10)
        db_config['OPTIONS'].setdefault('sslmode', 'require')

# ==============================
# CACHING (Redis Cluster)
# ==============================

REDIS_URL = config('REDIS_URL', default='redis://redis:6379/0')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_CLASS': 'redis.connection.BlockingConnectionPool',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 100,
                'timeout': 20,
                'retry_on_timeout': True,
            },
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': False,  # Fail fast in production
            'PICKLE_VERSION': -1,
        },
        'TIMEOUT': 900,  # 15 minutes
        'KEY_PREFIX': 'marvelsafari_prod',
        'VERSION': 1,
    },
    'session': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_SESSION_URL', default=REDIS_URL),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': 50},
            'IGNORE_EXCEPTIONS': False,
        },
        'TIMEOUT': 86400 * 30,  # 30 days
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'session'

# ==============================
# CELERY (Production configuration)
# ==============================

CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://redis:6379/1')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://redis:6379/2')
CELERY_TASK_ALWAYS_EAGER = False
CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Priority queues
CELERY_TASK_ROUTES = {
    'bookings.tasks.process_booking': {'queue': 'high_priority'},
    'bookings.tasks.expire_pending_bookings': {'queue': 'default'},
    'notifications.tasks.send_*': {'queue': 'notifications'},
    'analytics.tasks.*': {'queue': 'low_priority'},
}

# Dead letter queue for failed tasks
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# ==============================
# EMAIL (Real SMTP with retry)
# ==============================

EMAIL_BACKEND = 'django_ses.SESBackend'  # Or your production email backend
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# AWS SES (if configured)
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')

# ==============================
# SECURITY (Strict production settings)
# ==============================

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SAMESITE = 'Strict'

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in config('CSRF_TRUSTED_ORIGINS', default='https://marvelsafari.com').split(',')
    if origin.strip()
]

# Content Security Policy (strict)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "cdnjs.cloudflare.com")
CSP_STYLE_SRC = ("'self'", "cdnjs.cloudflare.com")
CSP_IMG_SRC = ("'self'", "https:")
CSP_FONT_SRC = ("'self'", "cdnjs.cloudflare.com")
CSP_CONNECT_SRC = ("'self'",)

# ==============================
# LOGGING (Structured for ELK/Datadog)
# ==============================

LOGGING['loggers']['django']['level'] = 'WARNING'
LOGGING['loggers']['bookings']['level'] = 'INFO'
LOGGING['loggers']['api']['level'] = 'INFO'

# ==============================
# CORS (Strict)
# ==============================

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in config('CORS_ALLOWED_ORIGINS', default='https://marvelsafari.com').split(',')
    if origin.strip()
]
CORS_ALLOW_ALL_ORIGINS = False

# ==============================
# MONITORING & ERROR TRACKING
# ==============================

ENABLE_METRICS = True

# Sentry for error tracking
try:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    sentry_sdk.init(
        dsn=config('SENTRY_DSN', default=''),
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=0.05,  # 5% of transactions
        profiles_sample_rate=0.01,  # 1% profiling
        send_default_pii=False,
        environment='production',
        max_breadcrumbs=50,
    )
except Exception as e:
    logging.error(f"Sentry initialization failed: {e}")

# ==============================
# RATE LIMITING (Strict)
# ==============================

RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'
# Configure rate limits via environment variables

# ==============================
# STATIC FILES (CDN-ready)
# ==============================

STATIC_URL = config('STATIC_URL', default='/static/')
STATIC_ROOT = config('STATIC_ROOT', default=MANAGE_PY_DIR / 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Configure CDN if using CloudFront/S3
AWS_S3_ENABLED = config('AWS_S3_ENABLED', default=False, cast=bool)
if AWS_S3_ENABLED:
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'

# ==============================
# MEDIA FILES (CDN-ready)
# ==============================

MEDIA_URL = config('MEDIA_URL', default='/media/')
MEDIA_ROOT = config('MEDIA_ROOT', default=MANAGE_PY_DIR / 'media')

# ==============================
# DEBUG
# ==============================

DEBUG = False
ALLOWED_HOSTS_STRICT = True

# ==============================
# PERFORMANCE
# ==============================

# Query optimization
ATOMIC_REQUESTS = True

# Cache template loading
TEMPLATES[0]['APP_DIRS'] = False
TEMPLATES[0]['OPTIONS']['loaders'] = [
    ('django.template.loaders.cached.Loader', [
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    ]),
]

# Connection pool optimization
CONN_MAX_AGE = 600

# ==============================
# HEALTHCHECK
# ==============================

HEALTHCHECK_ENABLED = True
HEALTHCHECK_CHECK_DATABASE = True
HEALTHCHECK_CHECK_REDIS = True
HEALTHCHECK_CHECK_CELERY = True
