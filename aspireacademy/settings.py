"""Django settings for aspireacademy project.

This file defaults to safe development values but reads production
secrets and flags from environment variables so the project can run
securely in production.
"""
from pathlib import Path
import os
import secrets
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# DEBUG should be disabled in production. Set DJANGO_DEBUG=True in env to enable.
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'


def _split_env_list(value):
    return [item.strip() for item in value.split(',') if item.strip()]

# Secrets and environment-driven settings
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = 'smkwesha' if DEBUG else None
    if SECRET_KEY is None:
        raise ImproperlyConfigured('The DJANGO_SECRET_KEY environment variable must be set in production.')

# Allow hosts configured via environment (comma-separated), with sensible defaults.
ALLOWED_HOSTS = _split_env_list(
    os.environ.get(
        'ALLOWED_HOSTS',
        '127.0.0.1,localhost,aspire-portal.onrender.com,aspireacademy.co.zw,www.aspireacademy.co.zw',
    )
)

CSRF_TRUSTED_ORIGINS = _split_env_list(
    os.environ.get(
        'CSRF_TRUSTED_ORIGINS',
        'https://aspire-portal.onrender.com,https://aspireacademy.co.zw,https://www.aspireacademy.co.zw',
    )
)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # local apps
    'apps.accounts',
    'apps.students',
    'apps.teachers',
    'apps.assignments',
    'apps.grades',
    'apps.notifications',
    'apps.calendarapp',
    'apps.news',
    'apps.finance',
    'apps.reports',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'aspireacademy.urls'

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
                'apps.news.context_processors.homepage_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'aspireacademy.wsgi.application'

# Render Persistent Disk mount point. Data stored under /data survives redeploys,
# unlike the ephemeral application filesystem.
PERSISTENT_ROOT = Path('/data')

# Database
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DATABASE_ENGINE', 'django.db.backends.sqlite3'),
        # Default SQLite location on Render Persistent Disk to prevent data loss.
        'NAME': os.environ.get('DATABASE_NAME', PERSISTENT_ROOT / 'db.sqlite3'),
    }
}

# Allow DATABASE_URL style environment via dj-database-url if available
try:
    import dj_database_url
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        DATABASES['default'] = dj_database_url.parse(database_url, conn_max_age=600)
except Exception:
    pass

# Password validation
AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:accounts_home'

MEDIA_URL = '/media/'
# User-uploaded files must be persisted across deploys, so store media on
# the Render Persistent Disk.
MEDIA_ROOT = PERSISTENT_ROOT / 'media'

# Security settings recommended for production
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get(
        'DJANGO_SECURE_SSL_REDIRECT',
        os.environ.get('SECURE_SSL_REDIRECT', 'True')
    ) == 'True'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', 3600))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'True') == 'True'
    SECURE_HSTS_PRELOAD = os.environ.get('SECURE_HSTS_PRELOAD', 'True') == 'True'
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'

# Email configuration
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@aspireacademy.local')
EMAIL_BACKEND = os.environ.get(
    'DJANGO_EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

# Celery configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'True' if DEBUG else 'False') == 'True'
CELERY_TASK_EAGER_PROPAGATES = True

# Basic logging configuration (expand as needed for production)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '%(levelname)s %(asctime)s %(module)s %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['console'], 'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO')},
}

# ============================================================================
# Cache Configuration - 5-minute TTL for dashboards
# ============================================================================
CACHES = {
    'default': {
        'BACKEND': os.environ.get('CACHE_BACKEND', 'django.core.cache.backends.locmem.LocMemCache'),
        'LOCATION': os.environ.get('CACHE_LOCATION', 'aspire-cache'),
        'TIMEOUT': int(os.environ.get('CACHE_TIMEOUT', '300')),  # 5 minutes
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}

# For production, use Redis:
# CACHES = {
#     'default': {
#         'BACKEND': 'django.core.cache.backends.redis.RedisCache',
#         'LOCATION': 'redis://127.0.0.1:6379/1',
#         'TIMEOUT': 300,
#     }
# }

# ============================================================================
# Celery Beat Scheduled Tasks
# ============================================================================
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Financial Tasks
    'recalculate-financial-status': {
        'task': 'apps.finance.tasks.recalculate_financial_status',
        'schedule': 4.0 * 3600,  # Every 4 hours
    },
    'check-overdue-accounts': {
        'task': 'apps.finance.tasks.check_overdue_accounts',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    'generate-monthly-financial-reports': {
        'task': 'apps.finance.tasks.generate_monthly_financial_reports',
        'schedule': crontab(day_of_month=1, hour=0, minute=0),  # Month-end (1st of next month at midnight)
    },
    'refresh-dashboard-cache': {
        'task': 'apps.finance.tasks.refresh_dashboard_cache',
        'schedule': 5.0 * 60,  # Every 5 minutes
    },
    'audit-financial-consistency': {
        'task': 'apps.finance.tasks.audit_financial_consistency',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    # Academic Tasks
    'calculate-class-performance': {
        'task': 'apps.grades.tasks.calculate_class_performance',
        'schedule': crontab(hour=23, minute=0),  # Daily at 11 PM
    },
    'identify-at-risk-students': {
        'task': 'apps.grades.tasks.identify_at_risk_students',
        'schedule': crontab(day_of_week=0, hour=8, minute=0),  # Weekly Monday at 8 AM
    },
    'recognize-high-achievers': {
        'task': 'apps.grades.tasks.recognize_high_achievers',
        'schedule': crontab(day_of_week=4, hour=10, minute=0),  # Weekly Friday at 10 AM
    },
    'generate-term-performance-reports': {
        'task': 'apps.grades.tasks.generate_term_performance_reports',
        'schedule': crontab(day_of_month=1, hour=1, minute=0),  # Month-end at 1 AM
    },
    'notify-exam-approaching': {
        'task': 'apps.grades.tasks.notify_exam_approaching',
        'schedule': crontab(hour=7, minute=0),  # Daily at 7 AM
    },
}
