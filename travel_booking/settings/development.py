"""
settings/development.py - Development environment settings
"""

from .base import *

ENVIRONMENT = 'development'
DEBUG = False
SECRET_KEY = 'django-insecure-dev-key-change-in-production'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*.local', '[::1]', 'testserver']

INSTALLED_APPS += [
    # 'debug_toolbar',
]

MIDDLEWARE += [
    # 'debug_toolbar.middleware.DebugToolbarMiddleware',
]

# ==============================
# DATABASE
# ==============================

DATABASES['default'] = {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': MANAGE_PY_DIR / 'db.sqlite3',
}

# ==============================
# CACHING (Development uses in-memory)
# ==============================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-dev-cache',
        'TIMEOUT': 300,
    }
}

# ==============================
# CELERY (Synchronous in development)
# ==============================

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+locmem://'

# ==============================
# EMAIL (Gmail SMTP in development)
# ==============================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_SSL = False
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@localhost')
CONTACT_NOTIFY_EMAIL = config('CONTACT_NOTIFY_EMAIL', default='marvelsafari@gmail.com')

# ==============================
# SECURITY (Relaxed for development)
# ==============================

SESSION_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = 'Lax'  # Allow redirects to work properly
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# ==============================
# DEBUG TOOLBAR
# ==============================

INTERNAL_IPS = ['127.0.0.1', 'localhost', '::1']
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda r: DEBUG,
    'SHOW_TEMPLATE_CONTEXT': True,
    'ENABLE_STACKTRACELOCALS': True,
}

# ==============================
# LOGGING (Verbose for development)
# ==============================

LOGGING['loggers']['django']['level'] = 'DEBUG'
LOGGING['loggers']['bookings']['level'] = 'DEBUG'
LOGGING['loggers']['api']['level'] = 'DEBUG'

# ==============================
# CORS (Open for development)
# ==============================

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:8000',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:8000',
]

# ==============================
# MONITORING
# ==============================

ENABLE_METRICS = False  # Disabled in development for performance
