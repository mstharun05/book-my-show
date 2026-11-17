#!/usr/bin/env bash
set -o errexit
python manage.py migrate --noinput
python manage.py bootstrap_deployment
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers 2 --timeout 120 --access-logfile -
