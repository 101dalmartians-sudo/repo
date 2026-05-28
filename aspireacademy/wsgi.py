"""WSGI config for aspireacademy project."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aspireacademy.settings')

application = get_wsgi_application()
