"""
Django settings for travel_booking project.
"""

import os
from pathlib import Path
from decouple import config
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)
DJANGO_LOG_LEVEL = config('DJANGO_LOG_LEVEL', default='INFO')

ALLOWED_HOSTS = [host.strip() for host in config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',') if host.strip()]
if DEBUG:
    ALLOWED_HOSTS += ['127.0.0.1', 'localhost', 'testserver']
ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS))

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    
    # Third-party apps
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_extensions',
    'django_filters',
    'phonenumber_field',
    'django_countries',
    'taggit',
    'mptt',
    'import_export',
    'guardian',
    'django_celery_beat',
    'django_celery_results',
    
    # Local apps
    'accounts',
    'properties.apps.PropertiesConfig',
    'bookings',
    'flights',
    'car_rentals',
    'tours',
    'reviews',
    'payments',
    'api',
    'analytics',
    'business',
    'notifications',
    'newsletter',
    'blog',
    'ai_assistant',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'travel_booking.middleware.StrictHttpVersionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'travel_booking.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'properties.context_processors.search_form',
                'bookings.context_processors.booking_cart',
            ],
        },
    },
]

WSGI_APPLICATION = 'travel_booking.wsgi.application'

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Authentication settings
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
]
# Provider specific settings
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
    }
}

SITE_ID = 1
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# CORS settings
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in config('CORS_ALLOWED_ORIGINS', default='').split(',') if origin.strip()]

# Email settings
# EMAIL SETTINGS (Gmail SMTP)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_USE_TLS = False
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')  # Use Gmail app password via .env
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER or 'no-reply@marvelsafari.com')
CONTACT_NOTIFY_EMAIL = config('CONTACT_NOTIFY_EMAIL', default=DEFAULT_FROM_EMAIL)
CONTACT_EMAIL_RECIPIENT = config('CONTACT_EMAIL_RECIPIENT', default=DEFAULT_FROM_EMAIL)

# Fallback to console email backend when debugging locally and SMTP is not configured
if DEBUG and not EMAIL_HOST_USER:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Celery settings
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Stripe settings
STRIPE_PUBLISHABLE_KEY = config('STRIPE_PUBLISHABLE_KEY', default='')
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')

# Cache settings
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Session settings
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'

# Security settings
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True 

# HTTP protocol guardrails
STRICT_HTTP_VERSION_ENABLED = config('STRICT_HTTP_VERSION_ENABLED', default=True, cast=bool)
SUPPORTED_HTTP_PROTOCOLS = {
    proto.strip().upper()
    for proto in config('SUPPORTED_HTTP_PROTOCOLS', default='HTTP/1.1,HTTP/2.0').split(',')
    if proto.strip()
}
if not SUPPORTED_HTTP_PROTOCOLS:
    SUPPORTED_HTTP_PROTOCOLS = {'HTTP/1.1'}

# AI assistant configuration
AI_PROVIDER_ORDER = [
    provider.strip()
    for provider in config('AI_ASSISTANT_PROVIDER_ORDER', default='').split(',')
    if provider.strip()
]
OPENAI_API_KEY = config('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', default='')
OPENAI_ORG_ID = config('OPENAI_ORG_ID', default='')
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')
AI_ASSISTANT = {
    'DEFAULT_PROVIDER': config('AI_ASSISTANT_PROVIDER', default='openai'),
    'PROVIDER_ORDER': AI_PROVIDER_ORDER,
    'OPENAI_MODEL': config('AI_ASSISTANT_OPENAI_MODEL', default='gpt-4o-mini'),
    'ANTHROPIC_MODEL': config('AI_ASSISTANT_ANTHROPIC_MODEL', default='claude-3-5-sonnet-20241022'),
    'TEMPERATURE': config('AI_ASSISTANT_TEMPERATURE', default=0.2, cast=float),
    'MAX_OUTPUT_TOKENS': config('AI_ASSISTANT_MAX_TOKENS', default=900, cast=int),
}
AI_OPENAI_TIMEOUT = config('AI_OPENAI_TIMEOUT', default=30, cast=int)
AI_OPENAI_MAX_RETRIES = config('AI_OPENAI_MAX_RETRIES', default=2, cast=int)
AI_MAX_DAILY_TOKENS = config('AI_MAX_DAILY_TOKENS', default=200000, cast=int)
AI_MAX_DAILY_COST_USD = config('AI_MAX_DAILY_COST_USD', default=75.0, cast=float)
AI_PROMPT_COST_PER_1K = config('AI_PROMPT_COST_PER_1K', default=0.005, cast=float)
AI_COMPLETION_COST_PER_1K = config('AI_COMPLETION_COST_PER_1K', default=0.015, cast=float)
AI_RATE_LIMIT_REQUESTS_PER_MIN = config('AI_RATE_LIMIT_REQUESTS_PER_MIN', default=20, cast=int)
AI_USAGE_LOGGER_NAME = config('AI_USAGE_LOGGER_NAME', default='ai_assistant.usage')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'structured': {
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'structured',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': DJANGO_LOG_LEVEL,
            'propagate': False,
        },
        'ai_assistant': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'ai_assistant.usage': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
