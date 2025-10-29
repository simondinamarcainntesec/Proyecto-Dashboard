from django.shortcuts import render
from .models import IaSoar

def dashboard_soar(request):
    # Para cross-filter en el front, embebemos filas crudas mínimas.
    # Ajusta el límite según tu volumen (puedes paginar o agregar filtros server-side después).
    rows = list(
        IaSoar.objects.values("severity", "srccountry", "security_action")[:10000]
    )
    ctx = {
        "tenant": getattr(request, "tenant", None),
        "events": rows,  # se leerá con json_script en el template
    }
    return render(request, "soar_dashboard/dashboardsoar.html", ctx)
