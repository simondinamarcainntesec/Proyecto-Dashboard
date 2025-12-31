# tenants/decorators.py
import logging
from functools import wraps

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

from tenants.models import Tenant

logger = logging.getLogger(__name__)


def _is_invalid_service_value(value) -> bool:
    """
    Considera "no habilitado" si es None/vacío o strings típicos.
    Ajusta aquí si tienes otros casos.
    """
    if value is None:
        return True
    s = str(value).strip()
    if not s:
        return True
    return s.lower() in ("0", "null", "none", "false")


def _is_inntesec_user(user) -> bool:
    """
    Revisa el tenant "propio" del usuario (no el tenant activo).
    Así, aunque cambie de tenant en sesión, sigue siendo Inntesec.
    """
    try:
        ut = getattr(user, "tenant", None)
        name = (getattr(ut, "name", "") or "").strip().lower()
        return name == "inntesec"
    except Exception:
        return False


def tenant_required(view_func):
    """
    Exige usuario autenticado y tenant válido.
    Renderiza login directamente para no depender de nombres de URL.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Debes iniciar sesión primero.")
            logger.warning("[Tenancy] Acceso sin autenticación a vista protegida.")
            return render(request, "auth/login.html", {"redirected_for_tenant": True})

        tenant_id = request.session.get("tenant_id")
        tenant = getattr(request, "tenant", None)

        # Si no hay tenant en request, intentamos reconstruir por sesión
        if tenant is None and tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id).first()
            if tenant:
                request.tenant = tenant

        if tenant is None:
            messages.error(request, "No se pudo determinar tu empresa (tenant).")
            logger.warning(
                "[Tenancy] Vista protegida sin tenant. user_id=%s path=%s",
                getattr(request.user, "id", None),
                getattr(request, "path", ""),
            )
            return render(request, "auth/login.html", {"redirected_for_tenant": True})

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def service_required(
    field_name: str,
    *,
    message: str = "No autorizado",
    template_name: str = "errors/403.html",
    allow_inntesec: bool = True,
    allow_staff: bool = False,
):
    """
    Retorna 403 si el tenant ACTIVO (request.tenant) NO tiene habilitado el servicio,
    evaluando un campo del modelo Tenant.

    Ej:
      @service_required("site24x7_id")
      @service_required("logs360siem_id")
      @service_required("alarms_one_id")

    Requiere que tenant_required se ejecute antes (para asegurar request.tenant).

    allow_inntesec:
      - Si el usuario pertenece al tenant "Inntesec" (user.tenant.name == "inntesec"),
        NO se bloquea por servicio, aunque el tenant activo no lo tenga habilitado.
        (Esto permite cambiar de tenant sin toparte con 403)
    allow_staff:
      - Si True, staff/superuser tampoco se bloquea.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 1) Bypass para Inntesec (tu caso: cambiar de tenant)
            if allow_inntesec and _is_inntesec_user(request.user):
                return view_func(request, *args, **kwargs)

            # 2) (Opcional) bypass por staff/superuser
            if allow_staff and (getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False)):
                return view_func(request, *args, **kwargs)

            tenant = getattr(request, "tenant", None)

            # Si por alguna razón no hay tenant, tratamos como no autorizado
            if tenant is None:
                logger.warning(
                    "[Tenancy] Bloqueo por servicio sin tenant. service=%s user_id=%s path=%s",
                    field_name,
                    getattr(request.user, "id", None),
                    getattr(request, "path", ""),
                )
                return _render_403(request, template_name, message)

            value = getattr(tenant, field_name, None)
            if _is_invalid_service_value(value):
                # Log seguro: solo IDs + service + path. Sin email, sin nombre tenant, sin value.
                # (Y en WARNING porque se bloquea; si prefieres menos ruido, cámbialo a logger.info)
                logger.warning(
                    "[Tenancy] Acceso bloqueado por servicio no habilitado. service=%s tenant_id=%s user_id=%s path=%s",
                    field_name,
                    getattr(tenant, "id", None),
                    getattr(request.user, "id", None),
                    getattr(request, "path", ""),
                )
                return _render_403(request, template_name, message)

            return view_func(request, *args, **kwargs)

        return _wrapped_view
    return decorator


def _render_403(request, template_name: str, message: str):
    """
    Render 403 con template si existe; si no, fallback a texto simple.
    """
    try:
        get_template(template_name)  # valida existencia
        return render(
            request,
            template_name,
            {
                "message": message,
                "path": getattr(request, "path", ""),
            },
            status=403,
        )
    except TemplateDoesNotExist:
        return HttpResponseForbidden(message)
