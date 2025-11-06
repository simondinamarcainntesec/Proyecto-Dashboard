"""
WSGI config for mysite project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

application = get_wsgi_application()

import sys
import logging

# 🔧 Redirigir stdout y stderr a error.log de Apache
sys.stdout = sys.stderr
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
