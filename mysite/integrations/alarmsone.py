# mysite/integrations/alarmsone.py
import os, json
from datetime import datetime, timezone
import httpx

BASE_URL = os.getenv("ALARMSONE_BASE_URL", "https://alarmsone.manageengine.com/rest/json")

def _token() -> str:
    t = os.getenv("ALARMSONE_TOKEN")
    if not t:
        raise RuntimeError("Falta ALARMSONE_TOKEN")
    return t

def _to_ms(dt: datetime) -> int:
    # datetime → epoch ms (UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp() * 1000)

def list_alarms(*, from_dt: datetime, to_dt: datetime, status="all",
                size=20, start=0, groupby=None, search_json: dict | None = None):
    url = f"{BASE_URL}/listAlarms"
    headers = {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/json",
    }
    params = {
        "fromDate": _to_ms(from_dt),
        "toDate": _to_ms(to_dt),
        "filter": status,
        "size": size,
        "from": start,
    }
    if groupby:
        params["groupby"] = groupby
    if search_json:
        params["searchJson"] = json.dumps(search_json, ensure_ascii=False)

    with httpx.Client(timeout=30.0) as client:
        r = client.get(url, headers=headers, params=params)
        r.raise_for_status()
        return r.json(), str(r.url)

def list_alarms_all(
    *, from_dt, to_dt, status="all", page_size=200, max_pages=10,
    groupby=None, search_json: dict | None = None
):
    """
    Descarga varias 'páginas' de listAlarms.
    - page_size: cuántos por página (la API limita; 200 suele ir bien).
    - max_pages: tope de páginas para no abusar en dev.
    Devuelve: {"total": <int|None>, "alarms": [ ... ] }
    """
    alarms = []
    total = None
    for p in range(max_pages):
        start = p * page_size
        raw, _ = list_alarms(
            from_dt=from_dt, to_dt=to_dt, status=status,
            size=page_size, start=start,
            groupby=groupby, search_json=search_json
        )
        data = raw.get("data") or raw
        batch = data.get("alarms", []) or []
        total = data.get("total", total)
        alarms.extend(batch)
        if not batch or len(batch) < page_size:
            break
    return {"total": total, "alarms": alarms}
