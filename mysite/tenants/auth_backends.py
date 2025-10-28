# tenants/authbackends.py
import logging
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from tenants.models import Tenant

logger = logging.getLogger(__name__)
UserModel = get_user_model()

class TenantBackend(ModelBackend):
    """
    Autenticación scoping por tenant.
    Si se entrega tenant_name (kwargs o POST 'tenant'), busca username dentro de ese tenant.
    Si no hay tenant_name, deja que el ModelBackend normal opere (si está configurado después).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        tenant_name = kwargs.get("tenant_name")
        if request and not tenant_name:
            tenant_name = request.POST.get("tenant") or request.session.get("tenant_name")

        if not username or not password:
            return None

        # Si no hay tenant_name, no forzamos scoping aquí: que resuelva el backend por defecto.
        if not tenant_name:
            logger.debug("[Auth] TenantBackend sin tenant_name → delega al ModelBackend.")
            return None

        tenant = Tenant.objects.filter(name__iexact=tenant_name).first()
        if not tenant:
            logger.warning("[Auth] Tenant no encontrado: %s", tenant_name)
            return None

        try:
            user = UserModel.objects.get(username=username, tenant=tenant)
        except UserModel.DoesNotExist:
            logger.warning("[Auth] Usuario no encontrado en tenant=%s username=%s", tenant_name, username)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            logger.debug("[Auth] Autenticación OK user=%s tenant=%s", user.username, tenant.name)
            return user

        logger.warning("[Auth] Password inválido user=%s tenant=%s", username, tenant.name)
        return None
