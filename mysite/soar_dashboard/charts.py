# soar_dashboard/charts.py
from django.db.models import Count, Value, TextField
from django.db.models.functions import Coalesce
from .models import IaSoar

# Usar TextField para que coincida con tus columnas (todas son texto)
NULL_TXT = Value("N/A", output_field=TextField())


def build_top_srccountry(limit=10):
    qs = (
        IaSoar.objects
        .annotate(k=Coalesce("srccountry", NULL_TXT, output_field=TextField()))
        .values("k")
        .annotate(total=Count("*"))
        .order_by("-total")[:limit]
    )
    return {
        "labels": [r["k"] for r in qs],
        "data":   [r["total"] for r in qs],
        "title":  "Top países origen (srccountry)",
    }


def build_severity():
    qs = (
        IaSoar.objects
        .annotate(k=Coalesce("severity", NULL_TXT, output_field=TextField()))
        .values("k")
        .annotate(total=Count("*"))
        .order_by("-total")
    )
    return {
        "labels": [r["k"] for r in qs],
        "data":   [r["total"] for r in qs],
        "title":  "Severidad",
    }


def build_security_action():
    qs = (
        IaSoar.objects
        .annotate(k=Coalesce("security_action", NULL_TXT, output_field=TextField()))
        .values("k")
        .annotate(total=Count("*"))
        .order_by("-total")
    )
    return {
        "labels": [r["k"] for r in qs],
        "data":   [r["total"] for r in qs],
        "title":  "Acción de seguridad",
    }
