"""
Este módulo ya no crea una nueva instancia de Celery.
Se mantiene para compatibilidad con importaciones existentes que esperan
`integrations.celery_app.app`. Ahora reexporta la app principal definida
en `mysite.celery`.
"""
from mysite.celery import app

__all__ = ("app",)
