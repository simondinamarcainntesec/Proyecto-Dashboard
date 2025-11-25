import requests
import json

URL = "https://log360cloud.manageengine.com/api/v2/alerts"
TOKEN = "1000.e2316eaa18d6e726db6c4fee9dc92d22.2606c20a41aa836e1e8b9385fb3a7b34"  # el mismo que usaste en el curl que sí trajo data
ACCOUNT_ID = "897671591"

headers = {
    "Authorization": f"Zoho-oauthtoken {TOKEN}",
    "account_id": ACCOUNT_ID,
    "Content-Type": "application/json",
}

body = {
    "query": "",
    "start_time": "2025-11-23T00:00:00Z",
    "end_time":   "2025-11-24T23:59:59Z",
    "from": 1,
    "limit": 50,
    "response_type": "client",
}

resp = requests.post(URL, headers=headers, data=json.dumps(body), timeout=30)

print(resp.status_code)
print(resp.text)
