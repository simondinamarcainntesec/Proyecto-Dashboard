from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from inyeccion_api.models import Alarm
from inyeccion_api.views import (
    _to_datetime_santiago,
    _format_aotags,
    _message_extract_multiple_sources,
    _get_value_case_insensitive,
)

logger = logging.getLogger(__name__)


def _value_for_column_alarm(alarm: dict[str, Any], column: str) -> Any:
    """
    Replica la lógica de value_for_column usada en realtime/dashboard,
    pero local a utils.py para no depender de que exista en views.py.

    Resolver valores para columnas usadas en realtime/dashboard.
    """
    # Campos directos
    if column in ("Action", "actions", "severity", "alarmid"):
        return _get_value_case_insensitive(alarm, column)

    # eventtime → datetime en America/Santiago
    if column == "eventtime":
        return _to_datetime_santiago(
            _get_value_case_insensitive(alarm, column)
        )

    # aotags crudo (el formateo a string se hace aparte)
    if column == "aotags":
        return _get_value_case_insensitive(alarm, column)

    # Campos parseados desde message / log_details
    if column in (
        "msg_severity",
        "msg_device_name",
        "level",
        "log_description",
        "subtype",
    ):
        extracted = _message_extract_multiple_sources(
            alarm,
            wanted=[
                "Severity",
                "Device Name",
                "Device",
                "Level",
                "Log Description",
                "Subtype",
            ],
        )

        if column == "msg_severity":
            return extracted.get("Severity", "") or ""

        if column == "msg_device_name":
            return (
                extracted.get("Device Name", "")
                or extracted.get("Device", "")
                or ""
            )

        if column == "level":
            return extracted.get("Level", "") or ""

        if column == "log_description":
            return extracted.get("Log Description", "") or ""

        if column == "subtype":
            return extracted.get("Subtype", "") or ""

    return ""


def _map_api_alarm_to_model(a: dict[str, Any]) -> Alarm | None:
    """
    Construye un objeto Alarm (no guardado) desde un dict de la API.

    Usa alertid (o alarmid) como clave única.
    Reutiliza la misma lógica de parseo que realtime
    (a través de _value_for_column_alarm)
    para device, msg_severity, level, log_description y subtype.
    """
    raw_alertid = (
        _get_value_case_insensitive(a, "alertid")
        or _get_value_case_insensitive(a, "alarmid")
        or _get_value_case_insensitive(a, "Alertid")
    )
    if not raw_alertid:
        return None

    # === Tiempo / tags (misma lógica conceptual que realtime) ===
    event_time = _value_for_column_alarm(a, "eventtime")
    if not isinstance(event_time, datetime):
        # Fallback por si algo llegara raro
        event_time = _to_datetime_santiago(
            _get_value_case_insensitive(a, "eventtime")
        )

    tags_raw = _value_for_column_alarm(a, "aotags")
    tags = _format_aotags(tags_raw)

    # Severidad "principal"
    severity = (_value_for_column_alarm(a, "severity") or "") or (
        _get_value_case_insensitive(a, "severity")
        or _get_value_case_insensitive(a, "Severity")
        or ""
    )

    # === Detalle, reutilizando exactamente la misma lógica de parseo ===

    # Dispositivo
    device_name = (
        _value_for_column_alarm(a, "msg_device_name")
        or _get_value_case_insensitive(a, "devname")
        or _get_value_case_insensitive(a, "device")
        or ""
    )

    # msg_severity
    msg_severity = _value_for_column_alarm(a, "msg_severity") or ""

    # level
    level = _value_for_column_alarm(a, "level") or ""

    # log_description
    log_description = _value_for_column_alarm(a, "log_description") or ""

    # subtype
    subtype = _value_for_column_alarm(a, "subtype") or ""

    # action / actions: misma lógica que en realtime_alarms_by_subtype
    action = (
        _get_value_case_insensitive(a, "actions")
        or _get_value_case_insensitive(a, "Action")
        or ""
    )
    actions = _get_value_case_insensitive(a, "actions") or ""

    logger.debug(
        "[MAP API ALARM] id=%s device=%r msg_sev=%r level=%r subtype=%r action=%r",
        raw_alertid,
        device_name,
        msg_severity,
        level,
        subtype,
        action,
    )

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
