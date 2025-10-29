from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required(login_url='/login/')
def home(request):
    dashboards = [
        {
            "title": "Dashboard AlarmsOne",
            "description": "Visualiza las alarmas, dispositivos y métricas críticas integradas desde ManageEngine AlarmsOne, con indicadores de severidad, acciones y tendencias por dispositivo.",
            "url": "/dashboard/alarmsone/"
        },
        {
            "title": "Dashboard SOAR",
            "description": "Analiza y automatiza la gestión de incidentes de seguridad mediante Inntesec Agent IA, con visualizaciones SOAR que integran correlación de alertas, flujos de respuesta inteligente y métricas de rendimiento operacional.",
            "url": "/dashboard-soar/dashboard/"
        },
        {
            "title": "Dashboard de Reportes y Análisis",
            "description": "Genera reportes de alarmas, tráfico y rendimiento de políticas de seguridad, con comparativas históricas y filtros dinámicos.",
            "url": "/dashboard/finanzas/"
        },
    ]
    return render(request, "home/home.html", {"dashboards": dashboards})
