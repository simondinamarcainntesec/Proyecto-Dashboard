from django.shortcuts import render
from .charts import (
    build_trend_data,
    build_donut_data,
    build_device_bar_data,
    build_action_bar_data,
    build_kpis,
)

def dashboard_view(request):
    trend_info = build_trend_data()
    severity_counts = build_donut_data()
    device_counts = build_device_bar_data()
    action_counts = build_action_bar_data()
    kpis = build_kpis()

    context = {
        **trend_info,
        "severity_counts": severity_counts,
        "device_counts": device_counts,
        "action_counts": action_counts,
        **kpis,
    }

    return render(request, "dashboard/dashboard.html", context)
