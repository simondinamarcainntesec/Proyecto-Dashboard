# inyeccion_api/utils.py
from __future__ import annotations

import json
import re
from datetime import datetime

import pytz

from inyeccion_api.models import Alarm


# ========== HELPERS GENERALES (MISMOS QUE REALTIME) ==========


def _get_value_case_insensitive(d: dict, key: str):
    if not isinstance(d, dict):
        return ""
    if key in d:
        return d[key]
    kl = key.lower()
    for k, val in d.items():
        if isinstance(k, str) and k.lower() == kl:
            return val
    return ""


def _to_datetime_santiago(timestamp_ms):
    """
    Convierte un timestamp en ms (UTC) a datetime tz-aware en America/Santiago.
    """
    if not timestamp_ms:
        return ""
    try:
        ts_s = int(timestamp_ms) / 1000
        utc_dt = datetime.fromtimestamp(ts_s, tz=pytz.utc)
        return utc_dt.astimezone(pytz.timezone("America/Santiago"))
    except Exception:
        return ""


_KEYVAL_ROW_REGEX = re.compile(
    r"<td[^>]*>\s*([^:<][^<]*?)\s*</td>\s*"
    r"<td[^>]*>\s*([\s\S]*?)\s*</td>",
    re.I,
)
_LINE_REGEX = re.compile(r"^\s*([^:]{1,64})\s*:\s*(.+)\s*$")


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "", flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def _norm_key(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s.strip())
    return s.lower()


def _extract_kv_generic(raw_block) -> dict:
    """
    Parser genérico para:
      - dicts
      - JSON
      - tablas HTML (FortiAnalyzer)
      - líneas 'key: value'
      - línea larga tipo Log360 'key=value key2=value2 ...'
    """
    if not raw_block:
        return {}

    # dict directo
    if isinstance(raw_block, dict):
        return {
            _norm_key(k): _strip_html(str(v))
            for k, v in raw_block.items()
            if isinstance(k, str)
        }

    s = str(raw_block)

    # 1) Intentar JSON
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return {
                _norm_key(k): _strip_html(str(v))
                for k, v in obj.items()
            }
    except Exception:
        pass

    # 2) Tablas HTML FortiAnalyzer
    pairs: dict[str, str] = {}
    for k, vv in _KEYVAL_ROW_REGEX.findall(s):
        key = _norm_key(k)
        val = _strip_html(vv)
        pairs[key] = val
    if pairs:
        return pairs

    # 3) Formato "key: value"
    kv: dict[str, str] = {}
    for line in s.splitlines():
        m = _LINE_REGEX.match(line)
        if m:
            key = _norm_key(m.group(1))
            val = _strip_html(m.group(2))
            kv[key] = val

    # 4) Formato "key=value" (Log360)
    if "=" in s:
        clean = _strip_html(s)
        for token in clean.replace("\n", " ").split(" "):
            if "=" in token:
                try:
                    k, v = token.split("=", 1)
                    k = _norm_key(k)
                    v = v.strip().strip('"')
                    if k:
                        kv[k] = v
                except Exception:
                    pass

    # fallback para Log Description si viene embebido
    if "log description" not in kv:
        m = re.search(
            r"log description[:\-]\s*([\s\S]+?)(?:<|$)",
            s,
            re.I,
        )
        if m:
            kv["log description"] = _strip_html(m.group(1))

    return kv


def _message_extract_multiple_sources(alarm: dict, wanted: list[str]) -> dict:
    """
    Combina info tanto de 'log_details' como de 'message',
    normalizando claves y devolviendo solo las pedidas en 'wanted'.
    Aplica la misma lógica de severidad que en el realtime:
    severity / Severity / severity2 / level.
    """
    detail_keys_candidates = [
        "log_details",
        "logdetail",
        "log-details",
        "log detail",
        "logdetails",
    ]
    merged: dict[str, str] = {}

    for dk in detail_keys_candidates:
        block = _get_value_case_insensitive(alarm, dk)
        d = _extract_kv_generic(block)
        if d:
            merged.update(d)

    msg_block = _get_value_case_insensitive(alarm, "message")
    dmsg = _extract_kv_generic(msg_block)
    if dmsg:
        merged.update(dmsg)

    # Aliases
    device_aliases = ["device name", "device", "devicename", "devname"]
    subtype_aliases = ["subtype", "sub type"]
    severity_aliases = ["severity", "severity2", "level"]

    out = {w: "" for w in wanted}
    for w in wanted:
        k = _norm_key(w)
        val = merged.get(k, "")

        # Device name
        if not val and k == "device name":
            for ak in device_aliases:
                if merged.get(ak):
                    val = merged[ak]
                    break

        # Subtype
        if not val and k == "subtype":
            for ak in subtype_aliases:
                if merged.get(ak):
                    val = merged[ak]
                    break

        # Severity (misma lógica que en realtime)
        if not val and k == "severity":
            for ak in severity_aliases:
                if merged.get(ak):
                    val = merged[ak]
                    break

        out[w] = val or ""

    return out


def _format_aotags(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        s = value.strip()
        try:
            obj = json.loads(s)
            value = obj
        except json.JSONDecodeError:
            cleaned = s.strip().strip('[]\"')
            return cleaned if cleaned else ""
    if isinstance(value, list):
        return ", ".join(
            str(t).strip()
            for t in value
            if isinstance(t, (str, int)) and str(t).strip()
        )
    return str(value)


# ========== MAPEO API → MODELO (USADO POR LA INGESTA) ==========


def _map_api_alarm_to_model(a: dict) -> Alarm | None:
    """
    Construye un objeto Alarm (no guardado) desde un dict de la API.

    Usa EXACTAMENTE la misma lógica de parseo que el realtime para:
      - device_name
      - msg_severity
      - level
      - log_description
      - subtype

    Y además:
      - Usa alertid / alarmid como clave única.
      - Convierte eventtime a timezone America/Santiago.
      - Normaliza aotags en un string.
    """
    if not isinstance(a, dict):
        return None

    # === ID único (alertid / alarmid) ===
    raw_alertid = (
        _get_value_case_insensitive(a, "alertid")
        or _get_value_case_insensitive(a, "alarmid")
        or _get_value_case_insensitive(a, "Alertid")
    )
    if not raw_alertid:
        return None

    # === Tiempo y tags ===
    event_time = _to_datetime_santiago(
        _get_value_case_insensitive(a, "eventtime")
    )
    tags = _format_aotags(_get_value_case_insensitive(a, "aotags"))

    # Severidad "principal" (tal como viene en la alarma)
    severity = (
        _get_value_case_insensitive(a, "severity")
        or _get_value_case_insensitive(a, "Severity")
        or ""
    )

    # Action / actions directo desde el dict
    action = _get_value_case_insensitive(a, "Action") or ""
    actions = _get_value_case_insensitive(a, "actions") or ""

    # ========= PARSEO DETALLADO (MISMO ENFOQUE QUE REALTIME) =========
    extracted = _message_extract_multiple_sources(
        a,
        wanted=[
            "Severity",
            "Device Name",
            "Device",
            "Level",
            "Log Description",
            "Subtype",
        ],
    )

    # msg_severity (Severity/log severity)
    msg_severity = (
        extracted.get("Severity", "")
        or _get_value_case_insensitive(a, "severity2")
        or ""
    )

    # Dispositivo
    device_name = (
        extracted.get("Device Name", "")
        or extracted.get("Device", "")
        or _get_value_case_insensitive(a, "devname")
        or _get_value_case_insensitive(a, "device")
        or ""
    )

    # level
    level = (
        extracted.get("Level", "")
        or _get_value_case_insensitive(a, "level")
        or ""
    )

    # log_description
    log_description = (
        extracted.get("Log Description", "")
        or _get_value_case_insensitive(a, "log_description")
        or ""
    )

    # subtype
    subtype = (
        extracted.get("Subtype", "")
        or _get_value_case_insensitive(a, "subtype")
        or ""
    )

    # === Construimos la instancia (NO guardada aún) ===
    return Alarm(
        alertid=str(raw_alertid),
        event_time=event_time,
        tags=tags,
        severity=severity,
        msg_severity=msg_severity,
        device_name=device_name,
        action=action,
        actions=actions,
        level=level,
        log_description=log_description,
        subtype=subtype,
    )
