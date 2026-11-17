"""Settings for a local Celery worker connected to the deployed database only."""
from .settings import *  # noqa: F403
import json
from urllib.parse import urlsplit
import dj_database_url

private_path = BASE_DIR / 'tmp' / 'live-worker.json'
private = json.loads(private_path.read_text(encoding='utf-8'))
db_url = private['DATABASE_URL']
if urlsplit(db_url).scheme not in ('postgres', 'postgresql'):
    raise RuntimeError('The live worker requires the external PostgreSQL URL.')
DATABASES = {'default': dj_database_url.parse(db_url, conn_max_age=0, ssl_require=True)}
DATABASES['default']['OPTIONS']['connect_timeout'] = 15
SECRET_KEY = private['SECRET_KEY']
SITE_URL = private['SITE_URL'].rstrip('/')
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = private['EMAIL_HOST_USER']
EMAIL_HOST_PASSWORD = private['EMAIL_HOST_PASSWORD']
DEFAULT_FROM_EMAIL = f'Book My Show <{EMAIL_HOST_USER}>'
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_TIMEOUT = 30
CELERY_BROKER_URL = 'sqla+sqlite:///' + (BASE_DIR / 'tmp' / 'live-celery-queue.sqlite3').as_posix()
CELERY_WORKER_ENABLE_REMOTE_CONTROL = False
