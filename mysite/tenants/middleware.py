# tenants/middleware.py
import logging
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from tenants.models import Tenant
from tenants.context import current_tenant, current_tenant_source

logger = logging.getLogger(__name__)
User = get_user_model()

class ActiveTenantMiddleware(MiddlewareMixin):
    """
    Carga el tenant activo en cada request, priorizando:
    1) Sesión (tenant_id)
    2) Usuario autenticado (user.tenant)
    Deja request.tenant y contextvars para managers/servicios.
    Guarda en request.tenant_source: "session" | "user" | None
    """


    def process_request(self, request):
        
        request.tenant = None
        request.tenant_source = None

        # 1) Intentar por sesión
        tenant_id = request.session.get("tenant_id")
        if tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id).first()
            if tenant:
                request.tenant = tenant
                request.tenant_source = "session"
                current_tenant.set(tenant)
                current_tenant_source.set("session")
                logger.debug("[Tenancy] Tenant por sesión: id=%s name=%s", tenant.id, tenant.name)
                return  # early exit: ya seteado

        # 2) Fallback: usuario autenticado
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            user_tenant = getattr(user, "tenant", None)
            if user_tenant:
                request.tenant = user_tenant
                request.tenant_source = "user"
                current_tenant.set(user_tenant)
                current_tenant_source.set("user")
                logger.debug("[Tenancy] Tenant por usuario: id=%s name=%s", user_tenant.id, user_tenant.name)
                return

        # 3) No se encontró tenant
        current_tenant.set(None)
        current_tenant_source.set(None)
        logger.debug("[Tenancy] Sin tenant asignado en el request.")

    def process_response(self, request, response):
        # Limpieza opcional (no estricta, el contextvar es por-request)
        return response
class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_id = request.session.get("current_tenant_id")
        if tenant_id:
            try:
                tenant = Client.objects.get(id=tenant_id)
                connection.set_tenant(tenant)  # ⬅️ esto cambia el schema activo
                request.tenant = tenant
            except Client.DoesNotExist:
                pass
        response = self.get_response(request)
        return response