# home/views.py
from __future__ import annotations
from datetime import datetime, timezone
import logging
import os
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import F, Value, TextField, Q
from django.db.models.functions import Lower, Replace, Trim, Cast

from tenants.decorators import tenant_required
from tenants.models import Tenant, TenantUser

from inyeccion_api.models import Alarm
from soar_incidents.models import IncidenteSOAR
from .models import TelegramSolicitud, IPBlacklist, IPWhitelist

from dashboard.charts import make_base_qs
import requests

from django.conf import settings  # por si lo usas en otros lados
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse

logger = logging.getLogger(__name__)


def _normalize_string_local(s: str) -> str:
    if not s:
        return ""
    out = str(s).strip()
    for ch in ["{", "}", "[", "]", '"', "'", " "]:
        out = out.replace(ch, "")
    return out.lower()


def _normalize_tenant_aotag(tenant) -> str:
    raw = getattr(tenant, "alarms_one_id", "") or ""
    return _normalize_string_local(raw)


def _annotate_norm_field(qs, field_name: str, alias: str):
    """
    Anota un alias con el campo normalizado en minúsculas,
    sin comillas/espacios y casteado a texto.
    """
    cleaned = Cast(F(field_name), TextField())
    for ch in ["{", "}", "[", "]", '"', "'", " "]:
        cleaned = Replace(cleaned, Value(ch), Value(""), output_field=TextField())
    cleaned = Trim(cleaned, output_field=TextField())
    cleaned = Lower(cleaned, output_field=TextField())
    return qs.annotate(**{alias: cleaned})


def _get_user_telegram_id(user) -> str | None:
    # 1) atributo directo en el user (si existiera)
    val = getattr(user, "telegram_id", None)
    if val:
        return str(val).strip()

    # 2) relación con TenantUser
    try:
        tu = getattr(user, "tenantuser", None)
        if tu and getattr(tu, "telegram_id", None):
            return str(tu.telegram_id).strip()
    except Exception:
        pass

    try:
        tu = TenantUser.objects.filter(user=user).order_by("-id").first()
        if tu and getattr(tu, "telegram_id", None):
            return str(tu.telegram_id).strip()
    except Exception:
        pass

    return None


def _split_search_terms(raw: str) -> list[str]:
    """
    Recibe un string como '1.1.1.1, 2.2.2.2' y retorna ['1.1.1.1', '2.2.2.2'].
    Ignora vacíos.
    """
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


@login_required
@tenant_required
def home_index(request):
    tenant = getattr(request, "tenant", None)
    user = request.user

    # ===== AOTAG tenant =====
    norm_tid = _normalize_tenant_aotag(tenant) if tenant else ""

    # ===== Alarmas (total/critical) filtradas por tenant =====
    alarms_total = 0
    alarms_critical_total = 0
    if norm_tid:
        dt_from_utc = datetime(1970, 1, 1, tzinfo=timezone.utc)
        dt_to_utc_exclusive = datetime.now(tz=timezone.utc)
        try:
            qs_base = make_base_qs(dt_from_utc, dt_to_utc_exclusive)
            alarms_total = qs_base.count()
            alarms_critical_total = qs_base.filter(
                msg_severity__iexact="critical"
            ).count()
        except Exception:
            try:
                qs_fallback = _annotate_norm_field(
                    Alarm.objects.all(), "tags", "norm_aotag"
                )
                alarms_total = qs_fallback.filter(norm_aotag=norm_tid).count()
                alarms_critical_total = qs_fallback.filter(
                    norm_aotag=norm_tid,
                    msg_severity__iexact="critical",
                ).count()
            except Exception as e:
                logger.exception("[HOME] Error KPI Alarmas (fallback): %s", e)

    # ===== SOAR por tenant =====
    soar_total = 0
    if norm_tid:
        try:
            qs_soar = _annotate_norm_field(
                IncidenteSOAR.objects.all(), "aotag", "norm_aotag"
            )
            soar_total = qs_soar.filter(norm_aotag=norm_tid).count()
        except Exception as e:
            logger.exception("[HOME] Error KPI SOAR: %s", e)

    # ===== Telegram SOLO por telegram_id del usuario =====
    user_tid = _get_user_telegram_id(user)
    logger.debug(
        "[HOME] user=%s telegram_id(raw)=%r",
        getattr(user, "username", "?"),
        user_tid,
    )

    telegram_total = 0
    try:
        if user_tid:
            norm1 = _normalize_string_local(user_tid)
            norm_opts = {norm1}
            if norm1.startswith("@"):
                norm_opts.add(norm1[1:])
            logger.debug("[HOME] telegram norm_opts=%s", norm_opts)

            qs_tel = _annotate_norm_field(
                TelegramSolicitud.objects.all(), "chat_id", "norm_chat"
            )
            telegram_total = qs_tel.filter(norm_chat__in=list(norm_opts)).count()

        logger.debug("[HOME] telegram_total=%d", telegram_total)
    except Exception as e:
        logger.exception("[HOME] Error KPI Telegram: %s", e)

    # ===== Selector de tenant (si el usuario es de Inntesec) =====
    all_tenants = []
    user_tenant = getattr(user, "tenant", None)
    if user_tenant and str(user_tenant.name).lower() == "inntesec":
        all_tenants = Tenant.objects.all().order_by("name")

    # ===== Buscador IP Blacklist / Whitelist (múltiples IP separadas por coma) =====
    blacklist_q_raw = (request.GET.get("blacklist_q") or "").strip()
    whitelist_q_raw = (request.GET.get("whitelist_q") or "").strip()

    # IPs que el usuario ya marcó para eliminación / gestión (no deben mostrarse)
    blacklist_removed_raw = (request.GET.get("blacklist_removed") or "").strip()
    whitelist_removed_raw = (request.GET.get("whitelist_removed") or "").strip()

    blacklist_terms = _split_search_terms(blacklist_q_raw)
    whitelist_terms = _split_search_terms(whitelist_q_raw)
    blacklist_removed_terms = _split_search_terms(blacklist_removed_raw)
    whitelist_removed_terms = _split_search_terms(whitelist_removed_raw)

    logger.debug(
        "[HOME] Blacklist search raw=%r terms=%s removed_terms=%s",
        blacklist_q_raw,
        blacklist_terms,
        blacklist_removed_terms,
    )

    # Inicializamos resultados
    blacklist_results = IPBlacklist.objects.none()
    whitelist_results = IPWhitelist.objects.none()
    whitelist_not_found_terms: list[str] = []

    # === BLACKLIST: buscamos en agent.ip_blacklist ===
    if blacklist_terms:
        try:
            # Usamos icontains por si las IP están guardadas con sufijos, espacios, etc.
            q_obj = Q()
            for term in blacklist_terms:
                q_obj |= Q(ip__icontains=term)

            qs_bl = IPBlacklist.objects.filter(q_obj)

            # IPs que el usuario ya marcó como removidas (no se muestran)
            if blacklist_removed_terms:
                qs_bl = qs_bl.exclude(ip__in=blacklist_removed_terms)

            # Ahora sí podemos ordenar por fecha_actualizacion porque existe en el modelo
            qs_bl = qs_bl.order_by("ip", "-fecha_actualizacion")

            logger.debug(
                "[HOME] Blacklist found %d registros, IPs=%s",
                qs_bl.count(),
                list(qs_bl.values_list("ip", flat=True)),
            )

            blacklist_results = qs_bl
        except Exception as e:
            logger.exception("[HOME] Error búsqueda blacklist: %s", e)

    # === WHITELIST ===
    if whitelist_terms:
        try:
            qs_wl = IPWhitelist.objects.filter(ip__in=whitelist_terms)

            if whitelist_removed_terms:
                qs_wl = qs_wl.exclude(ip__in=whitelist_removed_terms)

            whitelist_results = qs_wl

            # Calcular las IPs buscadas que no están en whitelist
            existing_ips = list(qs_wl.values_list("ip", flat=True))
            whitelist_not_found_terms = [
                ip for ip in whitelist_terms if ip not in existing_ips
            ]
        except Exception as e:
            logger.exception("[HOME] Error búsqueda whitelist: %s", e)

    ctx = {
        "tenant": tenant,
        "all_tenants": all_tenants,
        "alarms_total": alarms_total,
        "alarms_critical_total": alarms_critical_total,
        "soar_total": soar_total,
        "telegram_total": telegram_total,
        "debug_user_telegram_id": user_tid or "",
        # 🔎 contexto para la modal de IP
        "blacklist_q": blacklist_q_raw,
        "blacklist_terms": blacklist_terms,
        "blacklist_removed": blacklist_removed_raw,
        "blacklist_removed_terms": blacklist_removed_terms,
        "blacklist_results": blacklist_results,
        "whitelist_q": whitelist_q_raw,
        "whitelist_terms": whitelist_terms,
        "whitelist_removed": whitelist_removed_raw,
        "whitelist_removed_terms": whitelist_removed_terms,
        "whitelist_results": whitelist_results,
        "whitelist_not_found_terms": whitelist_not_found_terms,
    }
    return render(request, "home/index.html", ctx)


@login_required
@tenant_required
def blacklist_create_ticket(request):
    """
    Envía un request real (GET) a un webhook para crear ticket de eliminación
    de una IP en blacklist.

    Además, va marcando las IP como "removidas" para no mostrarlas
    nuevamente en los resultados y cierra la modal cuando ya no
    queden IPs coincidentes en la tabla IPBlacklist.
    """
    if request.method != "POST":
        return HttpResponseRedirect(reverse("home:index"))

    ip_value = (request.POST.get("ip") or "").strip()
    if not ip_value:
        messages.error(request, "No se recibió una IP válida.")
        return HttpResponseRedirect(reverse("home:index"))

    # Búsqueda original: puede contener varias IP separadas por coma
    blacklist_q_original = (request.POST.get("blacklist_q_original") or "").strip()
    # IPs ya removidas hasta este momento (en requests anteriores)
    blacklist_removed_original = (
        (request.POST.get("blacklist_removed_original") or "").strip()
    )

    # Convertimos a listas
    original_terms = _split_search_terms(blacklist_q_original)
    removed_terms = _split_search_terms(blacklist_removed_original)

    user = request.user

    # Buscar el TenantUser para obtener id_usuario desde la tabla tenants_tenantuser
    try:
        tenant_user = TenantUser.objects.filter(user=user).first()
    except Exception:
        tenant_user = None

    id_usuario = str(tenant_user.id if tenant_user else user.id)
    nombre_usuario = user.get_full_name() or user.username

    # Leer URL y PASSKEY desde variables de entorno
    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    passkey = os.getenv("PASSKEY", "").strip()

    if not webhook_url or not passkey:
        logger.error("[BLACKLIST] Webhook no configurado (URL o PASSKEY faltantes)")
        messages.error(
            request,
            "No se pudo enviar la solicitud. Webhook no está configurado.",
        )
        # Volvemos manteniendo el estado que venía (sin marcar nada nuevo como removido)
        params = {}
        if blacklist_q_original:
            params["blacklist_q"] = blacklist_q_original
        if blacklist_removed_original:
            params["blacklist_removed"] = blacklist_removed_original

        redirect_url = reverse("home:index")
        if params:
            redirect_url += "?" + urlencode(params)
        return HttpResponseRedirect(redirect_url)

    # Headers con passkey
    headers = {
        "passkey": passkey,
    }

    # Parámetros para el GET (query string) — AHORA CON type=blacklist
    params_webhook = {
        "value": "crear_ticket",
        "ip": ip_value,
        "id_usuario": id_usuario,
        "nombre_usuario": nombre_usuario,
        "type": "blacklist",
    }

    # ===== Llamada real al webhook (GET) =====
    try:
        logger.info(
            "[BLACKLIST] Enviando GET al webhook %s con headers=%s, params=%s",
            webhook_url,
            headers,
            params_webhook,
        )
        resp = requests.get(
            webhook_url,
            headers=headers,
            params=params_webhook,
            timeout=10,
        )

        if resp.status_code >= 400:
            logger.error(
                "[BLACKLIST] Webhook respondió error %s. Body: %s",
                resp.status_code,
                resp.text,
            )
            resp.raise_for_status()

        # Solo si el webhook responde OK, marcamos la IP como "removida"
        if ip_value not in removed_terms:
            removed_terms.append(ip_value)

        messages.success(
            request,
            f"Se envió la solicitud para eliminar la IP {ip_value} de la blacklist.",
        )
    except Exception as e:
        logger.exception("[BLACKLIST] Error llamando al webhook: %s", e)
        messages.error(
            request,
            "Ocurrió un error al enviar la solicitud al sistema de tickets.",
        )
        # En caso de error, NO agregamos la IP a removed_terms

    # ===== ¿Quedan IPs por mostrar? =====
    all_removed = False
    if original_terms:
        try:
            existing_ips = list(
                IPBlacklist.objects.filter(ip__in=original_terms).values_list(
                    "ip", flat=True
                )
            )
            if existing_ips:
                all_removed = set(existing_ips).issubset(set(removed_terms))
        except Exception as e:
            logger.exception("[BLACKLIST] Error comprobando IPs restantes: %s", e)

    if all_removed:
        return HttpResponseRedirect(reverse("home:index"))

    # ===== Redirección con estado =====
    params = {}
    if blacklist_q_original:
        params["blacklist_q"] = blacklist_q_original
    if removed_terms:
        params["blacklist_removed"] = ", ".join(removed_terms)

    redirect_url = reverse("home:index")
    if params:
        redirect_url += "?" + urlencode(params)

    return HttpResponseRedirect(redirect_url)


@login_required
@tenant_required
def whitelist_create_ticket(request):
    """
    Envía un request real (GET) a un webhook para crear ticket
    relacionado con una IP en whitelist.

    Misma lógica que blacklist_create_ticket, pero con destino whitelist.
    """
    if request.method != "POST":
        return HttpResponseRedirect(reverse("home:index"))

    ip_value = (request.POST.get("ip") or "").strip()
    if not ip_value:
        messages.error(request, "No se recibió una IP válida.")
        return HttpResponseRedirect(reverse("home:index"))

    # Búsqueda original: puede contener varias IP separadas por coma
    whitelist_q_original = (request.POST.get("whitelist_q_original") or "").strip()
    # IPs ya gestionadas hasta este momento (en requests anteriores)
    whitelist_removed_original = (
        (request.POST.get("whitelist_removed_original") or "").strip()
    )

    # Convertimos a listas
    original_terms = _split_search_terms(whitelist_q_original)
    removed_terms = _split_search_terms(whitelist_removed_original)

    user = request.user

    # Buscar el TenantUser para obtener id_usuario desde la tabla tenants_tenantuser
    try:
        tenant_user = TenantUser.objects.filter(user=user).first()
    except Exception:
        tenant_user = None

    id_usuario = str(tenant_user.id if tenant_user else user.id)
    nombre_usuario = user.get_full_name() or user.username

    # Leer URL y PASSKEY desde variables de entorno (WHITELIST)
    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    passkey = os.getenv("PASSKEY", "").strip()

    if not webhook_url or not passkey:
        logger.error("[WHITELIST] Webhook no configurado (URL o PASSKEY faltantes)")
        messages.error(
            request,
            "No se pudo enviar la solicitud de whitelist. Webhook no está configurado.",
        )
        params = {}
        if whitelist_q_original:
            params["whitelist_q"] = whitelist_q_original
        if whitelist_removed_original:
            params["whitelist_removed"] = whitelist_removed_original

        redirect_url = reverse("home:index")
        if params:
            redirect_url += "?" + urlencode(params)
        return HttpResponseRedirect(redirect_url)

    # Headers con passkey
    headers = {
        "passkey": passkey,
    }

    # Parámetros para el GET (query string) — con type=whitelist
    params_webhook = {
        "value": "crear_ticket",
        "ip": ip_value,
        "id_usuario": id_usuario,
        "nombre_usuario": nombre_usuario,
        "type": "whitelist",
    }

    # ===== Llamada real al webhook (GET) =====
    try:
        logger.info(
            "[WHITELIST] Enviando GET al webhook %s con headers=%s, params=%s",
            webhook_url,
            headers,
            params_webhook,
        )
        # ⬇⬇ timeout aumentado a 30 segundos
        resp = requests.get(
            webhook_url,
            headers=headers,
            params=params_webhook,
            timeout=30,
        )

        if resp.status_code >= 400:
            logger.error(
                "[WHITELIST] Webhook respondió error %s. Body: %s",
                resp.status_code,
                resp.text,
            )
            resp.raise_for_status()

        # Solo si el webhook responde OK, marcamos la IP como "removida"
        if ip_value not in removed_terms:
            removed_terms.append(ip_value)

    except requests.exceptions.ReadTimeout:
        # Timeout específico
        logger.error(
            "[WHITELIST] Timeout esperando respuesta del webhook (%s).",
            webhook_url,
        )
        # OJO: no añadimos la IP a removed_terms porque no sabemos si se procesó

    except Exception as e:
        logger.exception("[WHITELIST] Error llamando al webhook: %s", e)
        # Tampoco añadimos la IP a removed_terms en este caso

    # ===== ¿Quedan IPs por mostrar? =====
    all_removed = False
    if original_terms:
        try:
            existing_ips = list(
                IPWhitelist.objects.filter(ip__in=original_terms).values_list(
                    "ip", flat=True
                )
            )
            if existing_ips:
                all_removed = set(existing_ips).issubset(set(removed_terms))
        except Exception as e:
            logger.exception("[WHITELIST] Error comprobando IPs restantes: %s", e)

    if all_removed:
        return HttpResponseRedirect(reverse("home:index"))

    # ===== Redirección con estado =====
    params = {}
    if whitelist_q_original:
        params["whitelist_q"] = whitelist_q_original
    if removed_terms:
        params["whitelist_removed"] = ", ".join(removed_terms)

    redirect_url = reverse("home:index")
    if params:
        redirect_url += "?" + urlencode(params)

    return HttpResponseRedirect(redirect_url)
