import json
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from tenants.decorators import tenant_required, service_required
from tenants.models import TenantUser  
from .models import SoarTicket
from .utils import get_active_tenant
from tenants.models import Tenant
from django.db import IntegrityError, transaction
import logging
from utils.ms_email import enviar_correo_ticket_asignado, enviar_correo_ticket_cerrado


logger = logging.getLogger(__name__)

def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return {}


@login_required
@tenant_required
@service_required("alarms_one_id")
def api_tenant_users(request):
    """
    Devuelve usuarios del tenant ACTIVO (según sesión tenant_id si es Inntesec).
    Ignora tenant_id del front por seguridad.
    """
    if not _is_ajax(request):
        return HttpResponseBadRequest("Bad request")

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({"users": []})

    qs = (
        TenantUser.objects
        .filter(tenant_id=tenant.id, is_active=True)
        .only("id", "username", "first_name", "last_name", "email")
        .order_by("first_name", "last_name", "username")
    )

    users = []
    for u in qs:
        full_name = (f"{u.first_name} {u.last_name}").strip()
        users.append({
            "id": u.id,
            "username": u.username,
            "full_name": full_name or u.username,
            "email": u.email or "",
        })

    return JsonResponse({"users": users})



@require_POST
@login_required
@tenant_required
@service_required("alarms_one_id")
def api_ticket_create(request):
    """
    Crea ticket en agent.soar_ticket (estado OPEN).
    Si ya existe ticket para ese evento (alarm_id) en el tenant activo => 409 + code ALREADY_EXISTS.
    Además exige initial_notes y envía correo al usuario asignado.
    """
    if not _is_ajax(request):
        return HttpResponseBadRequest("Bad request")

    tenant = get_active_tenant(request)
    if not tenant:
        return JsonResponse({"ok": False, "error": "No tenant activo"}, status=400)

    data = _json_body(request)

    alarm_id = (data.get("alarm_id") or "").strip()
    assigned_to_id = data.get("assigned_to")
    due_date_str = (data.get("due_date") or "").strip()

    # ✅ comentario inicial obligatorio (server-side)
    initial_notes = (data.get("initial_notes") or "").strip()
    if not initial_notes:
        return JsonResponse({
            "ok": False,
            "code": "INITIAL_NOTES_REQUIRED",
            "error": "Debes ingresar un comentario u observación inicial para crear el ticket.",
        }, status=400)

    if not alarm_id:
        return JsonResponse({"ok": False, "error": "alarm_id requerido"}, status=400)

    existing = (
        SoarTicket.objects
        .filter(tenant_id=tenant.id, alarm_id=alarm_id)
        .only("id", "status")
        .first()
    )
    if existing:
        return JsonResponse({
            "ok": False,
            "code": "ALREADY_EXISTS",
            "error": "Este evento ya cuenta con un ticket asignado",
            "ticket_id": existing.id,
            "ticket_status": existing.status,
        }, status=409)

    if not assigned_to_id:
        return JsonResponse({"ok": False, "error": "assigned_to requerido"}, status=400)

    if not due_date_str:
        return JsonResponse({"ok": False, "error": "due_date requerido"}, status=400)

    try:
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    except Exception:
        return JsonResponse({"ok": False, "error": "due_date inválido (YYYY-MM-DD)"}, status=400)

    assigned_user = (
        TenantUser.objects
        .filter(id=assigned_to_id, tenant_id=tenant.id, is_active=True)
        .first()
    )
    if not assigned_user:
        return JsonResponse({"ok": False, "error": "Usuario no pertenece al tenant activo"}, status=400)

    try:
        ticket = SoarTicket.objects.create(
            tenant_id=tenant.id,
            alarm_id=alarm_id,

            dispositivo=(data.get("dispositivo") or "").strip(),
            tipo_de_amenaza=(data.get("tipo_de_amenaza") or "").strip(),
            nivel_de_severidad=(data.get("nivel_de_severidad") or "").strip(),

            event_date=(datetime.strptime(data["event_date"], "%Y-%m-%d").date()
                        if data.get("event_date") else None),
            event_time=(datetime.strptime(data["event_time"], "%H:%M:%S").time()
                        if data.get("event_time") else None),

            descripcion_incidente=(data.get("descripcion_incidente") or "").strip(),
            analisis_criticidad=(data.get("analisis_criticidad") or "").strip(),
            medidas_correctivas=(data.get("medidas_correctivas") or "").strip(),
            resumen_humano=(data.get("resumen_humano") or "").strip(),
            riesgo_detectado=(data.get("riesgo_detectado") or "").strip(),
            application=(data.get("application") or "").strip(),

            assigned_to=assigned_user,
            created_by=request.user,
            due_date=due_date,
            status=SoarTicket.STATUS_OPEN,

            # ✅ obligatorio (ya validado arriba)
            initial_notes=initial_notes,
        )

        assigned_email = (getattr(assigned_user, "email", "") or "").strip()

        def _send_mail_after_commit():
          if not assigned_email:
              logger.warning(
                  "[SOAR_TICKETS] Ticket %s creado, pero usuario %s no tiene email. No se envía correo.",
                  ticket.id, assigned_user.id
              )
              return
          try:
              enviar_correo_ticket_asignado(ticket)
          except Exception as e:
              logger.exception("[SOAR_TICKETS] Error enviando correo ticket=%s: %s", ticket.id, e)

        transaction.on_commit(_send_mail_after_commit)

    except IntegrityError:
        existing = (
            SoarTicket.objects
            .filter(tenant_id=tenant.id, alarm_id=alarm_id)
            .only("id", "status")
            .first()
        )
        return JsonResponse({
            "ok": False,
            "code": "ALREADY_EXISTS",
            "error": "Este evento ya cuenta con un ticket asignado",
            "ticket_id": getattr(existing, "id", None),
            "ticket_status": getattr(existing, "status", None),
        }, status=409)

    except Exception as e:
        return JsonResponse({"ok": False, "error": f"No se pudo crear ticket: {str(e)}"}, status=400)

    return JsonResponse({"ok": True, "ticket_id": ticket.id, "status": ticket.status})





@login_required
@tenant_required
@service_required("alarms_one_id")
def tickets_list(request):
    tenant = get_active_tenant(request)
    if not tenant:
        return render(request, "soar_tickets/tickets_list.html", {"tickets": [], "tenant": None})

    status = (request.GET.get("status") or "OPEN").upper()
    if status not in ("OPEN", "CLOSED", "ALL"):
        status = "OPEN"

    scope = (request.GET.get("scope") or "mine").lower()
    if scope not in ("mine", "all"):
        scope = "mine"

    user_tenant = getattr(request.user, "tenant", None)
    is_inntesec = bool(user_tenant and (user_tenant.name or "").lower() == "inntesec")

    # ✅ Inntesec: por defecto "all" si no viene scope (para que switch tenant muestre tickets del tenant)
    if is_inntesec and "scope" not in request.GET:
        scope = "all"

    base_qs = (
        SoarTicket.objects
        .select_related("assigned_to", "created_by", "closed_by")
        .filter(tenant_id=tenant.id)
    )

    # Si NO es Inntesec, siempre "mine"
    if not is_inntesec:
        scope = "mine"

    if scope == "mine":
        base_qs = base_qs.filter(assigned_to=request.user)

    # counts siempre por scope actual (no por status)
    open_count = base_qs.filter(status=SoarTicket.STATUS_OPEN).count()
    closed_count = base_qs.filter(status=SoarTicket.STATUS_CLOSED).count()

    # ✅ tickets según status
    if status == "ALL":
        tickets = base_qs.filter(status__in=[SoarTicket.STATUS_OPEN, SoarTicket.STATUS_CLOSED]).order_by("-opened_at")
    else:
        tickets = base_qs.filter(status=status).order_by("-opened_at")

    all_tenants = Tenant.objects.all().order_by("name") if is_inntesec else []

    return render(request, "soar_tickets/tickets_list.html", {
        "tenant": tenant,
        "all_tenants": all_tenants,
        "tickets": tickets,
        "status": status,
        "scope": scope,
        "open_count": open_count,
        "closed_count": closed_count,
    })


@require_POST
@login_required
@tenant_required
@service_required("alarms_one_id")
def ticket_close(request, ticket_id):
    tenant = get_active_tenant(request)
    if not tenant:
        if _is_ajax(request):
            return JsonResponse({"ok": False, "error": "No hay tenant activo."}, status=400)
        messages.error(request, "No hay tenant activo.")
        return redirect("soar_tickets:list")

    notes = (request.POST.get("notes") or "").strip()

    try:
        with transaction.atomic():
            t = (
                SoarTicket.objects
                .select_for_update()
                .filter(id=ticket_id, tenant_id=tenant.id)
                .first()
            )

            if not t:
                if _is_ajax(request):
                    return JsonResponse({"ok": False, "error": "Ticket no encontrado."}, status=404)
                messages.error(request, "Ticket no encontrado.")
                return redirect("soar_tickets:list")

            if t.status != SoarTicket.STATUS_OPEN:
                if _is_ajax(request):
                    return JsonResponse({"ok": True, "message": "El ticket ya estaba cerrado."})
                messages.info(request, "El ticket ya estaba cerrado.")
                return redirect("soar_tickets:list")

            t.status = SoarTicket.STATUS_CLOSED
            t.closed_at = timezone.now()
            t.closed_by = request.user
            t.notes = notes
            t.save(update_fields=["status", "closed_at", "closed_by", "notes"])

            closed_ticket_id = t.id

            def _send_close_email_after_commit():
                try:
                    closed_t = (
                        SoarTicket.objects
                        .select_related("assigned_to", "created_by", "closed_by", "tenant")
                        .get(id=closed_ticket_id)
                    )

                    assigned_user = getattr(closed_t, "assigned_to", None)
                    creator_user = getattr(closed_t, "created_by", None)

                    assigned_email = (getattr(assigned_user, "email", "") or "").strip()
                    creator_email = (getattr(creator_user, "email", "") or "").strip()

                    # 1) correo al asignado (saluda al asignado)
                    if assigned_email:
                        enviar_correo_ticket_cerrado(closed_t, recipient=assigned_user)
                    else:
                        logger.warning(
                            "[SOAR_TICKETS] Ticket %s cerrado, asignado sin email. No se envía correo al asignado.",
                            closed_ticket_id
                        )

                    # 2) correo al creador (saluda al creador) si es distinto email
                    if creator_email and creator_email.lower() != (assigned_email or "").lower():
                        enviar_correo_ticket_cerrado(closed_t, to_email=creator_email, recipient=creator_user)
                    elif not creator_email:
                        logger.warning(
                            "[SOAR_TICKETS] Ticket %s cerrado, creador sin email. No se envía correo al creador.",
                            closed_ticket_id
                        )

                except Exception as e:
                    logger.exception("[SOAR_TICKETS] Error enviando correos de cierre ticket=%s: %s", closed_ticket_id, e)

            transaction.on_commit(_send_close_email_after_commit)

    except Exception as e:
        logger.exception("[SOAR_TICKETS] Error cerrando ticket=%s: %s", ticket_id, e)
        if _is_ajax(request):
            return JsonResponse({"ok": False, "error": "No se pudo cerrar el ticket."}, status=400)
        messages.error(request, "No se pudo cerrar el ticket.")
        return redirect("soar_tickets:list")

    if _is_ajax(request):
        return JsonResponse({"ok": True, "message": "Ticket cerrado con éxito", "ticket_id": ticket_id})

    messages.success(request, "Ticket cerrado ✅")
    return redirect("soar_tickets:list")
