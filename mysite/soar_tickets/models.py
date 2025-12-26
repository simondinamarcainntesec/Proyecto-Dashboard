from django.conf import settings
from django.db import models
from django.db.models import Q

from tenants.models import Tenant


class SoarTicket(models.Model):
    STATUS_OPEN = "OPEN"
    STATUS_CLOSED = "CLOSED"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Abierto"),
        (STATUS_CLOSED, "Cerrado"),
    ]

    # ===== Contexto multi-tenant =====
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="soar_tickets", db_index=True)

    # ===== Identificador evento / alarma =====
    alarm_id = models.TextField(db_index=True)

    # ===== Snapshot del evento =====
    dispositivo = models.TextField(blank=True, default="")
    tipo_de_amenaza = models.TextField(blank=True, default="")
    nivel_de_severidad = models.TextField(blank=True, default="")

    event_date = models.DateField(null=True, blank=True)
    event_time = models.TimeField(null=True, blank=True)

    descripcion_incidente = models.TextField(blank=True, default="")
    analisis_criticidad = models.TextField(blank=True, default="")
    medidas_correctivas = models.TextField(blank=True, default="")
    resumen_humano = models.TextField(blank=True, default="")
    riesgo_detectado = models.TextField(blank=True, default="")
    application = models.TextField(blank=True, default="")

    # ===== Asignación =====
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="soar_assigned_tickets",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="soar_created_tickets",
    )

    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="soar_closed_tickets",
    )

    # ===== Estado / fechas =====
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    opened_at = models.DateTimeField(auto_now_add=True)      # inicio real
    due_date = models.DateField(null=True, blank=True)       # fin planificado
    closed_at = models.DateTimeField(null=True, blank=True)  # cierre real

    notes = models.TextField(blank=True, default="")

    class Meta:
        # 👇 IMPORTANTE: tabla en schema agent
        db_table = 'agent"."soar_ticket'
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_soar_ticket_tenant_status"),
            models.Index(fields=["tenant", "alarm_id"], name="idx_soar_ticket_tenant_alarm"),
        ]
        constraints = [
            # 1 ticket abierto por tenant+alarm_id (evita duplicados abiertos)
            models.UniqueConstraint(
                fields=["tenant", "alarm_id"],
                condition=Q(status="OPEN"),  # 👈 FIX: literal en vez de STATUS_OPEN
                name="uniq_open_ticket_per_alarm_tenant",
            )
        ]

    def __str__(self):
        return f"[{self.tenant_id}] {self.alarm_id} - {self.status}"
