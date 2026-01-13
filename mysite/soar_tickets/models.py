# soar_tickets/models.py
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

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="soar_tickets",
        db_index=True,
    )
    alarm_id = models.TextField(db_index=True)

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

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        db_index=True,
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    initial_notes = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")

    # ✅ RECORDATORIO 2 DÍAS ANTES DEL VENCIMIENTO (1 por ticket y por due_date)
    reminder_due_soon_for = models.DateField(
        null=True,
        blank=True,
        help_text="Para qué due_date ya se envió recordatorio 'vence en 2 días'.",
    )
    reminder_due_soon_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_due_soon_count = models.PositiveIntegerField(default=0)

    # ✅ NOTIFICACIÓN: TICKET VENCIDO (1 sola vez por ticket)
    overdue_notified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Cuándo se notificó por primera (y única) vez el vencimiento del ticket.",
    )
    overdue_notified_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'agent"."soar_ticket'
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_soar_ticket_tenant_status"),
            models.Index(fields=["tenant", "alarm_id"], name="idx_soar_ticket_tenant_alarm"),
            models.Index(fields=["status", "due_date"], name="idx_soar_ticket_status_due"),
            # ✅ acelera el scan de vencidos (open + due_date + no notificado)
            models.Index(fields=["status", "due_date", "overdue_notified_at"], name="idx_soar_ticket_overdue_scan"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "alarm_id"],
                condition=Q(status="OPEN"),
                name="uniq_open_ticket_per_alarm_tenant",
            )
        ]

    def __str__(self):
        return f"[{self.tenant_id}] {self.alarm_id} - {self.status}"
