# dashboard/realtime_transform.py
from __future__ import annotations
from collections import defaultdict, Counter
from datetime import datetime
import pytz

NA = "N/A"

# ----------------- helpers (alineados a charts.py) -----------------
def _norm_sev(x):
    s = (str(x).strip() if x is not None else "")
    return s.lower() if s else "n/a"

def _norm_msgsev(x):
    s = (str(x).strip() if x is not None else "")
    return s.lower() if s else "n/a"

def _norm_act(x):
    s = (str(x).strip() if x is not None else "")
    return s if s else NA  # conserva casing

def _norm_dev(x):
    s = (str(x).strip() if x is not None else "")
    return s if s else NA  # conserva casing

def _norm_level(x):
    s = (str(x).strip() if x is not None else "")
    return s if s else NA  # conserva casing

def _norm_subtype(x):
    s = (str(x).strip() if x is not None else "")
    return s if s else NA  # conserva casing

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

def _transpose(m: dict[str, Counter]) -> dict[str, dict]:
    """Convierte A->(B->n) en B->(A->n)"""
    out = defaultdict(Counter)
    for a, per in m.items():
        for b, n in per.items():
            out[b][a] += int(n)
    return {k: dict(v) for k, v in out.items()}

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

    # por hora (claves de hora en STRING "00".."23")
    total_by_hour             = Counter()               # índice numérico 0..23 (para arrays 24)
    sev_by_hour               = defaultdict(Counter)    # "HH" -> sev(lc) -> n
    dev_by_hour               = defaultdict(Counter)    # "HH" -> device -> n
    act_by_hour               = defaultdict(Counter)    # "HH" -> action -> n
    level_by_hour             = defaultdict(Counter)    # "HH" -> level -> n
    subtype_by_hour           = defaultdict(Counter)    # "HH" -> subtype -> n
    msgsev_by_hour            = defaultdict(Counter)    # "HH" -> msgsev(lc) -> n

    # series por hora (para arrays de 24)
    sev_series_by_hour        = defaultdict(Counter)    # sev(lc)   -> hour(int) -> n
    dev_series_by_hour        = defaultdict(Counter)    # device    -> hour(int) -> n
    act_series_by_hour        = defaultdict(Counter)    # action    -> hour(int) -> n
    msgsev_series_by_hour     = defaultdict(Counter)    # msgsev(lc)-> hour(int) -> n

    # cruces
    device_by_action          = defaultdict(Counter)    # action -> device -> n
    action_by_device          = defaultdict(Counter)    # device -> action -> n

    device_by_severity        = defaultdict(Counter)    # device -> sev(lc) -> n
    device_by_level           = defaultdict(Counter)    # device -> level   -> n
    device_by_subtype         = defaultdict(Counter)    # device -> subtype -> n
    device_by_logdesc         = defaultdict(Counter)    # logdesc -> device -> n

    action_by_level           = defaultdict(Counter)    # level -> action -> n
    severity_by_level         = defaultdict(Counter)    # level -> sev(lc) -> n
    level_by_msgseverity      = defaultdict(Counter)    # msg(lc) -> level -> n
    msgseverity_by_level      = defaultdict(Counter)    # level -> msg(lc) -> n
    level_by_subtype          = defaultdict(Counter)    # subtype -> level -> n

    severity_by_subtype       = defaultdict(Counter)    # subtype -> sev(lc) -> n
    action_by_subtype         = defaultdict(Counter)    # subtype -> act     -> n
    msgseverity_by_subtype    = defaultdict(Counter)    # msg(lc) -> subtype -> n
    subtype_by_msgseverity    = defaultdict(Counter)    # subtype -> msg(lc) -> n

    action_by_msgseverity     = defaultdict(Counter)    # msg(lc) -> action -> n
    severity_by_msgseverity   = defaultdict(Counter)    # sev(lc) -> msg(lc) -> n
    device_by_msgseverity     = defaultdict(Counter)    # msg(lc) -> device -> n

    action_by_logdesc         = defaultdict(Counter)    # logdesc -> action -> n
    severity_by_logdesc       = defaultdict(Counter)    # logdesc -> sev(lc) -> n

    # cruces directos severidad <-> acción
    severity_by_action        = defaultdict(Counter)    # action -> sev(lc) -> n
    action_by_severity        = defaultdict(Counter)    # sev(lc) -> action -> n

    for a in alarms:
        dt = _extract_dt_local(a, value_for_column, tzname)
        hour = dt.hour if isinstance(dt, datetime) else None

        sev        = _norm_sev(        value_for_column(a, "severity"))
        msgsev     = _norm_msgsev(     value_for_column(a, "msg_severity"))
        device     = _norm_dev(        value_for_column(a, "msg_device_name"))
        level      = _norm_level(      value_for_column(a, "level"))
        subtype    = _norm_subtype(    value_for_column(a, "subtype"))
        action     = _norm_act(        value_for_column(a, "actions") or value_for_column(a, "Action"))
        logdesc    = (str(value_for_column(a, "log_description") or "").strip() or NA)

        if hour is not None:
            hs = f"{hour:02d}"

            total_by_hour[hour] += 1

            if sev:    sev_by_hour[hs][sev]         += 1
            if device: dev_by_hour[hs][device]      += 1
            if action: act_by_hour[hs][action]      += 1
            if level:  level_by_hour[hs][level]     += 1
            if subtype:subtype_by_hour[hs][subtype] += 1
            if msgsev: msgsev_by_hour[hs][msgsev]   += 1

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
            action_by_device[device][action] += 1
            device_by_action[action][device] += 1
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

        if sev and action:
            severity_by_action[action][sev] += 1
            action_by_severity[sev][action] += 1

    # ---------- construir salida ----------
    trend_labels = []
    trend_data   = []
    severity_trends = {}

    hour_labels = [f"{h:02d}" for h in range(24)]
    hour_data   = _series24(total_by_hour)
    trend_labels_hour = hour_labels
    trend_by_hour = {"total": hour_data} | _ensure_series24(sev_series_by_hour)

    _device_by_sev_full = _transpose(device_by_severity)  # sev -> device -> n

    # hour-series por subtype
    hour_series_by_subtype = defaultdict(lambda: [0] * 24)
    for hs, per in subtype_by_hour.items():
        try:
            h = int(hs)
        except Exception:
            continue
        for st, n in per.items():
            hour_series_by_subtype[st][h] += int(n)


    severity_counts_by_msg_severity = _transpose(severity_by_msgseverity)   # msg -> sev
    msg_severity_by_subtype_out     = {st: dict(c) for st, c in subtype_by_msgseverity.items()}   # subtype -> msg
    subtype_by_msg_severity_out     = {msg: dict(c) for msg, c in msgseverity_by_subtype.items()} # msg -> subtype


    level_to_device   = _transpose(device_by_level)     # level -> device -> n
    subtype_to_device = _transpose(device_by_subtype)   # subtype -> device -> n

   
    level_counts_by_subtype = {st: dict(c) for st, c in level_by_subtype.items()}

    subtype_counts_by_level = _transpose(level_by_subtype)

    out = {
        "trend_labels": trend_labels,
        "trend_data": trend_data,
        "severity_trends": severity_trends,

        "severity_counts": dict(severity_counts),

        "device_counts": dict(device_counts),
        "action_counts": dict(action_counts),

        "device_counts_by_severity": _device_by_sev_full,
        "device_counts_by_severity_full": _device_by_sev_full,

        "trend_by_device": _ensure_series24(dev_series_by_hour),
        "trend_by_action": _ensure_series24(act_series_by_hour),
        "top_devices": dict(sorted(device_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]),

        "hour_labels": hour_labels,
        "hour_data": hour_data,
        "severity_counts_by_hour": {h: dict(c) for h, c in sev_by_hour.items()},
        "device_counts_by_hour":   {h: dict(c) for h, c in dev_by_hour.items()},
        "device_counts_by_hour_full": {h: dict(c) for h, c in dev_by_hour.items()},
        "action_counts_by_hour":   {h: dict(c) for h, c in act_by_hour.items()},
        "trend_labels_hour": trend_labels_hour,
        "trend_by_hour": trend_by_hour,

        "device_counts_by_action": {act: dict(c) for act, c in device_by_action.items()},
        "action_counts_by_device": {dev: dict(c) for dev, c in action_by_device.items()},
        "action_counts_by_severity": {sev: dict(c) for sev, c in action_by_severity.items()},

        "msg_severity_counts": dict(msg_severity_counts),
        "device_counts_by_msg_severity": {msg: dict(c) for msg, c in device_by_msgseverity.items()},
        "action_counts_by_msg_severity": {msg: dict(c) for msg, c in action_by_msgseverity.items()},
        "severity_counts_by_msg_severity": severity_counts_by_msg_severity,
        "msg_severity_counts_by_hour": {h: dict(c) for h, c in msgsev_by_hour.items()},
        "trend_by_msg_severity": {msg: _series24(c) for msg, c in msgsev_series_by_hour.items()},

        "level_counts": dict(level_counts),

        # level/subtype -> { device: n }
        "device_counts_by_level": level_to_device,
        "action_counts_by_level": {lvl: dict(c) for lvl, c in action_by_level.items()},
        "severity_counts_by_level": {lvl: dict(c) for lvl, c in severity_by_level.items()},
        "trend_by_level": {lvl: _series24(level_by_hour[lvl]) for lvl in level_counts.keys()},
        "level_counts_by_hour": {h: dict(c) for h, c in level_by_hour.items()},

        # Ambos mapas disponibles:
        "subtype_counts_by_level": subtype_counts_by_level,     # level -> {subtype: n}
        "level_counts_by_subtype": level_counts_by_subtype,     # subtype -> {level: n}  

        "msg_severity_by_level": {lvl: dict(c) for lvl, c in msgseverity_by_level.items()},
        "level_by_msg_severity": {msg: dict(c) for msg, c in level_by_msgseverity.items()},

        "subtype_counts": dict(subtype_counts),
        "device_counts_by_subtype": subtype_to_device,          # subtype -> {device: n}
        "action_counts_by_subtype": {st: dict(c) for st, c in action_by_subtype.items()},
        "severity_counts_by_subtype": {st: dict(c) for st, c in severity_by_subtype.items()},
        "subtype_counts_by_hour": {h: dict(c) for h, c in subtype_by_hour.items()},
        "hour_series_by_subtype": {st: arr[:] for st, arr in hour_series_by_subtype.items()},
        "msg_severity_by_subtype": msg_severity_by_subtype_out,
        "subtype_by_msg_severity": subtype_by_msg_severity_out,

        "logdesc_counts": dict(logdesc_counts),
        "device_counts_by_logdesc": {ld: dict(c) for ld, c in device_by_logdesc.items()},
        "action_counts_by_logdesc": {ld: dict(c) for ld, c in action_by_logdesc.items()},
        "severity_counts_by_logdesc": {ld: dict(c) for ld, c in severity_by_logdesc.items()},
    }

    # ===== Aliases para selectors.js =====
    out.update({
        "sevByHourRaw":        {k: dict(v) for k, v in out.get("severity_counts_by_hour", {}).items()},
        "devByHourRaw":        {k: dict(v) for k, v in out.get("device_counts_by_hour", {}).items()},
        "actByHourNorm":       {k: dict(v) for k, v in out.get("action_counts_by_hour", {}).items()},
        "trendLabels":         out.get("trend_labels", []),
        "trendLabelsHour":     out.get("trend_labels_hour", []),
        "trendByHourRaw":      out.get("trend_by_hour", {}),
        "severityTrendsMap":   out.get("severity_trends", {}),

        "actionCountsRaw":     dict(action_counts),
        "deviceCountsAll":     dict(device_counts),

        "actionByDev":         out.get("action_counts_by_device", {}),
        "deviceByAction":      out.get("device_counts_by_action", {}),
        "sevToAct":            out.get("action_counts_by_severity", {}),
        "actToSev":            {act: dict(c) for act, c in severity_by_action.items()},

        "msgSeverityCountsRaw":           dict(msg_severity_counts),
        "deviceByMsgSeverityRaw":         out.get("device_counts_by_msg_severity", {}),
        "actionByMsgSeverityRaw":         out.get("action_counts_by_msg_severity", {}),
        "severityByMsgSeverityRaw":       out.get("severity_counts_by_msg_severity", {}),
        "subtypeByMsgSeverityRaw":        out.get("subtype_by_msg_severity", {}),
        "msgSeverityBySubtypeRaw":        out.get("msg_severity_by_subtype", {}),
        "msgSeverityByHourRaw":           {h: dict(c) for h, c in msgsev_by_hour.items()},
        "msgSeverityByLevelRaw":          out.get("msg_severity_by_level", {}),
        "levelByMsgSeverityRaw":          out.get("level_by_msg_severity", {}),

        "levelCountsRaw":                 dict(level_counts),
        "deviceByLevelRaw":               out.get("device_counts_by_level", {}),
        "actionByLevelRaw":               out.get("action_counts_by_level", {}),
        "severityByLevelRaw":             out.get("severity_counts_by_level", {}),
        "levelCountsByHourRaw":           {h: dict(c) for h, c in level_by_hour.items()},

        # ⬇ alias correcto para Subtype → Level
        "levelBySubtypeRaw":              out.get("level_counts_by_subtype", {}),  #  subtype -> {level: n}

        "subtypeCountsRaw":               dict(subtype_counts),
        "deviceBySubtypeRaw":             out.get("device_counts_by_subtype", {}),
        "actionBySubtypeRaw":             out.get("action_counts_by_subtype", {}),
        "severityBySubtypeRaw":           out.get("severity_counts_by_subtype", {}),
        "subtypeByHourRaw":               {h: dict(c) for h, c in subtype_by_hour.items()},

        "logDescCountsRaw":               dict(logdesc_counts),
        "deviceByLogDescRaw":             out.get("device_counts_by_logdesc", {}),
        "actionByLogDescRaw":             out.get("action_counts_by_logdesc", {}),
        "severityByLogDescRaw":           out.get("severity_counts_by_logdesc", {}),

        "hourSeriesBySubtypeRaw":         out.get("hour_series_by_subtype", {}),
    })

    return out

