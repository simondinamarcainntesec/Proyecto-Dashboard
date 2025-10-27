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
    dt_val = value_for_column(alarm, "eventtime") # Use the accessor function
    if isinstance(dt_val, datetime):
        # If accessor already returns timezone-aware datetime in correct TZ
        if dt_val.tzinfo is not None and hasattr(dt_val.tzinfo, 'zone') and dt_val.tzinfo.zone == tzname:
             return dt_val
        # If it's aware but different TZ, convert
        elif dt_val.tzinfo is not None:
             return dt_val.astimezone(pytz.timezone(tzname))
        # If it's naive, assume UTC (common case) and convert
        else:
             try:
                 # Attempt to localize assuming UTC if naive
                 return pytz.utc.localize(dt_val).astimezone(pytz.timezone(tzname))
             except ValueError: # Handle cases where dt_val might already be localized implicitly
                 try:
                    # Try assuming it's already local naive time
                    local_tz = pytz.timezone(tzname)
                    aware_dt = local_tz.localize(dt_val, is_dst=None) # Let pytz handle DST
                    return aware_dt
                 except Exception: # Broad exception if localization fails
                    return None # Give up on naive datetime

    # Try parsing from int (milliseconds timestamp)
    try:
        # Ensure dt_val is not None before int conversion
        if dt_val is None:
            raise ValueError("Timestamp is None")
        ms = int(dt_val)
        # Check for reasonable timestamp range if needed
        dt_utc = datetime.fromtimestamp(ms/1000.0, tz=pytz.utc)
        return dt_utc.astimezone(pytz.timezone(tzname))
    except (ValueError, TypeError, OverflowError):
        pass # Not a valid int timestamp or None

    # Try parsing from string (ISO 8601 or similar)
    if isinstance(dt_val, str):
        try:
            dt_val_processed = dt_val.strip()
            # Handle 'Z' for UTC
            if dt_val_processed.endswith('Z'):
                # Ensure microseconds are handled correctly if present
                if '.' in dt_val_processed:
                    dt_part, micro_part = dt_val_processed[:-1].split('.', 1)
                    micro_part = micro_part[:6] # Truncate to 6 digits
                    dt_val_iso = f"{dt_part}.{micro_part}+00:00"
                else:
                    dt_val_iso = dt_val_processed[:-1] + '+00:00'
                dt_utc_aware = datetime.fromisoformat(dt_val_iso)

            # Handle timezone offsets like +00:00 or -03:00
            elif '+' in dt_val_processed[-6:] or (':' in dt_val_processed[-6:] and '-' in dt_val_processed[-6:]):
                 dt_utc_aware = datetime.fromisoformat(dt_val_processed)
            # Assume local time if no timezone info and matches expected format
            else:
                 try:
                     dt_naive = datetime.fromisoformat(dt_val_processed)
                     # Assume the naive string represents time in the target timezone
                     local_tz = pytz.timezone(tzname)
                     dt_utc_aware = local_tz.localize(dt_naive, is_dst=None) # Let pytz handle DST ambiguity
                 except ValueError: # Fallback: Assume UTC if format is right but localization fails
                     dt_naive = datetime.fromisoformat(dt_val_processed)
                     dt_utc_aware = pytz.utc.localize(dt_naive)


            return dt_utc_aware.astimezone(pytz.timezone(tzname))
        except (ValueError, TypeError):
           pass # Invalid string format

    return None # Give up if no format works


def _series24(counter_by_hour: Counter) -> list[int]:
    # Ensure keys are integers for range lookup
    int_counter = Counter({int(k): v for k, v in counter_by_hour.items() if str(k).isdigit()})
    return [int(int_counter.get(h, 0)) for h in range(24)]

def _ensure_series24(nested_counter: dict[str, Counter]) -> dict[str, list[int]]:
    out = {}
    for k, c in nested_counter.items():
        out[k] = _series24(c)
    return out

def _transpose(m: dict[str, dict | Counter]) -> dict[str, dict]:
    """Convierte A->(B->n) en B->(A->n). Handles dicts and Counters safely."""
    out = defaultdict(Counter)
    if not isinstance(m, dict):
        print(f"Warning: Input to _transpose is not a dict: {type(m)}")
        return {} # Return empty if input is not a dict
    for a, per in m.items():
        inner_dict = {}
        if isinstance(per, (dict, Counter)):
            inner_dict = dict(per) # Convert Counter to dict
        # If 'per' is not a dict/Counter, skip this key 'a'
        elif per is not None:
             # print(f"Warning: Unexpected type for key '{a}' in _transpose: {type(per)}")
             continue
        else: # per is None
             continue


        for b, n in inner_dict.items():
            try:
                # Ensure keys are strings, convert n to int safely
                out[str(b)][str(a)] += int(n)
            except (ValueError, TypeError):
                # Ignore if n cannot be converted to int
                # print(f"Warning: Cannot convert value '{n}' to int for keys '{b}', '{a}'")
                pass
    # Convert final result to plain dicts
    return {k: dict(v) for k, v in out.items()}


# ---------- transformación principal ----------
def build_realtime_context(alarms: list[dict], value_for_column, tzname="America/Santiago") -> dict:
    # Totales simples
    severity_counts         = Counter()
    action_counts           = Counter()
    device_counts           = Counter()
    level_counts            = Counter()
    subtype_counts          = Counter()
    logdesc_counts          = Counter()
    msg_severity_counts     = Counter()

    # por hora (claves de hora INT 0..23 para _series24)
    total_by_hour           = Counter()             # índice numérico 0..23 (para arrays 24)
    sev_by_hour             = defaultdict(Counter)  # INT hour -> sev(lc) -> n
    dev_by_hour             = defaultdict(Counter)  # INT hour -> device -> n
    act_by_hour             = defaultdict(Counter)  # INT hour -> action -> n
    level_by_hour           = defaultdict(Counter)  # INT hour -> level -> n
    subtype_by_hour         = defaultdict(Counter)  # INT hour -> subtype -> n
    msgsev_by_hour          = defaultdict(Counter)  # INT hour -> msgsev(lc) -> n

    # series por hora (para arrays de 24)
    sev_series_by_hour      = defaultdict(Counter)  # sev(lc)   -> hour(int) -> n
    dev_series_by_hour      = defaultdict(Counter)  # device    -> hour(int) -> n
    act_series_by_hour      = defaultdict(Counter)  # action    -> hour(int) -> n
    msgsev_series_by_hour   = defaultdict(Counter)  # msgsev(lc)-> hour(int) -> n

    # cruces
    device_by_action        = defaultdict(Counter)  # action -> device -> n
    action_by_device        = defaultdict(Counter)  # device -> action -> n

    device_by_severity      = defaultdict(Counter)  # device -> sev(lc) -> n
    device_by_level         = defaultdict(Counter)  # device -> level   -> n
    device_by_subtype       = defaultdict(Counter)  # device -> subtype -> n
    # device_by_logdesc       = defaultdict(Counter)  # logdesc -> device -> n # Corrected below

    action_by_level         = defaultdict(Counter)  # level -> action -> n
    severity_by_level       = defaultdict(Counter)  # level -> sev(lc) -> n
    level_by_msgseverity    = defaultdict(Counter)  # msg(lc) -> level -> n
    msgseverity_by_level    = defaultdict(Counter)  # level -> msg(lc) -> n
    level_by_subtype        = defaultdict(Counter)  # subtype -> level -> n

    severity_by_subtype     = defaultdict(Counter)  # subtype -> sev(lc) -> n
    action_by_subtype       = defaultdict(Counter)  # subtype -> act     -> n
    msgseverity_by_subtype  = defaultdict(Counter)  # msg(lc) -> subtype -> n
    subtype_by_msgseverity  = defaultdict(Counter)  # subtype -> msg(lc) -> n

    action_by_msgseverity   = defaultdict(Counter)  # msg(lc) -> action -> n
    severity_by_msgseverity = defaultdict(Counter)  # sev(lc) -> msg(lc) -> n
    device_by_msgseverity   = defaultdict(Counter)  # msg(lc) -> device -> n

    action_by_logdesc       = defaultdict(Counter)  # logdesc -> action -> n
    severity_by_logdesc     = defaultdict(Counter)  # logdesc -> sev(lc) -> n
    logdesc_by_device       = defaultdict(Counter)  # device -> logdesc -> n # Added for transposition

    # cruces directos severidad <-> acción
    severity_by_action      = defaultdict(Counter)  # action -> sev(lc) -> n
    action_by_severity      = defaultdict(Counter)  # sev(lc) -> action -> n

    valid_alarm_count = 0
    for a in alarms:
        dt = _extract_dt_local(a, value_for_column, tzname)
        hour = dt.hour if isinstance(dt, datetime) else None # hour is INT 0..23 or None

        sev        = _norm_sev(        value_for_column(a, "severity"))
        msgsev     = _norm_msgsev(     value_for_column(a, "msg_severity"))
        # Ensure device name comes from a consistent field if possible
        device     = _norm_dev(        value_for_column(a, "msg_device_name") or value_for_column(a, "device_name"))
        level      = _norm_level(      value_for_column(a, "level"))
        subtype    = _norm_subtype(    value_for_column(a, "subtype"))
        action     = _norm_act(        value_for_column(a, "actions") or value_for_column(a, "Action"))
        logdesc    = (str(value_for_column(a, "log_description") or "").strip() or NA)

        # Basic check if the alarm has minimal usable data
        if not sev or sev == 'n/a': # Skip if primary severity is missing/invalid
             continue

        valid_alarm_count += 1

        if hour is not None:
            # Use INT hour for processing, convert to string "HH" later if needed for output keys
            total_by_hour[hour] += 1

            if sev != 'n/a':    sev_by_hour[hour][sev]       += 1
            if device != NA:    dev_by_hour[hour][device]    += 1
            if action != NA:    act_by_hour[hour][action]    += 1
            if level != NA:     level_by_hour[hour][level]   += 1
            if subtype != NA:   subtype_by_hour[hour][subtype] += 1
            if msgsev != 'n/a': msgsev_by_hour[hour][msgsev]  += 1

            if sev != 'n/a':    sev_series_by_hour[sev][hour]      += 1
            if device != NA:    dev_series_by_hour[device][hour]   += 1
            if action != NA:    act_series_by_hour[action][hour]   += 1
            if msgsev != 'n/a': msgsev_series_by_hour[msgsev][hour]+= 1

        # Totals
        if sev != 'n/a':      severity_counts[sev]       += 1
        if msgsev != 'n/a':   msg_severity_counts[msgsev]+= 1
        if action != NA:      action_counts[action]      += 1
        if device != NA:      device_counts[device]      += 1
        if level != NA:       level_counts[level]        += 1
        if subtype != NA:     subtype_counts[subtype]    += 1
        if logdesc != NA:     logdesc_counts[logdesc]    += 1 # Avoid counting NA logdesc

        # Cross Filters (only count if both dimensions are valid)
        if device != NA and action != NA:
            action_by_device[device][action] += 1
            device_by_action[action][device] += 1
        if device != NA and sev != 'n/a':
            device_by_severity[device][sev] += 1
        if device != NA and level != NA:
            device_by_level[device][level] += 1
        if device != NA and subtype != NA:
            device_by_subtype[device][subtype] += 1
        if device != NA and msgsev != 'n/a':
            device_by_msgseverity[msgsev][device] += 1
        if device != NA and logdesc != NA:
            logdesc_by_device[device][logdesc] += 1 # device -> logdesc

        if level != NA and action != NA:
            action_by_level[level][action] += 1
        if level != NA and sev != 'n/a':
            severity_by_level[level][sev] += 1
        if level != NA and msgsev != 'n/a':
            msgseverity_by_level[level][msgsev] += 1
            level_by_msgseverity[msgsev][level] += 1
        if subtype != NA and level != NA:
            level_by_subtype[subtype][level] += 1 # subtype -> level

        if subtype != NA and sev != 'n/a':
            severity_by_subtype[subtype][sev] += 1 # subtype -> sev
        if subtype != NA and action != NA:
            action_by_subtype[subtype][action] += 1
        if msgsev != 'n/a' and subtype != NA:
            msgseverity_by_subtype[msgsev][subtype] += 1 # msg -> subtype
            subtype_by_msgseverity[subtype][msgsev] += 1 # subtype -> msg

        if action != NA and msgsev != 'n/a':
            action_by_msgseverity[msgsev][action] += 1
        if sev != 'n/a' and msgsev != 'n/a':
            severity_by_msgseverity[sev][msgsev] += 1 # sev -> msg

        if logdesc != NA and action != NA:
            action_by_logdesc[logdesc][action] += 1
        if logdesc != NA and sev != 'n/a':
            severity_by_logdesc[logdesc][sev] += 1

        if sev != 'n/a' and action != NA:
            severity_by_action[action][sev] += 1 # action -> sev
            action_by_severity[sev][action] += 1 # sev -> action

    # print(f"Processed {valid_alarm_count} valid alarms out of {len(alarms)}")

    # ---------- construir salida ----------
    trend_labels = [] # Assuming trend data is not calculated in realtime, adjust if needed
    trend_data   = []
    severity_trends = {} # Assuming trend data is not calculated in realtime

    hour_labels = [f"{h:02d}" for h in range(24)]
    hour_data   = _series24(total_by_hour)
    trend_labels_hour = hour_labels # Use hour labels if trend is hourly based
    # Simplified trend_by_hour, assumes you might just want total and severity per hour series
    trend_by_hour = {"total": hour_data} # | _ensure_series24(sev_series_by_hour) # Keep it simple?

    # Convert hour keys from INT to "HH" string format for JSON output consistency
    sev_by_hour_str = {f"{h:02d}": dict(c) for h, c in sev_by_hour.items()}
    dev_by_hour_str = {f"{h:02d}": dict(c) for h, c in dev_by_hour.items()}
    act_by_hour_str = {f"{h:02d}": dict(c) for h, c in act_by_hour.items()}
    level_by_hour_str = {f"{h:02d}": dict(c) for h, c in level_by_hour.items()}
    subtype_by_hour_str = {f"{h:02d}": dict(c) for h, c in subtype_by_hour.items()}
    msgsev_by_hour_str = {f"{h:02d}": dict(c) for h, c in msgsev_by_hour.items()}


    # --- Pre-calculate transposed structures needed for aliases ---
    # Convert inner Counters to dicts before transposing
    _device_by_sev_full = _transpose({k: dict(v) for k, v in device_by_severity.items()})  # sev -> device -> n
    _subtype_by_sev = _transpose({k: dict(v) for k, v in severity_by_subtype.items()}) # subtype -> sev  =>  sev -> subtype
    _sev_by_msgsev_transposed = _transpose({k: dict(v) for k, v in severity_by_msgseverity.items()}) # sev->msg => msg->sev
    # These were already calculated in the correct direction
    _subtype_by_msgsev = {k: dict(v) for k, v in msgseverity_by_subtype.items()} # msg -> subtype
    _msgsev_by_subtype = {k: dict(v) for k, v in subtype_by_msgseverity.items()} # subtype -> msg
    _level_by_subtype_transposed = _transpose({k: dict(v) for k, v in level_by_subtype.items()}) # subtype->level => level->subtype
    _device_by_logdesc = _transpose({k: dict(v) for k, v in logdesc_by_device.items()}) # device->logdesc => logdesc->device
    _act_by_sev_transposed = _transpose({k: dict(v) for k, v in action_by_severity.items()}) # sev->action => action->sev (sevToAct)


    # Calculate hour series by subtype using INT hours
    hour_series_by_subtype = defaultdict(lambda: [0] * 24)
    for h, per in subtype_by_hour.items(): # h is INT here
        for st, n in per.items():
             # Ensure index h is within bounds
             if 0 <= h < 24:
                hour_series_by_subtype[st][h] += int(n)


    # Base output structure (convert Counters/defaultdicts to plain dicts here)
    # Use the calculated plain dicts directly where possible
    out = {
        "trend_labels": trend_labels,
        "trend_data": trend_data,
        "severity_trends": severity_trends,

        "severity_counts": dict(severity_counts),

        "device_counts": dict(device_counts),
        "action_counts": dict(action_counts),

        "device_counts_by_severity": _device_by_sev_full,          # sev -> device
        "device_counts_by_severity_full": _device_by_sev_full,     # sev -> device

        "trend_by_device": _ensure_series24(dev_series_by_hour),
        "trend_by_action": _ensure_series24(act_series_by_hour),
        "top_devices": dict(sorted(device_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]),

        "hour_labels": hour_labels,
        "hour_data": hour_data,
        "severity_counts_by_hour": sev_by_hour_str,               # "HH" -> sev
        "device_counts_by_hour":   dev_by_hour_str,               # "HH" -> device
        "device_counts_by_hour_full": dev_by_hour_str,            # "HH" -> device
        "action_counts_by_hour":   act_by_hour_str,               # "HH" -> action
        "trend_labels_hour": trend_labels_hour,
        "trend_by_hour": trend_by_hour,

        "device_counts_by_action": {act: dict(c) for act, c in device_by_action.items()}, # action -> device
        "action_counts_by_device": {dev: dict(c) for dev, c in action_by_device.items()}, # device -> action
        "action_counts_by_severity": {sev: dict(c) for sev, c in action_by_severity.items()}, # sev -> action

        "msg_severity_counts": dict(msg_severity_counts),
        "device_counts_by_msg_severity": {msg: dict(c) for msg, c in device_by_msgseverity.items()}, # msg -> device
        "action_counts_by_msg_severity": {msg: dict(c) for msg, c in action_by_msgseverity.items()}, # msg -> action
        "severity_counts_by_msg_severity": {sev: dict(c) for sev, c in severity_by_msgseverity.items()}, # sev -> msg
        "msg_severity_counts_by_hour": msgsev_by_hour_str,        # "HH" -> msgsev
        "trend_by_msg_severity": {msg: _series24(c) for msg, c in msgsev_series_by_hour.items()},

        "level_counts": dict(level_counts),
        "device_counts_by_level": {lvl: dict(c) for lvl, c in device_by_level.items()},          # device -> level
        "action_counts_by_level": {lvl: dict(c) for lvl, c in action_by_level.items()},          # level -> action
        "severity_counts_by_level": {lvl: dict(c) for lvl, c in severity_by_level.items()},      # level -> sev
        "trend_by_level": {lvl: _series24(level_by_hour.get(lvl, Counter())) for lvl in level_counts.keys()},
        "level_counts_by_hour": level_by_hour_str,               # "HH" -> level
        "subtype_counts_by_level": _level_by_subtype_transposed, # level -> subtype
        "msg_severity_by_level": {lvl: dict(c) for lvl, c in msgseverity_by_level.items()},      # level -> msg
        "level_by_msg_severity": {msg: dict(c) for msg, c in level_by_msgseverity.items()},      # msg -> level

        "subtype_counts": dict(subtype_counts),
        "device_counts_by_subtype": {st: dict(c) for st, c in device_by_subtype.items()},       # device -> subtype
        "action_counts_by_subtype": {st: dict(c) for st, c in action_by_subtype.items()},       # subtype -> action
        "severity_counts_by_subtype": {st: dict(c) for st, c in severity_by_subtype.items()},   # subtype -> sev
        "subtype_counts_by_hour": subtype_by_hour_str,            # "HH" -> subtype
        "hour_series_by_subtype": {st: list(arr) for st, arr in hour_series_by_subtype.items()},
        "msg_severity_by_subtype": {msg: dict(c) for msg, c in msgseverity_by_subtype.items()},   # msg -> subtype
        "subtype_by_msg_severity": {st: dict(c) for st, c in subtype_by_msgseverity.items()},   # subtype -> msg

        "logdesc_counts": dict(logdesc_counts),
        "device_counts_by_logdesc": _device_by_logdesc,          # logdesc -> device
        "action_counts_by_logdesc": {ld: dict(c) for ld, c in action_by_logdesc.items()},       # logdesc -> action
        "severity_counts_by_logdesc": {ld: dict(c) for ld, c in severity_by_logdesc.items()},   # logdesc -> sev
    }

    # ===== Aliases for selectors.js (orientación correcta) =====
    # Use the pre-calculated, plain dict variables and keys from 'out'

    out.update({
        # --- Hour related ---
        "sevByHourRaw":        out.get("severity_counts_by_hour", {}), # Use calculated str key dict
        "devByHourRaw":        out.get("device_counts_by_hour", {}),   # Use calculated str key dict
        "actByHourNorm":       out.get("action_counts_by_hour", {}),   # Use calculated str key dict
        "levelCountsByHourRaw": out.get("level_counts_by_hour",{}),    # Use calculated str key dict
        "subtypeByHourRaw":    out.get("subtype_counts_by_hour",{}),   # Use calculated str key dict
        "msgSeverityByHourRaw": out.get("msg_severity_counts_by_hour",{}), # Use calculated str key dict

        # --- Trend related (placeholders) ---
        "trendLabels":         out.get("trend_labels", []),
        "trendLabelsHour":     out.get("trend_labels_hour", []),
        "trendByHourRaw":      out.get("trend_by_hour", {}),
        "severityTrendsMap":   out.get("severity_trends", {}),

        # --- Base Counts ---
        "actionCountsRaw":     out.get("action_counts", {}),
        "deviceCountsAll":     out.get("device_counts", {}),
        "msgSeverityCountsRaw": out.get("msg_severity_counts", {}),
        "levelCountsRaw":      out.get("level_counts", {}),
        "subtypeCountsRaw":    out.get("subtype_counts", {}),
        "logDescCountsRaw":    out.get("logdesc_counts", {}),

        # --- Action related ---
        "actionByDev":         out.get("action_counts_by_device", {}), # device -> action
        "deviceByAction":      out.get("device_counts_by_action", {}), # action -> device
        "sevToAct":            _act_by_sev_transposed, # action -> sev (transposed from sev->action)
        "actToSev":            out.get("severity_counts_by_action", {}), # action -> sev
        "actionByLevelRaw":    out.get("action_counts_by_level", {}),  # level -> action
        "actionBySubtypeRaw":  out.get("action_counts_by_subtype", {}),# subtype -> action
        "actionByMsgSeverityRaw": out.get("action_counts_by_msg_severity", {}), # msg -> action
        "actionByLogDescRaw":  out.get("action_counts_by_logdesc", {}), # logdesc -> action

        # --- Device related ---
        "deviceByLevelRaw":    _transpose({k: dict(v) for k, v in device_by_level.items()}), # level -> device (transpose)
        "deviceBySubtypeRaw":  _transpose({k: dict(v) for k, v in device_by_subtype.items()}),# subtype -> device (transpose)
        "deviceByMsgSeverityRaw": out.get("device_counts_by_msg_severity", {}),# msg -> device
        "deviceByLogDescRaw":  out.get("device_counts_by_logdesc", {}),# logdesc -> device

        # --- MsgSeverity related ---
        "severityByMsgSeverityRaw":   _sev_by_msgsev_transposed, # msg -> sev
        "subtypeByMsgSeverityRaw":    _subtype_by_msgsev,        # msg -> subtype
        "msgSeverityBySubtypeRaw":    _msgsev_by_subtype,        # subtype -> msg
        "msgSeverityBySeverityRaw":   {k: dict(v) for k, v in severity_by_msgseverity.items()}, # sev -> msg
        "msgSeverityByLevelRaw":      out.get("msg_severity_by_level", {}), # level -> msg
        "levelByMsgSeverityRaw":      out.get("level_by_msg_severity", {}), # msg -> level


        # --- Level related ---
        "severityByLevelRaw":         out.get("severity_counts_by_level", {}), # level -> sev
        "levelBySubtypeRaw":          out.get("subtype_counts_by_level", {}), # level -> subtype


        # --- Subtype related ---
        "severityBySubtypeRaw":       out.get("severity_counts_by_subtype", {}), # subtype -> sev
        "subtypeBySeverityRaw":       _subtype_by_sev, # sev -> subtype


        # --- LogDesc related ---
        "severityByLogDescRaw":       out.get("severity_counts_by_logdesc", {}), # logdesc -> sev

        # --- Other Series ---
        "hourSeriesBySubtypeRaw":     out.get("hour_series_by_subtype", {}),
    })

    # Final conversion pass to ensure no Counters/defaultdicts remain
    # (This is defensive programming, might not be strictly necessary if all conversions above are correct)
    final_cleaned_out = {}
    for key, value in out.items():
        if isinstance(value, dict):
            # Recursively clean nested dicts (up to 2 levels deep common in this structure)
            cleaned_dict = {}
            for k_inner, v_inner in value.items():
                if isinstance(v_inner, (Counter, defaultdict)):
                    cleaned_dict[k_inner] = dict(v_inner)
                elif isinstance(v_inner, dict):
                    # One more level deep for structures like A -> B -> n
                    cleaned_dict[k_inner] = {k_deep: dict(v_deep) if isinstance(v_deep, (Counter, defaultdict)) else v_deep
                                             for k_deep, v_deep in v_inner.items()}
                else:
                    cleaned_dict[k_inner] = v_inner # Assume list, number, str, etc.
            final_cleaned_out[key] = cleaned_dict
        elif isinstance(value, (Counter, defaultdict)):
             final_cleaned_out[key] = dict(value)
        else:
             final_cleaned_out[key] = value # Keep lists, numbers, strings as is

    return final_cleaned_out