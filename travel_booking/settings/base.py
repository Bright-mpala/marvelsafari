"""
settings/base.py - Shared settings for all environments
"""

import os
from pathlib import Path
from decouple import config
import dj_database_url
import logging.config

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # travel_booking_platform/travel_booking
MANAGE_PY_DIR = BASE_DIR  # Same as BASE_DIR - where manage.py is located

# ==============================
# CORE SETTINGS (Environment-agnostic)
# ==============================

ENVIRONMENT = config('ENVIRONMENT', default='development')
SECRET_KEY = config('SECRET_KEY', default='change-me-in-production')


def _env_bool(name, default=False):
    """
    Parse boolean environment flags defensively.

    Accepts common CI/ops values and treats unknown values as the provided
    default instead of crashing settings import.
    """
    raw_value = config(name, default=str(default))
    if isinstance(raw_value, bool):
        return raw_value

    value = str(raw_value).strip().lower()
    truthy = {'1', 'true', 't', 'yes', 'y', 'on'}
    falsy = {'0', 'false', 'f', 'no', 'n', 'off', '', 'release', 'prod', 'production'}

    if value in truthy:
        return True
    if value in falsy:
        return False
    return default


DEBUG = _env_bool('DEBUG', default=False)

# Allow configurable host list; default to all for convenience (override in env vars for prod)
ALLOWED_HOSTS = [
    host.strip()
    for host in config('ALLOWED_HOSTS', default='*').split(',')
    if host.strip()
]

# Application definition
INSTALLED_APPS = [
    'jazzmin',
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
    'allauth.socialaccount.providers.google',
    
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
    # 'mppt',  # Disabled - package not available
    'import_export',
    'guardian',
    'django_celery_beat',
    'django_celery_results',
    'drf_spectacular',
    
    # Local apps (domain services)
    'accounts',
    'properties',
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
    'locations',
    
    # Infrastructure apps
    'core',  # Will create for shared utilities
]

JAZZMIN_SETTINGS = {
    "site_title": "marvel.safari.essence.admin",
    "site_header": "marvel.safari.essence.admin",
    "welcome_sign": "Premium control center",
    "site_brand": "Marvel Safari",
    "site_logo": "favicon.svg",
    "login_logo": "favicon.svg",
    "login_title": "Marvel Safari Admin",
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    # Keep login uncluttered: disable global search and top menu on login
    "search_model": [],
    "order_with_respect_to": [
        "properties",
        "bookings",
        "tours",
        "payments",
        "accounts",
    ],
    "topmenu_links": [],
    "copyright": "Marvel Safari",
    "related_modal_active": True,
    "icons": {
        "accounts.User": "fas fa-user-circle",
        "accounts.BusinessAccount": "fas fa-briefcase",
        "properties.Property": "fas fa-hotel",
        "properties.PropertyType": "fas fa-tags",
        "properties.Amenity": "fas fa-spa",
        "bookings.Booking": "fas fa-calendar-check",
        "payments.Transaction": "fas fa-credit-card",
        "tours.Tour": "fas fa-route",
        "tours.TourSchedule": "fas fa-clock",
        "tours.TourBooking": "fas fa-ticket-alt",
        "reviews.Review": "fas fa-star",
        "newsletter.Subscriber": "fas fa-envelope-open-text",
        "notifications.Notification": "fas fa-bell",
        "blog.Post": "fas fa-newspaper",
        "analytics.Metric": "fas fa-chart-line",
    },
}

JAZZMIN_UI_TWEAKS = {
    "theme": "cosmo",
    "dark_mode_theme": None,
    "body_small_text": False,
    "brand_color": "#0f172a",
    "accent": "accent-primary",
    "navbar": "navbar-dark",
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "footer_fixed": False,
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'travel_booking.middleware.RequestTrackingMiddleware',
    'travel_booking.middleware.HealthCheckMiddleware',
]

ROOT_URLCONF = 'travel_booking.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [MANAGE_PY_DIR / 'templates'],
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

# ==============================
# DATABASE (Can be overridden)
# ==============================

DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Enable atomic requests for safety
DATABASES['default']['ATOMIC_REQUESTS'] = True

# ==============================
# AUTHENTICATION
# ==============================

AUTH_USER_MODEL = 'accounts.User'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,  # Enterprise-grade minimum
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

SITE_ID = 1
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# ==============================
# ALLAUTH CONFIGURATION
# ==============================

# Account settings
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'email2*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[MarvelSafari] '

# Use email-only authentication with custom user model (no username field)
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_MODEL_EMAIL_FIELD = 'email'

# Social Account Settings
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True

# Google OAuth Settings
# Note: OAuth credentials are stored in database via SocialApp model
# Use setup_google_oauth.py to configure them, or add via admin panel
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

# ==============================
# REST FRAMEWORK
# ==============================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.EnterprisePageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.AcceptHeaderVersioning',
    'DEFAULT_VERSION': '1.0',
    'ALLOWED_VERSIONS': ['1.0', '2.0'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'EXCEPTION_HANDLER': 'core.exceptions.enterprise_exception_handler',
    'NUM_PROXIES': 1,  # For X-Forwarded-For header
}

# JWT Configuration
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JTI_CLAIM': 'jti',
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_URL': None,
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
    'TOKEN_OBTAIN_SERIALIZER': 'accounts.authentication.CustomTokenObtainPairSerializer',
    'TOKEN_REFRESH_SERIALIZER': 'accounts.authentication.CustomTokenRefreshSerializer',
    'TOKEN_VERIFY_SERIALIZER': 'rest_framework_simplejwt.serializers.TokenVerifySerializer',
    'TOKEN_BLACKLIST_SERIALIZER': 'rest_framework_simplejwt.serializers.TokenBlacklistSerializer',
    'SLIDING_TOKEN_OBTAIN_SERIALIZER': 'rest_framework_simplejwt.serializers.TokenObtainSlidingSerializer',
    'SLIDING_TOKEN_REFRESH_SERIALIZER': 'rest_framework_simplejwt.serializers.TokenRefreshSlidingSerializer',
}

# ==============================
# CORS
# ==============================

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    origin.strip() 
    for origin in config('CORS_ALLOWED_ORIGINS', default='').split(',')
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True
CORS_MAX_AGE = 86400

# ==============================
# INTERNATIONALIZATION
# ==============================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = config('TIME_ZONE', default='UTC')
USE_I18N = True
USE_TZ = True

# ==============================
# STATIC & MEDIA FILES
# ==============================

STATIC_URL = '/static/'
STATICFILES_DIRS = [MANAGE_PY_DIR / 'static']
STATIC_ROOT = MANAGE_PY_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = MANAGE_PY_DIR / 'media'

# ==============================
# CACHING (Can be overridden per environment)
# ==============================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'default',
        'TIMEOUT': 300,
    }
}

# Admin dashboard cache window (seconds)
ADMIN_DASHBOARD_CACHE_SECONDS = config('ADMIN_DASHBOARD_CACHE_SECONDS', default=300, cast=int)

SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400 * 30  # 30 days
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Strict'

# Allow larger admin forms (e.g., tours with many fields/relations)
DATA_UPLOAD_MAX_NUMBER_FIELDS = config('DATA_UPLOAD_MAX_NUMBER_FIELDS', default=5000, cast=int)

# ==============================
# CELERY CONFIGURATION
# ==============================

CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='memory://')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='db+sqlite:///db.sqlite3')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
CELERY_TASK_MAX_RETRIES = 3

CELERY_BEAT_SCHEDULE = {
    'expire-pending-bookings': {
        'task': 'bookings.tasks.expire_pending_bookings',
        'schedule': 300.0,  # Every 5 minutes
    },
    'send-booking-reminders': {
        'task': 'notifications.tasks.send_booking_reminders',
        'schedule': 3600.0,  # Every hour
    },
    'aggregate-analytics': {
        'task': 'analytics.tasks.aggregate_daily_analytics',
        'schedule': 86400.0,  # Every day at midnight (configure TZ)
    },
}

# Route tasks to queues
CELERY_TASK_ROUTES = {
    'bookings.tasks.*': {'queue': 'bookings'},
    'notifications.tasks.*': {'queue': 'notifications'},
    'analytics.tasks.*': {'queue': 'analytics'},
}

# ==============================
# EMAIL CONFIGURATION
# ==============================

EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@marvelsafari.com')
SUPPORT_EMAIL = config('SUPPORT_EMAIL', default=DEFAULT_FROM_EMAIL)
PUBLIC_BASE_URL = config('PUBLIC_BASE_URL', default='')

# ==============================
# SECURITY (Base settings)
# ==============================

# CSRF
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'
CSRF_TRUSTED_ORIGINS = [
    origin.strip() 
    for origin in config('CSRF_TRUSTED_ORIGINS', default='').split(',')
    if origin.strip()
]

# Content Security Policy (will be set per environment)
CSP_DEFAULT_SRC = ("'self'",)

# X-Frame-Options
X_FRAME_OPTIONS = 'DENY'

# Secure headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# ==============================
# LOGGING
# ==============================

# Build formatters dict dynamically
_formatters = {
    'verbose': {
        'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
        'style': '{',
    },
}

# Try to add JSON formatter if pythonjsonlogger is available
try:
    import pythonjsonlogger.jsonlogger
    _formatters['json'] = {
        '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
        'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
    }
    _default_formatter = 'verbose' if DEBUG else 'json'
except ImportError:
    _default_formatter = 'verbose'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': _formatters,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': _default_formatter,
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'mail_admins'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'bookings': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'bookings.services': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'api': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ==============================
# EMAIL SETTINGS
# ==============================

# Default email settings (can be overridden in environment-specific settings)
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='Marvel Safari <noreply@marvelsafari.com>')
SERVER_EMAIL = config('SERVER_EMAIL', default='Marvel Safari <server@marvelsafari.com>')

# Contact form recipient
CONTACT_EMAIL_RECIPIENT = config('CONTACT_EMAIL_RECIPIENT', default='marvelsafari@gmail.com')
CONTACT_NOTIFY_EMAIL = config('CONTACT_NOTIFY_EMAIL', default='marvelsafari@gmail.com')

# ==============================
# AI ASSISTANT CONFIGURATION
# ==============================

AI_PROVIDER_ORDER = [
    provider.strip()
    for provider in config('AI_ASSISTANT_PROVIDER_ORDER', default='').split(',')
    if provider.strip()
]

OPENAI_API_KEY = config('OPENAI_API_KEY', default='')
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')

AI_ASSISTANT = {
    'DEFAULT_PROVIDER': config('AI_ASSISTANT_PROVIDER', default='openai'),
    'PROVIDER_ORDER': AI_PROVIDER_ORDER,
    'OPENAI_MODEL': config('AI_ASSISTANT_OPENAI_MODEL', default='gpt-4o-mini'),
    'ANTHROPIC_MODEL': config('AI_ASSISTANT_ANTHROPIC_MODEL', default='claude-3-5-sonnet-20241022'),
    'TEMPERATURE': config('AI_ASSISTANT_TEMPERATURE', default=0.2, cast=float),
    'MAX_OUTPUT_TOKENS': config('AI_ASSISTANT_MAX_TOKENS', default=900, cast=int),
}

# ==============================
# OTHER SETTINGS
# ==============================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Rate Limiting
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

# Monitor settings
ENABLE_METRICS = True

# Stripe (do not implement for this task)
STRIPE_ENABLED = False

# Booking/payment behavior
BOOKING_REQUIRE_PAYMENT = _env_bool('BOOKING_REQUIRE_PAYMENT', default=False)
