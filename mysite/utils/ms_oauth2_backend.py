from django.core.mail.backends.base import BaseEmailBackend
from utils.ms_email import enviar_correo_ms


class MicrosoftGraphEmailBackend(BaseEmailBackend):
    """Backend de correo que usa Microsoft Graph API (opción oficial y recomendada)."""

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        sent_count = 0
        for message in email_messages:
            try:
                enviar_correo_ms(
                    subject=message.subject,
                    body=message.body,
                    destinatarios=message.to,
                    remitente=message.from_email,
                )
                sent_count += 1
            except Exception as e:
                print(f"[ERROR MicrosoftGraphEmailBackend] {e}")
        return sent_count