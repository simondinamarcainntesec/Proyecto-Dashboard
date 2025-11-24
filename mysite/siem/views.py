# siem/views.py
from django.shortcuts import render
from .log360_service import obtener_alertas_logs360


def alerts_logs360_view(request):
    """
    Muestra las alertas de Log360 para las últimas ~48 h
    (ayer 00:00 UTC → hoy 23:59:59 UTC) en una tabla.
    """
    query = request.GET.get("q", "")
    alerts, error, start_time, end_time = obtener_alertas_logs360(query=query)

    context = {
        "alerts": alerts,
        "error": error,
        "query": query,
        "start_time": start_time,
        "end_time": end_time,
    }
    return render(request, "siem/alerts_list.html", context)
