# mysite/utils/ms_email.py

import logging
import requests
from django.conf import settings
from django.utils import timezone
import pytz

logger = logging.getLogger(__name__)
# ==============================================
# 🔑 Obtener token OAuth2 (client_credentials)
# ==============================================
def obtener_token_ms():
    """
    Solicita un token OAuth2 de Microsoft usando client_credentials.
    """
    ms_conf = settings.OAUTH2_MICROSOFT
    data = {
        "grant_type": "client_credentials",
        "client_id": ms_conf["MS_CLIENT_ID"],
        "client_secret": ms_conf["MS_CLIENT_SECRET"],
        "scope": "https://graph.microsoft.com/.default",
    }

    logger.debug(f"🔑 Solicitando token a {ms_conf['MS_TOKEN_URL']}")
    response = requests.post(ms_conf["MS_TOKEN_URL"], data=data)

    if response.status_code != 200:
        logger.error(f"❌ Error obteniendo token: {response.text}")
        raise Exception(f"Error obteniendo token de Microsoft: {response.text}")

    token = response.json().get("access_token")
    logger.info("🟢 Token Microsoft Graph obtenido correctamente.")
    return token


# ==============================================
# 📧 Envío genérico de correos por Microsoft Graph
# ==============================================
def enviar_correo_ms(destinatario, asunto, cuerpo_html):
    """
    Envía correo HTML a través de Microsoft Graph API.
    """
    token = obtener_token_ms()
    remitente = settings.OAUTH2_MICROSOFT["MS_USER_EMAIL"]

    url = f"https://graph.microsoft.com/v1.0/users/{remitente}/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = {
        "message": {
            "subject": asunto,
            "body": {"contentType": "HTML", "content": cuerpo_html},
            "toRecipients": [{"emailAddress": {"address": destinatario}}],
        },
        "saveToSentItems": "true",
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code not in (200, 202):
        logger.error(f"❌ Error enviando correo: {response.status_code} {response.text}")
        raise Exception(f"Error enviando correo: {response.text}")

    logger.info(f"📬 Correo enviado correctamente a {destinatario}")
# ==============================================
# 🔒 Correo específico: cambio de contraseña
# ==============================================
def enviar_correo_cambio_contrasena(email_destino, nombre_usuario):
    """Envía un correo de confirmación de cambio de contraseña."""
    asunto = "Confirmación de cambio de contraseña"
    zona_cl = pytz.timezone("America/Santiago")
    fecha = timezone.localtime(timezone.now(), zona_cl).strftime("%d/%m/%Y %H:%M:%S")

    cuerpo_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2>Hola, {nombre_usuario}</h2>
        <p>Tu contraseña fue cambiada exitosamente el <b>{fecha}</b>.</p>
        <p>Si realizaste este cambio, no necesitas hacer nada más.</p>
        <p style="color:red;">Si <b>no reconoces</b> este cambio, por favor contacta inmediatamente con el equipo de administración de Inntesec:</p>
        <p><a href="mailto:soporte@inntesec.com">soporte@inntesec.com</a></p>
        <hr>
        <p style="font-size: 12px; color: gray;">Este correo se envió automáticamente desde Inntesec Agent IA.</p>
    </body>
    </html>
    """

    enviar_correo_ms(email_destino, asunto, cuerpo_html)
    