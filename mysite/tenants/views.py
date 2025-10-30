# auth/views.py
import logging
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.cache import never_cache
from tenants.models import Tenant
from tenants.context import current_tenant, current_tenant_source
from django.http import HttpResponseRedirect
from django.urls import reverse

logger = logging.getLogger(__name__)
User = get_user_model()

def tenant_login_view(request):
    """
    Login con identifier (email o username) + password.
    Opcional: POST['tenant'] para scope explícito.
    Depuración:
      - Se loguea el origen del tenant (por sesión o por usuario).
      - Se rellena request.session['tenant_id'] y ['tenant_name'] con el tenant del usuario autenticado.
    """
    # Si ya hay sesión activa, cerramos para evitar mezclar empresas previas
    if request.method == "GET" and request.user.is_authenticated:
        # No cerramos automáticamente en GET para no sorprender al usuario.
        pass

    if request.method == "POST":
        identifier = request.POST.get("username")  # puede ser email o username
        password = request.POST.get("password")
        form_tenant_name = request.POST.get("tenant")  # opcional

        if not identifier or not password:
            messages.error(request, "Debes ingresar tu correo o usuario y contraseña.")
            return render(request, "auth/login.html", {"now": timezone.now()})

        # Cerramos sesión anterior (por si existía otra empresa activa)
        if request.user.is_authenticated:
            logout(request)

        # Resolución de usuario dentro de un tenant (si se proporcionó)
        user = None
        if form_tenant_name:
            tenant = Tenant.objects.filter(name__iexact=form_tenant_name).first()
            if not tenant:
                messages.error(request, "Empresa no encontrada.")
                return render(request, "auth/login.html", {"now": timezone.now()})

            user = (
                User.objects.filter(
                    Q(email__iexact=identifier) | Q(username__iexact=identifier),
                    tenant=tenant,
                )
                .select_related("tenant")
                .first()
            )
            if not user:
                messages.error(request, "Credenciales inválidas.")
                return render(request, "auth/login.html", {"now": timezone.now()})

            # Autentica con scoping por tenant (usa TenantBackend)
            user_auth = authenticate(
                request, username=user.username, password=password, tenant_name=tenant.name
            )
        else:
            # Sin tenant explícito: buscamos un match global (puede haber colisión)
            user = (
                User.objects.filter(
                    Q(email__iexact=identifier) | Q(username__iexact=identifier)
                )
                .select_related("tenant")
                .first()
            )
            if not user:
                messages.error(request, "Credenciales inválidas.")
                return render(request, "auth/login.html", {"now": timezone.now()})

            # Intentamos primero con TenantBackend usando el tenant del propio usuario encontrado
            tenant_name_guess = getattr(getattr(user, "tenant", None), "name", None)
            user_auth = authenticate(
                request, username=user.username, password=password, tenant_name=tenant_name_guess
            )
            if user_auth is None:
                # Fallback: backend por defecto (por si tu proyecto permite auth global)
                user_auth = authenticate(request, username=user.username, password=password)

        if user_auth is not None:
            login(request, user_auth)
            # Establecer tenant en sesión según el usuario autenticado (fuente BD)
            tenant = getattr(user_auth, "tenant", None)
            if tenant:
                request.session["tenant_id"] = tenant.id
                request.session["tenant_name"] = tenant.name
                logger.info("[Login] Ok user=%s tenant=%s (guardado en sesión).",
                            user_auth.username, tenant.name)
            else:
                request.session["tenant_id"] = None
                request.session["tenant_name"] = None
                logger.warning("[Login] Usuario autenticado sin tenant asociado: %s", user_auth.username)
                messages.warning(request, "Inicio de sesión sin tenant asociado.")

            # Info de depuración (si tu template la muestra)
            ctx = {
                "now": timezone.now(),
                "tenant_debug": {
                    "request_tenant_id": getattr(request.tenant, "id", None),
                    "request_tenant_name": getattr(request.tenant, "name", None),
                    "request_tenant_source": getattr(request, "tenant_source", None),
                    "ctx_tenant_name": getattr(current_tenant.get(), "name", None),
                    "ctx_tenant_source": current_tenant_source.get(),
                },
            }
            # Redirige a home del dashboard; si aún no lo quieres, render del login con debug
            return redirect("dashboard")  # ← si prefieres no redirigir todavía, comenta esta línea y usa el render de abajo.
            # return render(request, "auth/login.html", ctx)

        messages.error(request, "Credenciales inválidas.")
        return render(request, "auth/login.html", {"now": timezone.now()})

    # GET: Render simple (también muestra debug si el middleware ya estableció tenant)
    ctx = {
        "now": timezone.now(),
        "tenant_debug": {
            "request_tenant_id": getattr(getattr(request, "tenant", None), "id", None),
            "request_tenant_name": getattr(getattr(request, "tenant", None), "name", None),
            "request_tenant_source": getattr(request, "tenant_source", None),
            "ctx_tenant_name": getattr(current_tenant.get(), "name", None),
            "ctx_tenant_source": current_tenant_source.get(),
        },
    }
    return render(request, "auth/login.html", ctx)

@never_cache
def logout_view(request):
    """
    Cierra sesión, limpia por completo la sesión (incluye tenant_id/tenant_name)
    y vuelve al login con headers anti-cache para evitar 'volver atrás'.
    """
    logout(request)
    # limpia TODA la sesión (cualquier resto de tenant/filtros)
    request.session.flush()

    resp = HttpResponseRedirect(reverse("login"))  # no cambio tu template/route
    # cinturón y tirantes contra cache
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    resp["Expires"] = "0"
    return resp