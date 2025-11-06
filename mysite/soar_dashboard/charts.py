from django.db.models import Count, Value, TextField
from django.db.models.functions import Coalesce, Substr
from .models import IaSoar

NULL_TXT = Value("N/A", output_field=TextField())

def build_top_srccountry(limit=10):
    qs = (
        IaSoar.objects
        .annotate(k=Coalesce("srccountry", NULL_TXT, output_field=TextField()))
        .values("k")
        .annotate(total=Count("*"))
        .order_by("-total")[:limit]
    )
    return {"labels":[r["k"] for r in qs], "data":[r["total"] for r in qs], "title":"Top países origen (srccountry)"}

def build_severity():
    qs = (
        IaSoar.objects
        .annotate(k=Coalesce("severity", NULL_TXT, output_field=TextField()))
        .values("k")
        .annotate(total=Count("*"))
        .order_by("-total")
    )
    return {"labels":[r["k"] for r in qs], "data":[r["total"] for r in qs], "title":"Severidad"}

def build_security_action():
    qs = (
        IaSoar.objects
        .annotate(k=Coalesce("security_action", Coalesce("action", NULL_TXT, output_field=TextField()), output_field=TextField()))
        .values("k")
        .annotate(total=Count("*"))
        .order_by("-total")
    )
    return {"labels":[r["k"] for r in qs], "data":[r["total"] for r in qs], "title":"Acción de seguridad"}

# Extras opcionales si luego quieres server-side para estos:
def build_top_devices(limit=10):
    qs = (IaSoar.objects.annotate(k=Coalesce("device", NULL_TXT)).values("k").annotate(total=Count("*")).order_by("-total")[:limit])
    return {"labels":[r["k"] for r in qs], "data":[r["total"] for r in qs]}

def build_top_services(limit=10):
    qs = (IaSoar.objects.annotate(k=Coalesce("service", NULL_TXT)).values("k").annotate(total=Count("*")).order_by("-total")[:limit])
    return {"labels":[r["k"] for r in qs], "data":[r["total"] for r in qs]}

def build_top_proto(limit=10):
    qs = (IaSoar.objects.annotate(k=Coalesce("proto", NULL_TXT)).values("k").annotate(total=Count("*")).order_by("-total")[:limit])
    return {"labels":[r["k"] for r in qs], "data":[r["total"] for r in qs]}

def build_trend_by_date():
    qs = (IaSoar.objects.annotate(k=Coalesce("date", NULL_TXT)).values("k").annotate(total=Count("*")).order_by("k"))
    return {"labels":[r["k"] for r in qs], "data":[r["total"] for r in qs]}

def build_trend_by_hour():
    # time formato "HH:MM:SS" → HH con Substr
    qs = (
        IaSoar.objects
        .annotate(hh=Substr(Coalesce("time", Value("", output_field=TextField())), 1, 2))
        .values("hh")
        .annotate(total=Count("*"))
        .order_by("hh")
    )
    labels = [f"{(x or '00'):>02}:00" for x in [r["hh"] for r in qs]]
    data   = [r["total"] for r in qs]
    return {"labels": labels, "data": data}
