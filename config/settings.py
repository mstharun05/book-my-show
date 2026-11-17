
import os
import json
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Optional ignored local configuration; environment variables always win.
local_delivery_path = BASE_DIR / 'delivery.local.json'
local_delivery = {}
if local_delivery_path.exists():
    local_delivery = json.loads(local_delivery_path.read_text(encoding='utf-8'))
    for key in ('EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD',
                'DEFAULT_FROM_EMAIL', 'EMAIL_USE_TLS', 'EMAIL_USE_SSL'):
        if key in local_delivery:
            os.environ.setdefault(key, str(local_delivery[key]))

# Security
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-local-development-only-change-me"
)

DEBUG = os.environ.get("DEBUG", "False") == "True"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost,.onrender.com"
    ).split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CSRF_TRUSTED_ORIGINS",
        ""
    ).split(",")
    if origin.strip()
]

RENDER_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append('https://' + RENDER_HOSTNAME)
if os.environ.get('RENDER') and not os.environ.get('SECRET_KEY'):
    raise RuntimeError('Set SECRET_KEY before deploying.')
SECURE_SSL_REDIRECT = bool(os.environ.get('RENDER')) and not DEBUG
SECURE_HSTS_SECONDS = 3600 if os.environ.get('RENDER') else 0

# Applications
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "movies",
    "discovery",
    "bookings",
    "payments",
    "dashboard",
    "tickets",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"

USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}

# Uploaded media
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Django defaults
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "/movies/"
LOGOUT_REDIRECT_URL = "/movies/"

# Razorpay
# Environment variables take precedence over the ignored local development file.
razorpay_local_path = BASE_DIR / "razorpay.local.json"
razorpay_local = {}
if razorpay_local_path.exists():
    razorpay_local = json.loads(razorpay_local_path.read_text(encoding="utf-8"))
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", razorpay_local.get("RAZORPAY_KEY_ID", ""))
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", razorpay_local.get("RAZORPAY_KEY_SECRET", ""))

# Security for production
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https"
)

RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", razorpay_local.get("RAZORPAY_WEBHOOK_SECRET", ""))

SITE_URL = os.environ.get('SITE_URL', 'https://' + RENDER_HOSTNAME if RENDER_HOSTNAME else 'http://127.0.0.1:8002').rstrip('/')
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', local_delivery.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0'))
if CELERY_BROKER_URL == 'local-sqlite':
    (BASE_DIR / 'tmp').mkdir(exist_ok=True)
    CELERY_BROKER_URL = 'sqla+sqlite:///' + (BASE_DIR / 'tmp' / 'celery-queue.sqlite3').as_posix()
    CELERY_WORKER_ENABLE_REMOTE_CONTROL = False
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULE = {
    'pending-ticket-deliveries': {'task': 'tickets.tasks.dispatch_pending', 'schedule': 15.0},
}
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False') == 'True'
EMAIL_TIMEOUT = 30
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'tickets@localhost')

# Record application exceptions in Render's service logs even with DEBUG=False.
# Response bodies remain generic; do not log request headers or form data.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
        'django.security': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
    },
}
