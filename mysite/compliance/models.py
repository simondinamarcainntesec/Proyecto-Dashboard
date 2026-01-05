from __future__ import annotations
from django.db import models
from django.conf import settings

from tenants.models import Tenant


def _schema_table(name: str) -> str:
    # Para Postgres: "compliance"."<tabla>"
    return 'compliance"."%s' % name


class ComplianceControl(models.Model):
    """
    Catálogo GLOBAL de controles (sin tenant).
    Se importa una vez y sirve para todos.
    """
    domain = models.CharField(max_length=10)              # A.5, A.6...
    category = models.CharField(max_length=80)            # Organizacionales...
    code = models.CharField(max_length=20, unique=True)   # A.5.1
    title = models.CharField(max_length=255)              # Control (paráfrasis)
    description = models.TextField(blank=True, default="")

    # ✅ actividades ilimitadas (JSONB)
    activity_items = models.JSONField(default=list, blank=True)

    framework = models.CharField(max_length=60, blank=True, default="ISO27001")
    framework_version = models.CharField(max_length=20, blank=True, default="2022")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = _schema_table("compliance_control")
        indexes = [models.Index(fields=["domain", "category"])]

    def __str__(self):
        return f"{self.code} - {self.title}"


class ComplianceRisk(models.Model):
    """
    Riesgos por tenant (R-002, etc.)
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="compliance_risks")
    code = models.CharField(max_length=50)
    level = models.CharField(max_length=50, blank=True, default="")
    title = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = _schema_table("compliance_risk")
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uniq_compliance_risk_by_tenant")
        ]

    def __str__(self):
        return f"{self.tenant_id}:{self.code}"


class ComplianceTenantControl(models.Model):
    """
    SoA / estado por tenant en UNA sola tabla.
    Diferenciado por tenant_id (como te pidieron).
    """
    class Status(models.TextChoices):
        NOT_EVALUATED = "not_evaluated", "No evaluado"
        NOT_IMPLEMENTED = "not_implemented", "No implementado"
        IN_PROGRESS = "in_progress", "En proceso"
        IMPLEMENTED = "implemented", "Implementado"
        NA = "na", "No aplica"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="compliance_controls")
    control = models.ForeignKey(ComplianceControl, on_delete=models.CASCADE, related_name="tenant_controls")

    applicable = models.BooleanField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.NOT_EVALUATED)

    justification = models.TextField(blank=True, default="")
    responsible_label = models.CharField(max_length=255, blank=True, default="")

    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="responsible_compliance_controls"
    )

    primary_risk_code = models.CharField(max_length=50, blank=True, default="")

    target_date = models.DateField(null=True, blank=True)
    last_review_at = models.DateField(null=True, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)  # 0..100
    alert = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = _schema_table("compliance_tenant_control")
        constraints = [
            models.UniqueConstraint(fields=["tenant", "control"], name="uniq_tenant_control")
        ]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "applicable"]),
        ]

    def __str__(self):
        return f"{self.tenant_id}:{self.control.code}"


class ComplianceTenantControlRisk(models.Model):
    """
    Tabla intermedia M2M para que viva sí o sí en schema compliance.
    """
    tenant_control = models.ForeignKey(ComplianceTenantControl, on_delete=models.CASCADE)
    risk = models.ForeignKey(ComplianceRisk, on_delete=models.CASCADE)

    class Meta:
        db_table = _schema_table("compliance_tenant_control_risks")
        constraints = [
            models.UniqueConstraint(fields=["tenant_control", "risk"], name="uniq_tc_risk")
        ]


# ✅ M2M usando through (para controlar db_table)
ComplianceTenantControl.add_to_class(
    "risks",
    models.ManyToManyField(
        ComplianceRisk,
        through=ComplianceTenantControlRisk,
        blank=True,
        related_name="controls",
    )
)


class ComplianceEvidence(models.Model):
    """
    Evidencias 1-N por control del tenant.
    """
    tenant_control = models.ForeignKey(
        ComplianceTenantControl, on_delete=models.CASCADE, related_name="evidences"
    )
    type = models.CharField(max_length=30, default="link")  # link/path/file/ticket
    uri = models.TextField()
    title = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = _schema_table("compliance_evidence")
        constraints = [
            models.UniqueConstraint(fields=["tenant_control", "uri"], name="uniq_evidence_uri_by_control")
        ]
