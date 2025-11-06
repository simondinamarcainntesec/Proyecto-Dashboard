import requests
import json
from typing import Any, Optional
from django.core.cache import cache
from django.conf import settings

# --- Configuración de la API ---
API_URL = "https://iaproductivo.inntesec.cl/webhook/3c850e31-e699-4fa6-9fed-513d4ccd281b"
API_SECRET = "@L^E4$h!f^r1VmwD#c1B#C8XzM#B4pON"
API_HEADER_NAME = "passkey"
VERIFY_SSL = True


CANDIDATE_KEYS = {"Acces_token", "access_token", "token", "Access_Token", "ACCESS_TOKEN"}


def _find_token_in_response(obj: Any) -> Optional[str]:
    """
    Busca el token en la respuesta (dict/list), recorriendo recursivamente.
    (Esta es tu función 'find_token' adaptada)
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k in CANDIDATE_KEYS:
                if isinstance(v, str) and v.strip():
                    return v.strip()
        for v in obj.values():
            token = _find_token_in_response(v)
            if token:
                return token
    elif isinstance(obj, list):
        for item in obj:
            token = _find_token_in_response(item)
            if token:
                return token
    return None


def get_new_api_token():
    """
    Obtiene un nuevo token de la API.
    (Esta es tu función 'main' adaptada)
    """
    headers = {API_HEADER_NAME: API_SECRET}
    
    try:
        # Hacemos la petición con la librería requests
        response = requests.get(API_URL, headers=headers, timeout=20, verify=VERIFY_SSL)
        # Esto lanzará una excepción (HTTPError) si el código de estado es 4xx o 5xx
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Si hay un error de red o de HTTP, lo relanzamos para que la vista lo capture
        raise Exception(f"Error al conectar con la API para obtener el token: {e}")

    # Intentamos decodificar la respuesta como JSON
    try:
        data = response.json()
        token = _find_token_in_response(data)
        if token:
            return token
        # Si no se encuentra un token, pero la respuesta es JSON, lanzamos un error
        raise Exception(f"No se encontró un token válido en la respuesta JSON: {data}")
    except json.JSONDecodeError:
        # Si no es JSON, podría ser un token en texto plano
        text = response.text.strip()
        if text:
            return text
        # Si no hay texto, lanzamos un error
        raise Exception("La respuesta de la API de token estaba vacía.")


def get_api_token():
    """
    Obtiene el token de la caché si existe, o genera uno nuevo y lo guarda en caché.
    """
    token = cache.get('api_token')
    if not token:
        token = get_new_api_token()
        # Guarda el token en caché por 55 minutos
        cache.set('api_token', token, 60 * 55)
    return token


def get_data_from_api():
    """
    Obtiene los datos de la API usando el token.
    (Esta función permanece igual)
    """
    token = get_api_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }

    data_url = "https://api.example.com/data" 
    
    try:
        response = requests.get(data_url, headers=headers, verify=VERIFY_SSL)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error al obtener los datos de la API: {e}")