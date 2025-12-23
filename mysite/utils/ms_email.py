# mysite/utils/ms_email.py

import logging
import requests
from django.conf import settings
from django.utils import timezone
import pytz

logger = logging.getLogger(__name__)
# ==============================================
# Obtener token OAuth2 (client_credentials)
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
# Envío genérico de correos por Microsoft Graph
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
# Correo específico: cambio de contraseña
# ==============================================
def enviar_correo_cambio_contrasena(email_destino, nombre_usuario):
    """Envía un correo de confirmación de cambio de contraseña con el mismo diseño corporativo."""

    asunto = "Confirmación de cambio de contraseña – Portal Clientes Inntesec"
    zona_cl = pytz.timezone("America/Santiago")
    fecha = timezone.localtime(timezone.now(), zona_cl).strftime("%d/%m/%Y %H:%M:%S")

    cuerpo_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; padding: 40px; color: #333;">
      <div style="max-width: 600px; margin: auto; background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        
        <div style="text-align: center; margin-bottom: 25px;">
          <img src="https://ia.inntesec.com/static/img/inntesec_logo_negro.png" alt="Inntesec" style="height: 50px;">
        </div>

        <h2 style="color: #0a0a0a;">Hola, {nombre_usuario}</h2>
        <p>Te informamos que tu contraseña fue cambiada exitosamente el <b>{fecha}</b>.</p>

        <p>Si realizaste este cambio, no necesitas hacer nada más.</p>

        <p style="color: red; margin-top: 20px;">
          Si <b>no reconoces</b> este cambio, por favor contacta inmediatamente con el equipo de administración de Inntesec:
        </p>
        <p>
          <a href="mailto:soporte@inntesec.com">soporte@inntesec.com</a>
        </p>

        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">

        <p style="font-size: 12px; color: gray; text-align: center;">
          Este correo se envió automáticamente desde <b>Inntesec Agent IA</b>. Por favor, no respondas a este mensaje.
        </p>
      </div>
    </body>
    </html>
    """

    enviar_correo_ms(email_destino, asunto, cuerpo_html)


def enviar_correo_recuperar_contrasena(email_destino, nombre_usuario, reset_link):
    """Envía un correo HTML con el enlace de recuperación de contraseña (usando Graph API)."""

    asunto = "Recuperación de contraseña – Portal Clientes Inntesec"
    zona_cl = pytz.timezone("America/Santiago")
    fecha = timezone.localtime(timezone.now(), zona_cl).strftime("%d/%m/%Y %H:%M:%S")

    cuerpo_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; padding: 40px; color: #333;">
      <div style="max-width: 600px; margin: auto; background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        
        <div style="text-align: center; margin-bottom: 25px;">
          <img src="https://ia.inntesec.com/static/img/inntesec_logo_negro.png" alt="Inntesec" style="height: 50px;">
        </div>

        <h2 style="color: #0a0a0a;">Hola, {nombre_usuario}</h2>
        <p>Hemos recibido una solicitud para restablecer tu contraseña el <b>{fecha}</b>.</p>

        <p style="margin-top: 20px;">Para crear una nueva contraseña, haz clic en el siguiente enlace:</p>

        <p style="text-align: center; margin: 30px 0;">
          <a href="{reset_link}" target="_blank" 
            style="background-color: #007bff; color: white; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: bold;">
            Restablecer Contraseña
          </a>
        </p>

        <p style="color: #555;">Si <b>no realizaste</b> esta solicitud, puedes ignorar este correo.</p>

        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">

        <p style="font-size: 12px; color: gray; text-align: center;">
          Este correo se envió automáticamente desde <b>Inntesec Agent IA</b>. Por favor, no respondas a este mensaje.
        </p>
      </div>
    </body>
    </html>
    """

    # Envía el correo usando tu método Graph API
    from utils.ms_email import enviar_correo_ms
    enviar_correo_ms(email_destino, asunto, cuerpo_html)

def enviar_correo_registro_cliente(email_destino, nombre_usuario, tenant_name, password, url_login):
    """Envía el correo de bienvenida al nuevo cliente con diseño corporativo."""
    asunto = f"Acceso a tu cuenta en {tenant_name}"

    cuerpo_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; padding: 40px; color: #333;">
      <div style="max-width: 600px; margin: auto; background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

        <div style="text-align: center; margin-bottom: 25px;">
          <img src="https://ia.inntesec.com/static/img/inntesec_logo_negro.png" alt="Inntesec" style="height: 50px;">
        </div>

        <h2 style="color: #0a0a0a;">Hola, {nombre_usuario}</h2>
        <p>Tu cuenta ha sido creada exitosamente en <b>{tenant_name}</b>.</p>

        <div style="background: #f1f5ff; padding: 15px; border-radius: 8px; margin: 20px 0;">
          <p style="margin: 0;">
            <b>Usuario:</b> {email_destino}<br>
            <b>Contraseña temporal:</b> {password}
          </p>
        </div>

        <p>Puedes acceder a tu cuenta haciendo clic en el siguiente enlace:</p>
        <p style="text-align: center; margin: 25px 0;">
          <a href="{url_login}" target="_blank"
             style="background-color: #007bff; color: white; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: bold;">
             Iniciar Sesión
          </a>
        </p>

        <p>Por seguridad, cambia tu contraseña al iniciar sesión.</p>

        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
        <p style="font-size: 12px; color: gray; text-align: center;">
          Este mensaje fue generado automáticamente por el sistema <b>Inntesec IA</b>. Por favor, no respondas a este correo.
        </p>
      </div>
    </body>
    </html>
    """

    enviar_correo_ms(email_destino, asunto, cuerpo_html)