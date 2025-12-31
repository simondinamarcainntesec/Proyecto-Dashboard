# soar_tickets/tasks.py
import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.db.utils import NotSupportedError  # 👈 opcional si quieres excluir retry

from .models import SoarTicket
from utils.ms_email import enviar_correo_ticket_recordatorio_2dias

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    # 👇 opcional: evita reintentar por este error específico
    # dont_autoretry_for=(NotSupportedError,),
)
def send_due_soon_reminders(self):
    today = timezone.localdate()
    target_due = today + timedelta(days=2)  # “vence en 2 días”

    qs = (
        SoarTicket.objects
        .select_related("tenant", "assigned_to")  # ✅ acá sí, para el scan inicial
        .filter(status=SoarTicket.STATUS_OPEN, due_date=target_due)
        .exclude(reminder_due_soon_for=target_due)
    )

    total = qs.count()
    sent = 0
    skipped_no_email = 0

    logger.info("[SOAR_TICKETS] due-soon scan: today=%s target_due=%s candidates=%s", today, target_due, total)

    for ticket in qs.iterator(chunk_size=200):
        assigned = getattr(ticket, "assigned_to", None)
        email = (getattr(assigned, "email", "") or "").strip()

        # Si no tiene email: marcamos como avisado para no spamear
        if not email:
            skipped_no_email += 1
            ticket.reminder_due_soon_for = target_due
            ticket.reminder_due_soon_sent_at = timezone.now()
            ticket.reminder_due_soon_count = (ticket.reminder_due_soon_count or 0) + 1
            ticket.save(update_fields=["reminder_due_soon_for", "reminder_due_soon_sent_at", "reminder_due_soon_count"])
            continue

        with transaction.atomic():
            # ✅ IMPORTANTÍSIMO:
            # NO uses select_related("assigned_to") acá porque hace LEFT OUTER JOIN (nullable)
            locked = (
                SoarTicket.objects
                .select_for_update()
                .select_related("tenant")     # ✅ tenant NO es nullable, safe
                .get(id=ticket.id)
            )

            # Re-check con lock (anti duplicado)
            if locked.reminder_due_soon_for == target_due:
                continue

            # assigned_to lo accedemos normal (puede hacer 1 query extra, pero es seguro)
            assigned_locked = locked.assigned_to
            email_locked = (getattr(assigned_locked, "email", "") or "").strip()

            ok = False
            if email_locked:
                ok = enviar_correo_ticket_recordatorio_2dias(locked)
            else:
                skipped_no_email += 1

            locked.reminder_due_soon_for = target_due
            locked.reminder_due_soon_sent_at = timezone.now()
            locked.reminder_due_soon_count = (locked.reminder_due_soon_count or 0) + 1
            locked.save(update_fields=["reminder_due_soon_for", "reminder_due_soon_sent_at", "reminder_due_soon_count"])

            if ok:
                sent += 1

    logger.info("[SOAR_TICKETS] due-soon done: sent=%s skipped_no_email=%s total=%s", sent, skipped_no_email, total)
    return {"target_due": str(target_due), "candidates": total, "sent": sent, "skipped_no_email": skipped_no_email}
