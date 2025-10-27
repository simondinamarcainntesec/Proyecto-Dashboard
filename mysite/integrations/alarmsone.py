import os
import subprocess
import httpx
from datetime import datetime, timedelta

# -------------------------
# Función para obtener token vía script externo
# -------------------------
def obtener_token_via_script():
    script_path = "/home/inntesec-ia/Proyecto-Dashboard/obtener_token.py"
    
    try:
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True,
            timeout=25
        )
        if result.returncode == 0:
            token = result.stdout.strip()
            if token:
                print(f"✅ Token obtenido correctamente: {token[:10]}...")  # opcional
                return token
            else:
                print("❌ El script devolvió vacío, no se obtuvo token")
                return None
        else:
            print(f"❌ Error ejecutando script obtener_token.py (exit {result.returncode})")
            print(result.stderr or result.stdout)
            return None
    except Exception as e:
        print(f"❌ Excepción ejecutando obtener_token.py: {e}")
        return None

# -------------------------
# Función principal para obtener token
# -------------------------
def get_token():
    token = obtener_token_via_script()
    if not token:
        raise RuntimeError("No se pudo obtener el token desde obtener_token.py")
    return token

# -------------------------
# Ejemplo de uso de token en petición HTTPX
# -------------------------
def list_alarms_all(from_dt: int, to_dt: int):
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    url = f"https://alarmsone.manageengine.com/rest/json/listAlarms?fromDate={from_dt}&toDate={to_dt}&filter=all&size=200&from=0"
    
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None

# -------------------------
# Test rápido
# -------------------------
if __name__ == "__main__":
    print("Token:", get_token())
    # Ejemplo: desde hace 7 días hasta hoy
    from_dt = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
    to_dt = int(datetime.now().timestamp() * 1000)
    alarms = list_alarms_all(from_dt, to_dt)
    print("Cantidad de alarmas:", len(alarms) if alarms else 0)
