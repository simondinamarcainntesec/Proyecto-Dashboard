from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from compliance.models import (
    ComplianceControl,
    ComplianceTenantControl,
    ComplianceEvidence,
    ComplianceRisk,
    ComplianceTenantControlRisk,
)
from tenants.models import Tenant


def _s(v: Any) -> str:
    return ("" if v is None else str(v)).strip()


def _to_bool(v: Any) -> Optional[bool]:
    s = _s(v).lower()
    if s in ("sí", "si", "yes", "y", "true", "1"):
        return True
    if s in ("no", "n", "false", "0"):
        return False
    return None


def _to_date(v: Any) -> Optional[date]:
    if v is None or _s(v) == "":
        return None
    dt = pd.to_datetime(v, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.date()


def _to_progress(v: Any) -> int:
    s = _s(v)
    if not s:
        return 0
    s2 = s.replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", s2)
    if not m:
        return 0
    num = float(m.group(1))
    if "%" in s2:
        return max(0, min(100, int(round(num))))
    if 0 <= num <= 1:
        return max(0, min(100, int(round(num * 100))))
    return max(0, min(100, int(round(num))))


def _map_status(v: Any) -> str:
    s = _s(v).lower()
    if s in ("implementado", "implemented"):
        return ComplianceTenantControl.Status.IMPLEMENTED
    if s in ("en proceso", "in progress", "proceso"):
        return ComplianceTenantControl.Status.IN_PROGRESS
    if s in ("no implementado", "not implemented", "pendiente"):
        return ComplianceTenantControl.Status.NOT_IMPLEMENTED
    if s in ("no aplica", "n/a", "na"):
        return ComplianceTenantControl.Status.NA
    return ComplianceTenantControl.Status.NOT_EVALUATED


def parse_activity_items(cell: Any) -> list[str]:
    """
    Convierte "Actividad para cumplir" a lista ilimitada.
    Soporta bullets (•) y saltos de línea.
    """
    s = _s(cell)
    if not s:
        return []
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    out: list[str] = []
    for ln in lines:
        ln = re.sub(r'^[\-\•\*]\s*', '', ln).strip()
        if ln:
            out.append(ln)
    return out


def split_evidences(v: Any) -> list[str]:
    s = _s(v)
    if not s:
        return []
    parts = re.split(r"[;\n]+", s)
    return [p.strip() for p in parts if p.strip()]


class Command(BaseCommand):
    help = "Importa hoja 'Controles' del Excel (catálogo + SoA por tenant) en schema compliance."

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", type=str)
        parser.add_argument("--tenant-id", type=int, required=True)
        parser.add_argument("--sheet", default="Controles")
        parser.add_argument("--library-only", action="store_true")
        parser.add_argument("--bootstrap-tenant", action="store_true")
        parser.add_argument("--no-evidences", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        xlsx_path = opts["xlsx_path"]
        sheet = opts["sheet"]
        tenant_id = opts["tenant_id"]

        tenant = Tenant.objects.filter(id=tenant_id).first()
        if not tenant:
            raise CommandError(f"No existe Tenant con id={tenant_id}")

        try:
            df = pd.read_excel(xlsx_path, sheet_name=sheet, engine="openpyxl")
        except Exception as e:
            raise CommandError(f"No pude leer el Excel: {e}")

        expected = [
            "Dominio","Categoría","Código","Control (paráfrasis)","Descripción (detalle)","Actividad para cumplir",
            "Aplicable (Sí/No)","Estado","Justificación (SoA)","Evidencias (enlaces/rutas)","Responsable",
            "Riesgo principal (ID)","Nivel de riesgo (lookup)","Fecha objetivo","Última revisión",
            "Progreso %","Alerta","Notas"
        ]
        missing = [c for c in expected if c not in df.columns]
        if missing:
            raise CommandError(f"Faltan columnas: {missing}\nEncontradas: {list(df.columns)}")

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING(f"DRY RUN OK. Filas={len(df)}"))
            return

        with transaction.atomic():
            # 1) Catálogo global
            for _, row in df.iterrows():
                code = _s(row["Código"])
                if not code:
                    continue

                ComplianceControl.objects.update_or_create(
                    code=code,
                    defaults=dict(
                        domain=_s(row["Dominio"]),
                        category=_s(row["Categoría"]),
                        title=_s(row["Control (paráfrasis)"]),
                        description=_s(row["Descripción (detalle)"]),
                        activity_items=parse_activity_items(row["Actividad para cumplir"]),
                        framework="ISO27001",
                        framework_version="2022",
                    ),
                )

            if opts["library_only"]:
                self.stdout.write(self.style.SUCCESS("OK: catálogo importado."))
                return

            # 2) Bootstrap SoA vacío
            if opts["bootstrap_tenant"]:
                all_controls = ComplianceControl.objects.all().only("id")
                bulk = [
                    ComplianceTenantControl(
                        tenant=tenant,
                        control=c,
                        applicable=None,
                        status=ComplianceTenantControl.Status.NOT_EVALUATED,
                        progress=0,
                    )
                    for c in all_controls
                ]
                ComplianceTenantControl.objects.bulk_create(bulk, ignore_conflicts=True)
                self.stdout.write(self.style.SUCCESS(
                    f"OK: bootstrap SoA tenant_id={tenant.id} (creados faltantes)."
                ))
                return

            # 3) Import SoA real desde el Excel para este tenant
            for _, row in df.iterrows():
                code = _s(row["Código"])
                if not code:
                    continue

                control = ComplianceControl.objects.get(code=code)

                tc, _ = ComplianceTenantControl.objects.update_or_create(
                    tenant=tenant,
                    control=control,
                    defaults=dict(
                        applicable=_to_bool(row["Aplicable (Sí/No)"]),
                        status=_map_status(row["Estado"]),
                        justification=_s(row["Justificación (SoA)"]),
                        responsible_label=_s(row["Responsable"]),
                        primary_risk_code=_s(row["Riesgo principal (ID)"]),
                        target_date=_to_date(row["Fecha objetivo"]),
                        last_review_at=_to_date(row["Última revisión"]),
                        progress=_to_progress(row["Progreso %"]),
                        alert=_to_bool(row["Alerta"]) or False,
                        notes=_s(row["Notas"]),
                    )
                )

                primary_risk = _s(row["Riesgo principal (ID)"])
                risk_level = _s(row["Nivel de riesgo (lookup)"])
                if primary_risk:
                    r, _ = ComplianceRisk.objects.get_or_create(
                        tenant=tenant,
                        code=primary_risk,
                        defaults=dict(level=risk_level),
                    )
                    if risk_level and r.level != risk_level:
                        r.level = risk_level
                        r.save(update_fields=["level"])

                    ComplianceTenantControlRisk.objects.get_or_create(
                        tenant_control=tc,
                        risk=r
                    )

                if not opts["no_evidences"]:
                    for ev in split_evidences(row["Evidencias (enlaces/rutas)"]):
                        ev_type = "link" if ev.startswith("http") else "path"
                        try:
                            ComplianceEvidence.objects.create(
                                tenant_control=tc,
                                type=ev_type,
                                uri=ev
                            )
                        except Exception:
                            pass

        self.stdout.write(self.style.SUCCESS("OK: import completo."))
