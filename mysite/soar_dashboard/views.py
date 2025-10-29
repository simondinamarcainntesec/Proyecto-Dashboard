# soar_dashboard/views.py
from __future__ import annotations

import logging
from typing import Iterable

from django.contrib.auth.decorators import login_required
from django.db.models import F, Value, TextField
from django.db.models.functions import Lower, Replace, Trim, Cast
from django.shortcuts import render
from tenants.decorators import tenant_required

from .models import IaSoar

logger = logging.getLogger(__name__)


# ----------------------------
# Helpers de normalización
# ----------------------------
def _normalize_string_local(s: str) -> str:
    """
    Limpia llaves/corchetes/comillas/espacios y pasa a lower.
    Ej: '{9596000000007083}' -> '9596000000007083'
    """
    if not s:
        return ""
    out = str(s).strip()
    for ch in ['{', '}', '[', ']', '"', "'", " "]:
        out = out.replace(ch, "")
    return out.lower()


def _normalize_tenant_aotag(tenant) -> str:
    """
    Obtiene y normaliza tenant.alarms_one_id para comparación.
    """
    raw = getattr(tenant, "alarms_one_id", "") or ""
    return _normalize_string_local(raw)


def _annotate_norm_aotag(qs):
    """
    Anota norm_aotag a nivel BD con todos los Replace/Trim/Lower necesarios.
    IMPORTANTE: en CADA paso seteamos output_field=TextField para evitar
    el FieldError de tipos mezclados.
    """
    # Partimos casteando a TextField explícitamente
    cleaned = Cast(F("aotag"), TextField())

    # Reemplazos en cadena, SIEMPRE con output_field=TextField()
    cleaned = Replace(cleaned, Value("{"), Value(""), output_field=TextField())
    cleaned = Replace(cleaned, Value("}"), Value(""), output_field=TextField())
    cleaned = Replace(cleaned, Value("["), Value(""), output_field=TextField())
    cleaned = Replace(cleaned, Value("]"), Value(""), output_field=TextField())
    cleaned = Replace(cleaned, Value('"'), Value(""), output_field=TextField())
    cleaned = Replace(cleaned, Value("'"), Value(""), output_field=TextField())
    cleaned = Replace(cleaned, Value(" "), Value(""), output_field=TextField())

    # Trim + lower (también con output_field)
    cleaned = Trim(cleaned, output_field=TextField())
    cleaned = Lower(cleaned, output_field=TextField())

    return qs.annotate(norm_aotag=cleaned)


# ----------------------------
# Vista principal del SOAR
# ----------------------------
@login_required
@tenant_required
def dashboard_soar(request):
    """
    Renderiza el panel SOAR con JSON embebido, filtrando por tenant:
    - Compara IaSoar.aotag (normalizado) con tenant.alarms_one_id (normalizado).
    - Si no hay tenant o no hay match, devuelve events=[].
    """
    tenant = getattr(request, "tenant", None)
    norm_tid = _normalize_tenant_aotag(tenant) if tenant else ""

    logger.info("[SOAR] Entrando a dashboard_soar | tenant=%s | alarms_one_id(raw)=%s | alarms_one_id(norm)=%s",
                getattr(tenant, "name", None),
                getattr(tenant, "alarms_one_id", None),
                norm_tid)

    rows: Iterable[dict] = []

    try:
        qs = IaSoar.objects.all()

        # Si hay tenant, aplicamos filtro por aotag normalizado
        if norm_tid:
            qs = _annotate_norm_aotag(qs).filter(norm_aotag=norm_tid)
        else:
            # Sin tenant (o sin alarms_one_id) => sin datos
            logger.warning("[SOAR] request sin tenant o sin alarms_one_id -> devolviendo 0 filas")
            qs = qs.none()

        # Trae solo los campos que usa el front (ajusta si agregas más charts)
        rows = list(
            qs.values(
                "date", "time",
                "device", "service", "proto",
                "srccountry",
                "severity",
                "security_action",  # principal en este dashboard
                "action",           # fallback si llega vacío
            )[:20000]
        )

    except Exception as e:
        logger.exception("[SOAR] Error consultando IaSoar: %s", e)
        rows = []

    logger.info("[SOAR] Filas post-filtro=%d (tenant=%s)", len(rows), getattr(tenant, "name", None))

    ctx = {
        "tenant": tenant,
        "events": rows,  # el front lo lee con json_script('soar-events')
    }
    return render(request, "soar_dashboard/dashboardsoar.html", ctx)
