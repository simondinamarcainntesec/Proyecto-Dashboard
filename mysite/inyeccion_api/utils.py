from inyeccion_api.models import Alarm

def _map_api_alarm_to_model(a: dict) -> Alarm | None:
    """
    Construye un objeto Alarm (no guardado) desde un dict de la API.
    Usa alertid (o alarmid) como clave única.
    """
    raw_alertid = (
        _get_value_case_insensitive(a, "alertid")
        or _get_value_case_insensitive(a, "alarmid")
        or _get_value_case_insensitive(a, "Alertid")
    )
    if not raw_alertid:
        return None

    event_time = _to_datetime_santiago(_get_value_case_insensitive(a, "eventtime"))
    tags = _format_aotags(_get_value_case_insensitive(a, "aotags"))
    severity = _get_value_case_insensitive(a, "severity") or ""
    action = _get_value_case_insensitive(a, "Action") or ""
    actions = _get_value_case_insensitive(a, "actions") or ""

    extracted = _message_extract_multiple_sources(
        a, ["Device Name", "Device", "Severity", "Level", "Log Description", "Subtype"]
    )

    device_name = extracted.get("Device Name", "") or extracted.get("Device", "") or ""
    msg_severity = extracted.get("Severity", "") or ""
    level = extracted.get("Level", "") or ""
    log_description = extracted.get("Log Description", "") or ""
    subtype = extracted.get("Subtype", "") or ""

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