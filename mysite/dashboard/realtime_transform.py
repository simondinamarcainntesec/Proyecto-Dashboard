# dashboard/realtime_transform.py
from __future__ import annotations
from collections import defaultdict, Counter
from datetime import datetime
import pytz

# ----------------- helpers -----------------
def _norm(x):
    if x is None:
        return ""
    return str(x).strip()

def _norm_lc(x):
    return _norm(x).lower()

def _extract_dt_local(alarm, value_for_column, tzname="America/Santiago"):
    dt = value_for_column(alarm, "eventtime")
    if isinstance(dt, datetime):
        return dt
    try:
        ms = int(alarm.get("eventtime"))
        dt_utc = datetime.fromtimestamp(ms/1000.0, tz=pytz.utc)
        return dt_utc.astimezone(pytz.timezone(tzname))
    except Exception:
        return None

def _series24(counter_by_hour: Counter) -> list[int]:
    return [int(counter_by_hour.get(h, 0)) for h in range(24)]

def _ensure_series24(nested_counter: dict[str, Counter]) -> dict[str, list[int]]:
    out = {}
    for k, c in nested_counter.items():
        out[k] = _series24(c)
    return out

# ---------- transformación principal ----------
def build_realtime_context(alarms: list[dict], value_for_column, tzname="America/Santiago") -> dict:
    # Totales simples
    severity_counts           = Counter()
    action_counts             = Counter()
    device_counts             = Counter()
    level_counts              = Counter()
    subtype_counts            = Counter()
    logdesc_counts            = Counter()
    msg_severity_counts       = Counter()

    # por hora
    total_by_hour             = Counter()
    sev_by_hour               = defaultdict(Counter)    # hour -> sev -> n
    dev_by_hour               = defaultdict(Counter)    # hour -> dev -> n
    act_by_hour               = defaultdict(Counter)    # hour -> action -> n
    level_by_hour             = defaultdict(Counter)    # hour -> level -> n
    subtype_by_hour           = defaultdict(Counter)    # hour -> subtype -> n
    msgsev_by_hour            = defaultdict(Counter)    # hour -> msgsev -> n

    # series por hora (para trendBy*)
    sev_series_by_hour        = defaultdict(Counter)    # sev   -> hour -> n
    dev_series_by_hour        = defaultdict(Counter)    # dev   -> hour -> n
    act_series_by_hour        = defaultdict(Counter)    # act   -> hour -> n
    msgsev_series_by_hour     = defaultdict(Counter)    # msg   -> hour -> n

    # cruces
    device_by_action          = defaultdict(Counter)    # device -> action -> n
    action_by_device          = defaultdict(Counter)    # action -> device -> n

    device_by_severity        = defaultdict(Counter)    # device -> sev -> n
    device_by_level           = defaultdict(Counter)    # device -> level -> n
    device_by_subtype         = defaultdict(Counter)    # device -> subtype -> n
    device_by_logdesc         = defaultdict(Counter)    # logdesc -> device -> n

    action_by_level           = defaultdict(Counter)    # level -> action -> n
    severity_by_level         = defaultdict(Counter)    # level -> sev -> n
    level_by_msgseverity      = defaultdict(Counter)    # msg   -> level -> n
    msgseverity_by_level      = defaultdict(Counter)    # level -> msg   -> n
    level_by_subtype          = defaultdict(Counter)    # subtype -> level -> n

    severity_by_subtype       = defaultdict(Counter)    # subtype -> sev -> n
    action_by_subtype         = defaultdict(Counter)    # subtype -> act -> n
    msgseverity_by_subtype    = defaultdict(Counter)    # msg -> subtype -> n
    subtype_by_msgseverity    = defaultdict(Counter)    # subtype -> msg -> n

    action_by_msgseverity     = defaultdict(Counter)    # msg -> act -> n
    severity_by_msgseverity   = defaultdict(Counter)    # sev -> msg -> n
    device_by_msgseverity     = defaultdict(Counter)    # msg -> device -> n

    action_by_logdesc         = defaultdict(Counter)    # logdesc -> action -> n
    severity_by_logdesc       = defaultdict(Counter)    # logdesc -> sev -> n

    for a in alarms:
        dt = _extract_dt_local(a, value_for_column, tzname)
        hour = dt.hour if isinstance(dt, datetime) else None

        sev        = _norm_lc(value_for_column(a, "severity"))
        msgsev     = _norm_lc(value_for_column(a, "msg_severity"))
        device     = _norm(value_for_column(a, "msg_device_name"))
        level      = _norm_lc(value_for_column(a, "level"))
        subtype    = _norm_lc(value_for_column(a, "subtype"))
        # usar 'actions' y caer a 'Action'
        action     = _norm_lc(value_for_column(a, "actions") or value_for_column(a, "Action"))
        logdesc    = _norm(value_for_column(a, "log_description"))

        if hour is not None:
            total_by_hour[hour] += 1
            if sev:    sev_by_hour[hour][sev]         += 1
            if device: dev_by_hour[hour][device]      += 1
            if action: act_by_hour[hour][action]      += 1
            if level:  level_by_hour[hour][level]     += 1
            if subtype:subtype_by_hour[hour][subtype] += 1
            if msgsev: msgsev_by_hour[hour][msgsev]   += 1

            if sev:    sev_series_by_hour[sev][hour]      += 1
            if device: dev_series_by_hour[device][hour]   += 1
            if action: act_series_by_hour[action][hour]   += 1
            if msgsev: msgsev_series_by_hour[msgsev][hour]+= 1

        if sev:        severity_counts[sev]       += 1
        if msgsev:     msg_severity_counts[msgsev]+= 1
        if action:     action_counts[action]      += 1
        if device:     device_counts[device]      += 1
        if level:      level_counts[level]        += 1
        if subtype:    subtype_counts[subtype]    += 1
        if logdesc:    logdesc_counts[logdesc]    += 1

        if device and action:
            device_by_action[device][action] += 1
            action_by_device[action][device] += 1
        if device and sev:
            device_by_severity[device][sev] += 1
        if device and level:
            device_by_level[device][level] += 1
        if device and subtype:
            device_by_subtype[device][subtype] += 1
        if device and msgsev:
            device_by_msgseverity[msgsev][device] += 1
        if logdesc and device:
            device_by_logdesc[logdesc][device] += 1

        if level and action:
            action_by_level[level][action] += 1
        if level and sev:
            severity_by_level[level][sev] += 1
        if level and msgsev:
            msgseverity_by_level[level][msgsev] += 1
            level_by_msgseverity[msgsev][level] += 1
        if subtype and level:
            level_by_subtype[subtype][level] += 1

        if subtype and sev:
            severity_by_subtype[subtype][sev] += 1
        if subtype and action:
            action_by_subtype[subtype][action] += 1
        if msgsev and subtype:
            msgseverity_by_subtype[msgsev][subtype] += 1
            subtype_by_msgseverity[subtype][msgsev] += 1

        if action and msgsev:
            action_by_msgseverity[msgsev][action] += 1
        if sev and msgsev:
            severity_by_msgseverity[sev][msgsev] += 1

        if logdesc and action:
            action_by_logdesc[logdesc][action] += 1
        if logdesc and sev:
            severity_by_logdesc[logdesc][sev] += 1

    # ---------- construir salida con NOMBRES HISTÓRICOS ----------
    # trend por día (histórico usa esto; en realtime lo dejamos vacío/coherente)
    trend_labels = []           # hoy no tiene sentido por días
    trend_data   = []           # idem
    severity_trends = {}        # idem (front lo tolera si está vacío)

    # Hourly
    hour_labels = [f"{h:02d}" for h in range(24)]
    hour_data   = _series24(total_by_hour)
    trend_labels_hour = hour_labels
    trend_by_hour = {"total": hour_data} | _ensure_series24(sev_series_by_hour)

    # Estructuras “Raw” que TU JS espera (nombres exactos)
    out = {
        # === trend (hist) ===
        "trend_labels": trend_labels,
        "trend_data": trend_data,
        "severity_trends": severity_trends,

        # === severidad (donut / KPI) ===
        "severity_counts": dict(severity_counts),

        # === devices / acciones totales ===
        "device_counts": dict(device_counts),
        "action_counts": dict(action_counts),

        # === device-by-severity (dos variantes que usa selectors) ===
        "device_counts_by_severity": {d: dict(c) for d, c in device_by_severity.items()},
        "device_counts_by_severity_full": {
            sev: {dev: cnt for dev, cnt in devs.items()}
            for sev, devs in _transpose(device_by_severity).items()
        },

        # === trends por device / action (series por hora) ===
        "trend_by_device": _ensure_series24(dev_series_by_hour),
        "trend_by_action": _ensure_series24(act_series_by_hour),
        "top_devices": dict(sorted(device_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]),

        # === por hora ===
        "hour_labels": hour_labels,
        "hour_data": hour_data,
        "severity_counts_by_hour": {h: dict(c) for h, c in sev_by_hour.items()},
        "device_counts_by_hour":   {h: dict(c) for h, c in dev_by_hour.items()},
        "device_counts_by_hour_full": {h: dict(c) for h, c in dev_by_hour.items()},
        "action_counts_by_hour":   {h: dict(c) for h, c in act_by_hour.items()},
        "trend_labels_hour": trend_labels_hour,
        "trend_by_hour": trend_by_hour,

        # === acciones / cruces ===
        "device_counts_by_action": {d: dict(c) for d, c in device_by_action.items()},
        "action_counts_by_device": {a: dict(c) for a, c in action_by_device.items()},
        "action_counts_by_severity": {a: dict(c) for a, c in _transpose(severity_by_msgseverity).items()},  # compat

        # === msg_severity ===
        "msg_severity_counts": dict(msg_severity_counts),
        "device_counts_by_msg_severity": {msg: dict(c) for msg, c in device_by_msgseverity.items()},
        "action_counts_by_msg_severity": {msg: dict(c) for msg, c in action_by_msgseverity.items()},
        "severity_counts_by_msg_severity": {sev: dict(c) for sev, c in severity_by_msgseverity.items()},
        "msg_severity_counts_by_hour": {msg: _series24(c) for msg, c in msgsev_series_by_hour.items()},
        "trend_by_msg_severity": {msg: _series24(c) for msg, c in msgsev_series_by_hour.items()},

        # === level ===
        "level_counts": dict(level_counts),
        "device_counts_by_level": {d: dict(c) for d, c in device_by_level.items()},
        "action_counts_by_level": {lvl: dict(c) for lvl, c in action_by_level.items()},
        "severity_counts_by_level": {lvl: dict(c) for lvl, c in severity_by_level.items()},
        "trend_by_level": {lvl: _series24(level_by_hour[lvl]) for lvl in level_counts.keys()},
        "level_counts_by_hour": {h: dict(c) for h, c in level_by_hour.items()},
        "subtype_counts_by_level": _transpose(level_by_subtype),
        "msg_severity_by_level": {lvl: dict(c) for lvl, c in msgseverity_by_level.items()},
        "level_by_msg_severity": {msg: dict(c) for msg, c in level_by_msgseverity.items()},

        # === subtype ===
        "subtype_counts": dict(subtype_counts),
        "device_counts_by_subtype": {d: dict(c) for d, c in device_by_subtype.items()},
        "action_counts_by_subtype": {s: dict(c) for s, c in action_by_subtype.items()},
        "severity_counts_by_subtype": {s: dict(c) for s, c in severity_by_subtype.items()},
        "trend_by_subtype": {s: _series24(subtype_by_hour[s]) for s in subtype_counts.keys()},
        "subtype_counts_by_hour": {h: dict(c) for h, c in subtype_by_hour.items()},
        "level_counts_by_subtype": _transpose(level_by_subtype),
        "msg_severity_by_subtype": {msg: dict(c) for msg, c in msgseverity_by_subtype.items()},
        "subtype_by_msg_severity": {s: dict(c) for s, c in subtype_by_msgseverity.items()},
        "hour_series_by_subtype": {s: _series24(subtype_by_hour[s]) for s in subtype_counts.keys()},

        # === log description ===
        "logdesc_counts": dict(logdesc_counts),
        "device_counts_by_logdesc": {ld: dict(c) for ld, c in device_by_logdesc.items()},
        "action_counts_by_logdesc": {ld: dict(c) for ld, c in action_by_logdesc.items()},
        "severity_counts_by_logdesc": {ld: dict(c) for ld, c in severity_by_logdesc.items()},
    }

    # Aliases EXACTOS que usa tu front histórico (variables “Raw”)
    out.update({
        "sevByHourRaw":        {k: dict(v) for k, v in out["severity_counts_by_hour"].items()},
        "devByHourRaw":        {k: dict(v) for k, v in out["device_counts_by_hour"].items()},
        "actByHourNorm":       {k: dict(v) for k, v in out["action_counts_by_hour"].items()},
        "trendLabels":         out["trend_labels"],
        "trendLabelsHour":     out["trend_labels_hour"],
        "trendByHourRaw":      out["trend_by_hour"],
        "severityTrendsMap":   out["severity_trends"],

        "actionCountsRaw":     dict(action_counts),
        "deviceCountsAll":     dict(device_counts),

        "actionByDev":         out["action_counts_by_device"],
        "sevToAct":            out["action_counts_by_severity"],

        "msgSeverityCountsRaw":           dict(msg_severity_counts),
        "deviceByMsgSeverityRaw":         out["device_counts_by_msg_severity"],
        "actionByMsgSeverityRaw":         out["action_counts_by_msg_severity"],
        "severityByMsgSeverityRaw":       out["severity_counts_by_msg_severity"],
        "msgSeverityByHourRaw":           {h: dict(c) for h, c in msgsev_by_hour.items()},
        "msgSeverityByLevelRaw":          out["msg_severity_by_level"],
        "levelByMsgSeverityRaw":          out["level_by_msg_severity"],
        "msgSeverityBySubtypeRaw":        out["msg_severity_by_subtype"],

        "levelCountsRaw":                 dict(level_counts),
        "deviceByLevelRaw":               out["device_counts_by_level"],
        "actionByLevelRaw":               out["action_counts_by_level"],
        "severityByLevelRaw":             out["severity_counts_by_level"],
        "levelCountsByHourRaw":           {h: dict(c) for h, c in level_by_hour.items()},
        "levelBySubtypeRaw":              out["level_counts_by_subtype"],

        "subtypeCountsRaw":               dict(subtype_counts),
        "deviceBySubtypeRaw":             out["device_counts_by_subtype"],
        "actionBySubtypeRaw":             out["action_counts_by_subtype"],
        "severityBySubtypeRaw":           out["severity_counts_by_subtype"],
        "subtypeByHourRaw":               {h: dict(c) for h, c in subtype_by_hour.items()},

        "logDescCountsRaw":               dict(logdesc_counts),
        "deviceByLogDescRaw":             out["device_counts_by_logdesc"],
        "actionByLogDescRaw":             out["action_counts_by_logdesc"],
        "severityByLogDescRaw":           out["severity_counts_by_logdesc"],

        "hourSeriesBySubtypeRaw":         out["hour_series_by_subtype"],
    })

    return out


def _transpose(m: dict[str, Counter]) -> dict[str, dict]:
    """Convierte A->(B->n) en B->(A->n)"""
    out = defaultdict(Counter)
    for a, per in m.items():
        for b, n in per.items():
            out[b][a] += int(n)
    return {k: dict(v) for k, v in out.items()}
