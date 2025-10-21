import requests

# URL del webhook
WEBHOOK_URL = "https://iaproductivo.inntesec.cl/webhook/4721cd5e-0c36-4773-8292-fa3b8580cebd"

# Tu passkey correcta
PASSKEY = "@aDv%6rSBPXXhD*iW7dl6PCjOZ4a0Fkc"  # reemplaza con la passkey real

# Parámetro a enviar
PARAMS = {"value": "Clientes"}

def consultar_webhook():
    try:
        headers = {"passkey": PASSKEY}  # se envía como header, no Authorization

        response = requests.get(WEBHOOK_URL, headers=headers, params=PARAMS)
        response.raise_for_status()  # lanza excepción si status != 2xx

        print(f"Status: {response.status_code}")
        print("Respuesta del webhook:", response.text)

    except requests.exceptions.HTTPError as http_err:
        print(f"Error HTTP al consultar el webhook: {http_err}")
        print("Detalle:", response.text)
    except Exception as err:
        print(f"Error inesperado: {err}")

if __name__ == "__main__":
    consultar_webhook()
