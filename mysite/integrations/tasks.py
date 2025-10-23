from pathlib import Path
import logging
from celery import shared_task
import requests
from integrations.api_client import UnauthorizedError


TOKEN_FILE = "token.txt"  # Ajusta según tu ruta real

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def tarea_ingesta_api(self, from_dt=None, to_dt=None):
    """
    Tarea de ingesta de alarmas desde la API.
    Maneja obtención automática de token y reintentos.
    """
    try:
        token = None

        # Intentar leer token existente
        if Path(TOKEN_FILE).exists():
            with open(TOKEN_FILE, "r") as f:
                token = f.read().strip()
        
        def obtener_resultado(token_actual):
            """
            Intenta llamar a la API con el token actual.
            Si falla por token inválido, devuelve None para forzar refresco.
            """
            try:
                return list_alarms_all(from_dt=from_dt, to_dt=to_dt, token=token_actual)
            except UnauthorizedError:  # Ajusta según la excepción real
                logging.warning("Token inválido o expirado.")
                return None

        result = obtener_resultado(token)

        # Si token es inválido o no existe, pedir uno nuevo
        if result is None:
            logging.info("Obteniendo un token nuevo...")
            token = tarea_obtener_token()
            # Guardar token en archivo
            with open(TOKEN_FILE, "w") as f:
                f.write(token)
            result = list_alarms_all(from_dt=from_dt, to_dt=to_dt, token=token)

        logging.info(f"✅ Ingesta completada: {len(result)} alarmas procesadas.")
        return result

    except Exception as e:
        logging.warning(f"❌ Error durante la ingesta de API: {e}")
        raise self.retry(exc=e)