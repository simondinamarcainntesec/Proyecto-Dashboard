from __future__ import absolute_import, unicode_literals
from .celery import app as celery_app

# Also expose the app as 'celery' so `celery -A mysite` can auto-discover it.
from .celery import app as celery

__all__ = ('celery_app', 'celery')
