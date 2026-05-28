#!/bin/sh
set -e

# Run migrations and collectstatic, then start Gunicorn
python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
