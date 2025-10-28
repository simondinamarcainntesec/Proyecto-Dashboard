# tenants/context.py
from contextvars import ContextVar

# Contexto global seguro por-request (apto para async)
current_tenant = ContextVar("current_tenant", default=None)

# Origen del tenant (para depuración): "session" | "user" | None
current_tenant_source = ContextVar("current_tenant_source", default=None)
