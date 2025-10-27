# dashboard/realtime.py
from __future__ import annotations
import subprocess, httpx, pytz, json, re
from datetime import datetime, timezone as _pytimezone
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render

from . import views as v
from .realtime_transform import build_realtime_context

# ---------- rango hoy 00:00 -> ahora ----------
def _today_range_ms_scl():
    tz = pytz.timezone("America/Santiago")
    now_local = datetime.now(tz)
    start_local = tz.localize(datetime(now_local.year, now_local.month, now_local.day, 0, 0, 0))
    start_utc = start_local.astimezone(_pytimezone.utc)
    now_utc = now_local.astimezone(_pytimezone.utc)
    return int(start_utc.timestamp() * 1000), int(now_utc.timestamp() * 1000)


def _get_token_via_script_local():
    script_path = "/home/inntesec-ia/Proyecto-Dashboard/obtener_token.py"
    out = subprocess.run(["python3", script_path], capture_output=True, text=True, timeout=25)
    if out.returncode != 0:
        raise RuntimeError(f"obtener_token.py exit={out.returncode} stderr={out.stderr or out.stdout}")
    token = (out.stdout or "").strip()
    if not token:
        raise RuntimeError("obtener_token.py devolvió vacío")
    return token


def _fetch_alarms_today_direct(max_pages=50, page_size=1000):
    token = _get_token_via_script_local()
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    from_ms, to_ms = _today_range_ms_scl()

    base = "https://alarmsone.manageengine.com/rest/json/listAlarms"
    all_rows, offset = [], 0
    for _ in range(max_pages):
        url = f"{base}?fromDate={from_ms}&toDate={to_ms}&filter=all&size={page_size}&from={offset}"
        with httpx.Client(timeout=30) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            payload = r.json() or {}
        rows = payload.get("data") or payload.get("alarms") or []
        if not isinstance(rows, list):
            rows = []
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return from_ms, to_ms, all_rows


_get_value_case_insensitive = getattr(v, "_get_value_case_insensitive", None)
_to_datetime_santiago      = getattr(v, "_to_datetime_santiago", None)
_format_aotags             = getattr(v, "_format_aotags", None)
_message_extract_multiple_sources = getattr(v, "_message_extract_multiple_sources", None)

if _get_value_case_insensitive is None:
    def _get_value_case_insensitive(d: dict, key: str):
        if not isinstance(d, dict): return ""
        if key in d: return d[key]
        kl = key.lower()
        for k, val in d.items():
            if isinstance(k, str) and k.lower() == kl:
                return val
        return ""

if _to_datetime_santiago is None:
    def _to_datetime_santiago(timestamp_ms):
        if not timestamp_ms: return ""
        try:
            import pytz
            ts_s = int(timestamp_ms) / 1000
            utc_dt = datetime.fromtimestamp(ts_s, tz=pytz.utc)
            return utc_dt.astimezone(pytz.timezone("America/Santiago"))
        except Exception:
            return ""

if _message_extract_multiple_sources is None:
    import re, json
    _KEYVAL_ROW_REGEX = re.compile(r"<td[^>]*>\s*([^:<][^<]*?)\s*</td>\s*<td[^>]*>\s*([\s\S]*?)\s*</td>", re.I)
    _LINE_REGEX = re.compile(r"^\s*([^:]{1,64})\s*:\s*(.+)\s*$")
    def _strip_html(s: str) -> str:
        s = re.sub(r"<[^>]+>", "", s or "", flags=re.I)
        return re.sub(r"\s+", " ", s).strip()
    def _norm_key(s: str) -> str:
        if not isinstance(s, str): return ""
        s = s.replace("\xa0", " ")
        s = re.sub(r"\s+", " ", s.strip())
        return s.lower()
    def _extract_kv_from_any(raw_block) -> dict:
        if not raw_block: return {}
        if isinstance(raw_block, dict):
            return { _norm_key(k): _strip_html(json.dumps(v, ensure_ascii=False) if isinstance(v,(dict,list)) else str(v))
                     for k, v in raw_block.items() if isinstance(k, str) }
        s = str(raw_block)
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                return { _norm_key(k): _strip_html(json.dumps(v, ensure_ascii=False) if isinstance(v,(dict,list)) else str(v))
                         for k, v in obj.items() if isinstance(k, str) }
        except Exception:
            pass
        pairs = {}
        for k, v in _KEYVAL_ROW_REGEX.findall(s):
            key = _norm_key(k); val = _strip_html(v)
            if val or key not in pairs: pairs[key] = val
        if pairs: return pairs
        kv = {}
        for line in s.splitlines():
            m = _LINE_REGEX.match(line)
            if m:
                key = _norm_key(m.group(1)); val = _strip_html(m.group(2))
                if val or key not in kv: kv[key] = val
        if "log description" not in kv:
            m = re.search(r"Log\s*Description[:\-]\s*([\s\S]+?)(?:<|$)", s, re.I)
            if m: kv["log description"] = _strip_html(m.group(1))
        return kv
    def _message_extract_multiple_sources(alarm: dict, wanted: list[str]) -> dict:
        detail_keys_candidates = ["log_details", "logdetail", "log-details", "log detail", "logdetails"]
        merged = {}
        for dk in detail_keys_candidates:
            block = _get_value_case_insensitive(alarm, dk)
            d = _extract_kv_from_any(block)
            if d: merged.update(d)
        msg_block = _get_value_case_insensitive(alarm, "message")
        dmsg = _extract_kv_from_any(msg_block); merged.update(dmsg)
        device_aliases = ["device name", "device", "devicename"]
        subtype_aliases = ["subtype", "sub type"]
        out = {w: "" for w in wanted}
        for w in wanted:
            k = _norm_key(w); val = merged.get(k, "")
            if not val and k == "device name":
                for ak in device_aliases:
                    if merged.get(ak): val = merged[ak]; break
            if not val and k == "subtype":
                for ak in subtype_aliases:
                    if merged.get(ak): val = merged[ak]; break
            out[w] = val
        return out

_value_for_column_from_views = getattr(v, "_value_for_column", None)

def _value_for_column_fallback(alarm: dict, column: str):
    if column in ("Action", "actions", "severity", "alarmid"):
        return _get_value_case_insensitive(alarm, column)
    if column == "eventtime":
        return _to_datetime_santiago(_get_value_case_insensitive(alarm, column))
    if column == "aotags":
        s = _get_value_case_insensitive(alarm, column)
        return s
    if column in ("msg_severity", "msg_device_name", "level", "log_description", "subtype"):
        extracted = _message_extract_multiple_sources(
            alarm, wanted=["Severity", "Device Name", "Device", "Level", "Log Description", "Subtype"]
        )
        if column == "msg_severity":
            return extracted.get("Severity", "") or ""
        if column == "msg_device_name":
            return extracted.get("Device Name", "") or extracted.get("Device", "") or ""
        if column == "level":
            return extracted.get("Level", "") or ""
        if column == "log_description":
            return extracted.get("Log Description", "") or ""
        if column == "subtype":
            return extracted.get("Subtype", "") or ""
    return ""

value_for_column = _value_for_column_from_views or _value_for_column_fallback

# ---------- vistas ----------

def realtime_page(request):
    try:
        _, _, alarms = _fetch_alarms_today_direct()
        ctx = build_realtime_context(alarms, value_for_column, tzname="America/Santiago")

        kpi_total = sum(ctx.get("severity_counts", {}).values())
        kpi_high  = (ctx.get("severity_counts", {}).get("high", 0) +
                     ctx.get("severity_counts", {}).get("critical", 0))
        kpi_dev   = len(ctx.get("device_counts", {}))

        page_ctx = {
            "kpi_total": kpi_total,
            "kpi_high":  kpi_high,
            "kpi_dispositivos": kpi_dev,
            **ctx
        }
        return render(request, "dashboard/realtime.html", page_ctx)
    except httpx.HTTPStatusError as e:
        return HttpResponseBadRequest(f"realtime_page error: HTTP {e.response.status_code}: {e}")
    except Exception as e:
        return HttpResponseBadRequest(f"realtime_page error: {type(e).__name__}: {e}")


def realtime_data(request):
    try:
        _, _, alarms = _fetch_alarms_today_direct()
        ctx = build_realtime_context(alarms, value_for_column, tzname="America/Santiago")
        return JsonResponse({"ok": True, "data": ctx}, json_dumps_params={"indent": 2})
    except httpx.HTTPStatusError as e:
        return HttpResponseBadRequest(f"realtime_data error: HTTP {e.response.status_code}: {e}")
    except Exception as e:
        return HttpResponseBadRequest(f"realtime_data error: {type(e).__name__}: {e}")


def _presence_summary(alarms, columns):
    total = len(alarms)
    cols_out = {}
    for col in columns:
        cnt = 0
        for a in alarms:
            try:
                val = value_for_column(a, col)
            except Exception:
                val = ""
            s = "" if val is None else (val if isinstance(val, str) else str(val))
            if s:
                cnt += 1
        cols_out[col] = {"non_empty": cnt, "percent": round((cnt / total * 100.0), 2) if total else 0.0}
    return {"total_rows": total, "columns": cols_out}


def debug_whitelist_today_direct(request):
    try:
        _, _, alarms = _fetch_alarms_today_direct()
        cols = getattr(v, "_WHITELIST_ORDERED", [
            "Action", "actions", "aotags", "severity",
            "msg_severity", "msg_device_name", "level", "log_description", "subtype",
            "eventtime", "alarmid",
        ])
        summary = _presence_summary(alarms, cols)
        return JsonResponse({"ok": True, "summary": summary, "sample_rows": alarms[:3]}, json_dumps_params={"indent": 2})
    except httpx.HTTPStatusError as e:
        return HttpResponseBadRequest(f"debug_whitelist_today_direct error: HTTP {e.response.status_code}: {e}")
    except Exception as e:
        return HttpResponseBadRequest(f"debug_whitelist_today_direct error: {type(e).__name__}: {e}")
