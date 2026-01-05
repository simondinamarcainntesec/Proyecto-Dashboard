# inyeccion_api/utils.py
from __future__ import annotations

import json
import re
import logging
from datetime import datetime

import pytz

from inyeccion_api.models import Alarm

logger = logging.getLogger(__name__)

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


# ===================== HARMONY (bunion_harmony) =====================

_UUID_REGEX = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.I,
)


def _is_bunion_harmony(alarm: dict) -> bool:
    app = _get_value_case_insensitive(alarm, "application")
    return str(app or "").strip().lower() == "bunion_harmony"


def _harmony_clean_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = re.sub(r"&nbsp;", " ", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"</?div[^>]*>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _harmony_rx_one(html: str, pattern: str) -> str:
    m = re.search(pattern, html, flags=re.I | re.S)
    return _harmony_clean_text(m.group(1)) if m else ""


def _parse_harmony_message(html: str) -> dict:
    """
    Extrae campos útiles desde el HTML "Harmony Endpoint Custom Alert Notification".
    SOLO usar cuando alarm.application == bunion_harmony.
    Devuelve dict con claves normalizadas para _message_extract_multiple_sources.
    """
    if not html:
        return {}

    # Tenant / Service / Importance
    tenant = (
        _harmony_rx_one(html, r"Tenant:[\s\S]*?<a[^>]*>(.*?)</a>")
        or _harmony_rx_one(html, r"Tenant:\s*([\s\S]*?)</p>")
    )
    service = (
        _harmony_rx_one(html, r"Service Name:[\s\S]*?<a[^>]*>(.*?)</a>")
        or _harmony_rx_one(html, r"Service Name:\s*([\s\S]*?)</p>")
    )
    importance = (
        _harmony_rx_one(html, r"Importance:[\s\S]*?<a[^>]*>(.*?)</a>")
        or _harmony_rx_one(html, r"Importance:\s*([\s\S]*?)</p>")
    )

    # Summary: "Alert matched 3 times on 1 device" o "different devices"
    match_count = ""
    device_count = ""
    m = re.search(
        r"Alert matched\s*(\d+)\s*times\s*on\s*(\d+)\s*(?:different\s*)?devices?",
        html,
        flags=re.I,
    )
    if m:
        match_count = m.group(1)
        device_count = m.group(2)

    # Custom alert / Tag / Matched on
    custom_alert = _harmony_rx_one(html, r"Custom alert name:\s*(.*?)</p>")
    tag = _harmony_rx_one(html, r"Tag:\s*(.*?)</p>")
    matched_on = _harmony_rx_one(html, r"Matched on:\s*(.*?)</p>")

    # URL
    threat_url = _harmony_rx_one(
        html,
        r'href="(https://portal\.checkpoint\.com/Dashboard/endpoint/ThreatHunting#[^"]+)"',
    )

    # Tabla device-table
    devices = []
    statuses = []
    report_ids = []
    events = []

    # OJO: algunos correos usan class="x_...device-table"
    table_html = ""
    tm = re.search(
        r"<table[^>]*class=\"[^\"]*device-table[^\"]*\"[^>]*>([\s\S]*?)</table>",
        html,
        flags=re.I,
    )
    if tm:
        table_html = tm.group(1) or ""

    # Filas: 4 <td>
    if table_html:
        row_re = re.compile(
            r"<tr[^>]*>\s*"
            r"<td[^>]*>([\s\S]*?)</td>\s*"
            r"<td[^>]*>([\s\S]*?)</td>\s*"
            r"<td[^>]*>([\s\S]*?)</td>\s*"
            r"<td[^>]*>([\s\S]*?)</td>\s*"
            r"</tr>",
            flags=re.I,
        )
        for r in row_re.findall(table_html):
            rid = _harmony_clean_text(r[0])
            dev = _harmony_clean_text(r[1])
            st = _harmony_clean_text(r[2])
            evtime = _harmony_clean_text(r[3])

            if not rid or not _UUID_REGEX.search(rid):
                continue

            report_ids.append(rid)
            if dev:
                devices.append(dev)
            if st:
                statuses.append(st)

            events.append(
                {
                    "report_id": rid,
                    "device_name": dev,
                    "attack_status": st,
                    "event_time_gmt": evtime,
                }
            )

    # Uniq preservando orden
    def uniq_keep_order(seq):
        seen = set()
        out = []
        for x in seq:
            if not x:
                continue
            k = str(x)
            if k in seen:
                continue
            seen.add(k)
            out.append(k)
        return out

    devices_u = uniq_keep_order(devices)
    statuses_u = uniq_keep_order(statuses)
    report_ids_u = uniq_keep_order(report_ids)

    # Elegimos "device principal" para realtime/histórico
    primary_device = devices_u[0] if devices_u else ""

    # Level: attack status (si hay varios, join)
    level = ", ".join(statuses_u) if statuses_u else ""

    # Subtype: custom alert name (más útil que "create" del recent_activities)
    subtype = custom_alert or tag or "Harmony"

    # msg_severity: importance (en minúsculas)
    msg_sev = (importance or "").strip().lower()

    # log_description: armar algo útil
    desc_parts = []
    if tenant:
        desc_parts.append(f"Tenant={tenant}")
    if service:
        desc_parts.append(f"Service={service}")
    if importance:
        desc_parts.append(f"Importance={importance}")
    if custom_alert:
        desc_parts.append(f"Alert={custom_alert}")
    if tag:
        desc_parts.append(f"Tag={tag}")
    if match_count and device_count:
        desc_parts.append(f"Matched={match_count} on {device_count} device(s)")
    if devices_u:
        desc_parts.append(f"Devices={','.join(devices_u)}")
    if statuses_u:
        desc_parts.append(f"Status={','.join(statuses_u)}")
    if report_ids_u:
        rid_join = ",".join(report_ids_u[:10])
        if len(report_ids_u) > 10:
            rid_join += "..."
        desc_parts.append(f"ReportIDs={rid_join}")
    if matched_on:
        desc_parts.append(f"Rule={matched_on}")
    if threat_url:
        desc_parts.append("ThreatHuntingURL=available")

    log_description = " | ".join(desc_parts).strip()

    merged = {
        "tenant": tenant,
        "service name": service,
        "importance": importance,
        "severity": msg_sev,                 # para msg_severity
        "device name": primary_device,       # para msg_device_name
        "level": level,                      # para level
        "subtype": subtype,                  # para subtype
        "log description": log_description,  # para log_description
        "tag": tag,
        "custom alert name": custom_alert,
        "matched on": matched_on,
        "threat hunting url": threat_url,
        "match count": match_count,
        "device count": device_count,
        "events": events,
    }
    return merged


def _message_extract_multiple_sources(alarm: dict, wanted: list[str]) -> dict:
    """
    Combina info tanto de 'log_details' como de 'message',
    normalizando claves y devolviendo solo las pedidas en 'wanted'.
    Aplica la misma lógica de severidad que en el realtime:
    severity / Severity / severity2 / level.

    ✅ NUEVO: Para bunion_harmony parsea el HTML del message y lo integra al merged.
    """
    detail_keys_candidates = [
        "log_details",
        "logdetail",
        "log-details",
        "log detail",
        "logdetails",
    ]
    merged: dict[str, str] = {}

    # ✅ PARSEO ESPECÍFICO SOLO SI application == bunion_harmony
    if _is_bunion_harmony(alarm):
        raw_html = _get_value_case_insensitive(alarm, "message")
        if isinstance(raw_html, str) and raw_html:
            try:
                merged.update(_parse_harmony_message(raw_html))
            except Exception as e:
                logger.exception("[HISTORICO][HARMONY] Error parseando HTML: %s", e)

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
