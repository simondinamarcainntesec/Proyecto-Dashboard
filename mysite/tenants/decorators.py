# tenants/decorators.py
import logging
from functools import wraps
from django.shortcuts import render
from django.contrib import messages
from tenants.models import Tenant

logger = logging.getLogger(__name__)

def tenant_required(view_func):
    """
    Exige usuario autenticado y tenant válido.
    NOTA: NO hacemos redirect por nombre de URL para no tocar rutas.
    Renderizamos el login template directamente, como pediste.
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
            logger.warning("[Tenancy] Vista protegida sin tenant. user=%s", request.user)
            return render(request, "auth/login.html", {"redirected_for_tenant": True})

        return view_func(request, *args, **kwargs)

    return _wrapped_view
