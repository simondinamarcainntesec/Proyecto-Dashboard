// selectors.js
import {
  normalizeCountsLabels,
  findKeyCI,
  normalizeMapValues,
  readJSON,
  prettyActionLabel,
} from "./utils.js";
import data from "./data.js";
import { colorFor, colorForMsgSeverity } from "./theme.js";

/* =========================================================
 *  HELPERS
 * =======================================================*/
function top10(m) {
  return Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, 10);
}

function applySeveritySlice(counts, severityFilter) {
  if (!severityFilter) return counts;

  const raw = String(severityFilter).trim().toLowerCase();

  // Valores que significan "todas las severidades" → no recortamos
  if (!raw || raw === "all" || raw === "todas" || raw === "todos" || raw === "any") {
    return counts;
  }

  // Buscamos una clave real en el mapa (case-insensitive)
  const realKey = findKeyCI(counts, severityFilter);

  // Si NO existe en el mapa, no recortamos (para no generar 0 artificial)
  if (!realKey) {
    return counts;
  }

  const v = Number(counts[realKey] || 0);
  return { [realKey]: v };
}

// pivots → severidad (para donut/KPI)
function sevForDevice(device) {
  const dev = data.canonicalDeviceKey(device);
  const out = {};
  Object.keys(data.deviceBySevFullRaw || {}).forEach((sev) => {
    const m = data.deviceBySevFullRaw[sev] || {};
    out[String(sev).trim()] = Number(m[dev] || 0);
  });
  return out;
}
function sevForAction(actionKey) {
  const m = data.actToSev[actionKey] || {};
  const out = {};
  Object.keys(m).forEach((sev) => (out[sev] = Number(m[sev] || 0)));
  return out;
}
function sevForHour(hour) {
  const m = data.sevByHourRaw?.[hour] || {};
  const out = {};
  Object.keys(m).forEach(
    (sev) => (out[String(sev).trim()] = Number(m[sev] || 0)),
  );
  return out;
}
function sevForMsgSeverity(msg) {
  const src = data.severityByMsgSeverityRaw || {};
  const real = findKeyCI(src, msg);
  const m = real ? src[real] || {} : {};
  const out = {};
  Object.keys(m).forEach(
    (sev) => (out[String(sev).trim()] = Number(m[sev] || 0)),
  );
  return out;
}
function sevForLevel(level) {
  const real = findKeyCI(data.severityByLevelRaw, level) ?? level;
  const per = data.severityByLevelRaw?.[real] || {};
  const out = {};
  Object.keys(per).forEach(
    (sev) => (out[String(sev).trim()] = Number(per[sev] || 0)),
  );
  return out;
}
function sevForSubtype(subtype) {
  const real = findKeyCI(data.severityBySubtypeRaw, subtype) ?? subtype;
  const per = data.severityBySubtypeRaw?.[real] || {};
  const out = {};
  Object.keys(per).forEach(
    (sev) => (out[String(sev).trim()] = Number(per[sev] || 0)),
  );
  return out;
}
function sevForLogDesc(desc) {
  const real = findKeyCI(data.severityByLogDescRaw, desc) ?? desc;
  const per = data.severityByLogDescRaw?.[real] || {};
  const out = {};
  Object.keys(per).forEach(
    (sev) => (out[String(sev).trim()] = Number(per[sev] || 0)),
  );
  return out;
}

/* =========================================================
 *  PIVOT ACTIVO
 * =======================================================*/
function activePivot(state) {
  // Logueamos el estado bruto
  console.debug("[pivot] estado actual:", {
    deviceFilter: state.deviceFilter,
    actionFilter: state.actionFilter,
    hourFilter: state.hourFilter,
    msgSeverityFilter: state.msgSeverityFilter,
    levelFilter: state.levelFilter,
    subtypeFilter: state.subtypeFilter,
    logDescriptionFilter: state.logDescriptionFilter,
    severityFilter: state.severityFilter,
  });

  // Normalizamos el msgSeverityFilter
  const msgRaw = (state.msgSeverityFilter || "").trim();
  let msgKey = null;

  // Si el valor es "all", "todas", etc. → NO lo usamos como pivot
  if (
    msgRaw &&
    !["all", "todas", "todos", "any"].includes(msgRaw.toLowerCase())
  ) {
    msgKey = findKeyCI(data.severityByMsgSeverityRaw || {}, msgRaw) || msgRaw;
  }

  let res;
  if (state.deviceFilter) {
    res = ["device", state.deviceFilter];
  } else if (state.actionFilter) {
    res = ["action", state.actionFilter];
  } else if (state.hourFilter) {
    res = ["hour", state.hourFilter];
  } else if (msgKey) {
    res = ["msg", msgKey];
  } else if (state.levelFilter) {
    res = ["level", state.levelFilter];
  } else if (state.subtypeFilter) {
    res = ["subtype", state.subtypeFilter];
  } else if (state.logDescriptionFilter) {
    res = ["logdesc", state.logDescriptionFilter];
  } else if (state.severityFilter) {
    res = ["severity", state.severityFilter];
  } else {
    res = ["none", ""];
  }

  console.debug("[pivot] elegido:", { kind: res[0], key: res[1] });
  return res;
}

/* =========================================================
 *  DONUT / KPIs – MAPA DE SEVERIDAD ACTIVO
 * =======================================================*/
export function getActiveCounts(state) {
  const [kind, key] = activePivot(state); // ya loguea adentro

  let base;
  switch (kind) {
    case "device":
      base = sevForDevice(key);
      break;
    case "action":
      base = sevForAction(key);
      break;
    case "hour":
      base = sevForHour(key);
      break;
    case "msg":
      base = sevForMsgSeverity(key);
      break;
    case "level":
      base = sevForLevel(key);
      break;
    case "subtype":
      base = sevForSubtype(key);
      break;
    case "logdesc":
      base = sevForLogDesc(key);
      break;
    default:
      base = data.severityCounts; // global (campo severity)
      break;
  }

  console.debug("[counts] base antes de normalizar:", {
    kind,
    key,
    baseRaw: base,
  });

  base = normalizeCountsLabels(base || {});
  const baseNormalized = { ...base };

  base = applySeveritySlice(base, state.severityFilter);
  console.debug("[counts] después de normalize + slice:", {
    severityFilter: state.severityFilter,
    baseNormalized,
    finalCounts: base,
  });

  if (!base || Object.keys(base).length === 0) {
    console.debug("[counts] vacío → devolviendo { 'N/A': 0 }");
    return { "N/A": 0 };
  }
  return base;
}

// === Mismos datos que el donut, sin recortar por severityFilter ===
export function getActiveCountsForDonut(state) {
  const [kind, key] = activePivot(state);

  let base;
  switch (kind) {
    case "device":
      base = sevForDevice(key);
      break;
    case "action":
      base = sevForAction(key);
      break;
    case "hour":
      base = sevForHour(key);
      break;
    case "msg":
      base = sevForMsgSeverity(key);
      break;
    case "level":
      base = sevForLevel(key);
      break;
    case "subtype":
      base = sevForSubtype(key);
      break;
    case "logdesc":
      base = sevForLogDesc(key);
      break;
    default:
      base = data.severityCounts;
      break;
  }

  base = normalizeCountsLabels(base || {});
  if (!base || Object.keys(base).length === 0) return { "N/A": 0 };
  return base;
}

// Helper: counts específicos para el KPI → usamos EXACTAMENTE lo mismo que el donut
function getCountsForKpi(state) {
  return getActiveCountsForDonut(state);
}

// KPI “Severidad crítica” + totales
export function calcKpis(state) {
  console.debug("==================================");
  console.debug("[KPI] calcKpis() llamado con state:", state);

  // Para KPI usamos los mismos counts que el donut (sin slice por severityFilter)
  const counts = getCountsForKpi(state) || {};

  let total = Object.values(counts).reduce(
    (a, b) => a + (Number(b) || 0),
    0,
  );

  // Ajuste device → usa total del device completo
  if (state.deviceFilter && !state.severityFilter) {
    const dk = data.canonicalDeviceKey(state.deviceFilter);
    if (
      data.deviceCountsAll &&
      Object.prototype.hasOwnProperty.call(data.deviceCountsAll, dk)
    ) {
      console.debug("[KPI] override total por device:", {
        device: dk,
        totalDevice: data.deviceCountsAll[dk],
      });
      total = Number(data.deviceCountsAll[dk] || 0);
    }
  }

  // ==========================
  // HIGH (críticos)
  // 1) Intentar msg_severity SOLO si tiene "critical"
  // 2) Si no hay "critical" en msg_severity → fallback a severity normal
  // ==========================
  let high = 0;

  try {
    let usedMsg = false;

    // Lógica de la barra de msg_severity
    const msgData = msgSeverityDataForCurrentFilter(state);

    const hasMsgData =
      msgData &&
      Array.isArray(msgData.keys) &&
      msgData.keys.length > 0 &&
      Array.isArray(msgData.data);

    if (hasMsgData) {
      const map = {};
      msgData.keys.forEach((k, idx) => {
        map[k] = Number(msgData.data[idx] || 0);
      });

      const realKey = findKeyCI(map, "critical"); // <- busca "critical" CI

      if (realKey) {
        high = Number(map[realKey] || 0);
        usedMsg = true;
        console.debug("[KPI] high desde msg_severity:", {
          map,
          realKey,
          high,
        });
      } else {
        console.debug(
          "[KPI] msg_severity tiene datos pero NO 'critical' → usaremos severity normal",
          { map },
        );
      }
    }

    // Si no se usó msg_severity (porque no había datos o no había 'critical')
    if (!usedMsg) {
      const normCounts = normalizeCountsLabels({ ...counts });
      high = Number(normCounts["critical"] || 0);
      console.debug(
        "[KPI] high desde severity (fallback o sin msg_severity crítico):",
        { normCounts, high },
      );
    }
  } catch (e) {
    console.error(
      "[KPI] error calculando high, fallback severity",
      e,
    );
    const normCounts = normalizeCountsLabels({ ...counts });
    high = Number(normCounts["critical"] || 0);
  }

  const devices = state.deviceFilter
    ? 1
    : Object.keys(data.deviceCountsAll || {}).length;

  console.debug("[KPI] resultado final:", {
    total,
    high,
    devices,
    counts,
  });

  return { total, high, devices };
}



/* =========================================================
 *  (NUEVO) SEVERIDAD ALARMA (barra) → cambia a MSG_SEVERITY si hay level
 * =======================================================*/
export function severityBarDataForCurrentFilter(state) {
  // CASO 1: Hay un level seleccionado → mostrar msg_severity para ese level
  if (state.levelFilter && data.msgSeverityByLevelRaw) {
    const levKey =
      findKeyCI(data.msgSeverityByLevelRaw, state.levelFilter) ??
      state.levelFilter;

    const per = data.msgSeverityByLevelRaw[levKey] || {};

    const labels = Object.keys(per); // ["high","medium","low",...]
    const values = labels.map((k) => Number(per[k] || 0));

    return {
      labels,
      data: values,
      keys: labels,
      mode: "msg",
    };
  }

  // CASO 2: No hay level seleccionado → severidad clásica
  const m = normalizeMapValues(data.severityCounts);
  const labels = Object.keys(m);
  const values = labels.map((k) => Number(m[k] || 0));

  return {
    labels,
    data: values,
    keys: labels,
    mode: "severity",
  };
}

/* =========================================================
 *  TREND (Alarmas por día)
 * =======================================================*/
export function trendDataForCurrentFilter(state) {
  function baseTrend(labels, items) {
    const datasets = items.map(({ label, data, color }) => ({
      label,
      data,
      borderColor: color,
      backgroundColor: color + "33",
      borderWidth: 3,
      pointRadius: 3,
      pointHoverRadius: 5,
      fill: true,
      tension: 0.35,
    }));
    return { labels, datasets };
  }

  const { canonicalDeviceKey } = data;

  const labels = Array.isArray(data.trendLabels) ? data.trendLabels : [];
  const sumSeveritySeries = () => {
    const map = data.severityTrendsMap || {};
    const L = labels.length || (Object.values(map)[0]?.data?.length || 0);
    const total = new Array(L).fill(0);
    for (const k of Object.keys(map)) {
      const arr = map[k]?.data || [];
      for (let i = 0; i < L; i++) total[i] += Number(arr[i] || 0);
    }
    return total;
  };
  const totalSeries =
    Array.isArray(data.trendData) && data.trendData.length
      ? data.trendData
      : sumSeveritySeries();

  if (
    state.deviceFilter &&
    data.trendByDevice?.[canonicalDeviceKey(state.deviceFilter)]
  ) {
    const dk = canonicalDeviceKey(state.deviceFilter);
    return baseTrend(data.trendLabels, [
      { label: dk, data: data.trendByDevice[dk], color: "#60A5FA" },
    ]);
  }
  if (state.actionFilter && data.trendByAction?.[state.actionFilter]) {
    return baseTrend(data.trendLabels, [
      {
        label: `Acción: ${prettyActionLabel(state.actionFilter)}`,
        data: data.trendByAction[state.actionFilter],
        color: "#8B5CF6",
      },
    ]);
  }
  if (state.hourFilter && data.trendByHourRaw?.[state.hourFilter]) {
    const series = data.trendByHourRaw[state.hourFilter] || [];
    return baseTrend(data.trendLabelsHour, [
      { label: `Hora ${state.hourFilter}:00`, data: series, color: "#0EA5E9" },
    ]);
  }
  if (
    state.msgSeverityFilter &&
    data.trendByMsgSeverityRaw?.[state.msgSeverityFilter]
  ) {
    return baseTrend(data.trendLabels, [
      {
        label: `Severidad Alarma: ${state.msgSeverityFilter}`,
        data: data.trendByMsgSeverityRaw[state.msgSeverityFilter],
        color: "#F43F5E",
      },
    ]);
  }
  if (state.levelFilter && data.trendByLevel?.[state.levelFilter]) {
    return baseTrend(data.trendLabels, [
      {
        label: `Level: ${state.levelFilter}`,
        data: data.trendByLevel[state.levelFilter],
        color: "#0EA5E9",
      },
    ]);
  }
  if (state.subtypeFilter && data.trendBySubtype?.[state.subtypeFilter]) {
    return baseTrend(data.trendLabels, [
      {
        label: `Subtype: ${state.subtypeFilter}`,
        data: data.trendBySubtype[state.subtypeFilter],
        color: "#22C55E",
      },
    ]);
  }

  if (state.severityFilter) {
    const want = String(state.severityFilter).trim().toLowerCase();
    const map = data.severityTrendsMap || {};
    const matchKey = Object.keys(map).find(
      (k) => String(k).trim().toLowerCase() === want,
    );
    const series =
      matchKey && map[matchKey]?.data?.length
        ? map[matchKey].data
        : new Array(labels.length).fill(0);
    return baseTrend(labels, [
      { label: matchKey || want, data: series, color: "#60A5FA" },
    ]);
  }

  return baseTrend(labels, [
    { label: "Alarmas por día", data: totalSeries, color: "#60A5FA" },
  ]);
}

/* =========================================================
 *  HOURLY (Alarmas por hora)
 * =======================================================*/
export function hourDataForCurrentFilter(state) {
  const labels = data.hourLabels || [];
  let series = data.hourData || [];
  let label = "Alarmas (por hora, rango actual)";

  if (state.subtypeFilter) {
    const json = data.hourSeriesBySubtypeRaw || {};
    const keys = Object.keys(json || {});
    console.debug(
      "[hourly] subtypeFilter:",
      state.subtypeFilter,
      "keys json:",
      keys.length ? keys.slice(0, 5) : keys,
    );

    if (keys.length) {
      const subKey =
        findKeyCI(json, state.subtypeFilter) ?? state.subtypeFilter;
      const arr = json[subKey] || [];
      console.debug(
        "[hourly] usando hour-series-by-subtype →",
        subKey,
        "len:",
        arr?.length,
      );

      series = Array.isArray(arr)
        ? labels.map((_, i) => Number(arr[i] || 0))
        : labels.map(() => 0);
      label = `Alarmas por hora — Subtype: ${subKey}`;
      return { labels, data: series, label };
    }

    const map = data.subtypeByHourRaw || {};
    console.debug("[hourly] fallback subtypeByHourRaw");
    series = labels.map(
      (h) => Number((map[h] || {})[state.subtypeFilter] || 0),
    );
    label = `Alarmas por hora — Subtype: ${state.subtypeFilter}`;
    return { labels, data: series, label };
  }

  if (state.deviceFilter && data.devByHourRaw) {
    const dk = data.canonicalDeviceKey(state.deviceFilter);
    series = labels.map(
      (h) => Number((data.devByHourRaw[h] || {})[dk] || 0),
    );
    label = `Alarmas por hora — Dispositivo: ${dk}`;
    return { labels, data: series, label };
  }

  if (state.severityFilter && data.sevByHourRaw) {
    series = labels.map((h) => {
      const m = data.sevByHourRaw[h] || {};
      const hk = findKeyCI(m, state.severityFilter) || state.severityFilter;
      return Number(m[hk] || 0);
    });
    label = `Alarmas por hora — Severidad: ${state.severityFilter}`;
    return { labels, data: series, label };
  }

  if (state.actionFilter && data.actByHourNorm) {
    series = labels.map(
      (h) => Number((data.actByHourNorm[h] || {})[state.actionFilter] || 0),
    );
    label = `Alarmas por hora — Acción: ${state.actionFilter}`;
    return { labels, data: series, label };
  }

  if (state.msgSeverityFilter && data.msgSeverityByHourRaw) {
    series = labels.map(
      (h) =>
        Number(
          (data.msgSeverityByHourRaw[h] || {})[state.msgSeverityFilter] || 0,
        ),
    );
    label = `Alarmas por hora — Msg Severity: ${state.msgSeverityFilter}`;
    return { labels, data: series, label };
  }

  if (state.levelFilter && data.levelCountsByHourRaw) {
    series = labels.map(
      (h) => Number((data.levelCountsByHourRaw[h] || {})[state.levelFilter] || 0),
    );
    label = `Alarmas por hora — Level: ${state.levelFilter}`;
    return { labels, data: series, label };
  }

  return { labels, data: series, label };
}

/* =========================================================
 *  ACCIONES (barra)
 * =======================================================*/
export function actionDataForCurrentFilter(state) {
  const { canonicalDeviceKey } = data;

  if (
    state.deviceFilter &&
    data.actionByDev?.[canonicalDeviceKey(state.deviceFilter)]
  ) {
    const m = data.actionByDev[canonicalDeviceKey(state.deviceFilter)];
    const keys = Object.keys(m);
    return {
      labels: keys.map(prettyActionLabel),
      data: keys.map((k) => Number(m[k] || 0)),
      keys,
    };
  }
  if (state.severityFilter) {
    const realSev = findKeyCI(data.sevToAct, state.severityFilter);
    if (realSev && data.sevToAct[realSev]) {
      const m = data.sevToAct[realSev];
      const keys = Object.keys(m);
      return {
        labels: keys.map(prettyActionLabel),
        data: keys.map((k) => Number(m[k] || 0)),
        keys,
      };
    }
  }
  if (
    state.msgSeverityFilter &&
    data.actionByMsgSeverityRaw?.[state.msgSeverityFilter]
  ) {
    const m = data.actionByMsgSeverityRaw[state.msgSeverityFilter];
    const keys = Object.keys(m);
    return {
      labels: keys.map(prettyActionLabel),
      data: keys.map((k) => Number(m[k] || 0)),
      keys,
    };
  }
  if (state.hourFilter && data.actByHourNorm?.[state.hourFilter]) {
    const m = data.actByHourNorm[state.hourFilter];
    const keys = Object.keys(m);
    return {
      labels: keys.map(prettyActionLabel),
      data: keys.map((k) => Number(m[k] || 0)),
      keys,
    };
  }
  if (state.levelFilter && data.actionByLevelRaw) {
    const levKey =
      findKeyCI(data.actionByLevelRaw, state.levelFilter) ??
      state.levelFilter;
    const per = data.actionByLevelRaw[levKey] || {};
    const keys = Object.keys(per);
    return {
      labels: keys.map(prettyActionLabel),
      data: keys.map((k) => Number(per[k] || 0)),
      keys,
    };
  }
  if (state.subtypeFilter && data.actionBySubtypeRaw) {
    const subKey =
      findKeyCI(data.actionBySubtypeRaw, state.subtypeFilter) ??
      state.subtypeFilter;
    const per = data.actionBySubtypeRaw[subKey] || {};
    const keys = Object.keys(per);
    return {
      labels: keys.map(prettyActionLabel),
      data: keys.map((k) => Number(per[k] || 0)),
      keys,
    };
  }
  if (state.logDescriptionFilter && data.actionByLogDescRaw) {
    const logKey =
      findKeyCI(data.actionByLogDescRaw, state.logDescriptionFilter) ??
      state.logDescriptionFilter;
    const per = data.actionByLogDescRaw[logKey] || {};
    const keys = Object.keys(per);
    return {
      labels: keys.map(prettyActionLabel),
      data: keys.map((k) => Number(per[k] || 0)),
      keys,
    };
  }

  const m = normalizeMapValues(data.actionCountsRaw);
  const keys = Object.keys(m);
  return {
    labels: keys.map(prettyActionLabel),
    data: keys.map((k) => Number(m[k] || 0)),
    keys,
  };
}

/* =========================================================
 *  MSG SEVERITY (barra)
 * =======================================================*/
export function msgSeverityDataForCurrentFilter(state) {
  const { canonicalDeviceKey } = data;

  if (state.deviceFilter && data.deviceByMsgSeverityRaw) {
    const devKey = canonicalDeviceKey(state.deviceFilter);
    const map = {};
    Object.entries(data.deviceByMsgSeverityRaw).forEach(
      ([msg, perDev]) => {
        map[msg] = Number((perDev || {})[devKey] || 0);
      },
    );
    const keys = Object.keys(map);
    return {
      labels: keys,
      data: keys.map((k) => map[k]),
      keys,
      colors: keys.map(colorForMsgSeverity),
    };
  }

  if (state.severityFilter && data.severityByMsgSeverityRaw) {
    const map = {};
    Object.entries(data.severityByMsgSeverityRaw).forEach(
      ([msg, perSev]) => {
        const k =
          findKeyCI(perSev, state.severityFilter) || state.severityFilter;
        map[msg] = Number((perSev || {})[k] || 0);
      },
    );
    const keys = Object.keys(map);
    return {
      labels: keys,
      data: keys.map((k) => map[k]),
      keys,
      colors: keys.map(colorForMsgSeverity),
    };
  }

  if (state.actionFilter && data.actionByMsgSeverityRaw) {
    const map = {};
    Object.entries(data.actionByMsgSeverityRaw).forEach(
      ([msg, perAct]) => {
        const per = perAct || {};
        const real =
          findKeyCI(per, state.actionFilter) ?? state.actionFilter;
        map[msg] = Number(per[real] || 0);
      },
    );
    const keys = Object.keys(map);
    return {
      labels: keys,
      data: keys.map((k) => map[k]),
      keys,
      colors: keys.map(colorForMsgSeverity),
    };
  }

  if (state.hourFilter && data.msgSeverityByHourRaw?.[state.hourFilter]) {
    const m = data.msgSeverityByHourRaw[state.hourFilter] || {};
    const keys = Object.keys(m);
    return {
      labels: keys,
      data: keys.map((k) => Number(m[k] || 0)),
      keys,
      colors: keys.map(colorForMsgSeverity),
    };
  }

  if (state.levelFilter && data.msgSeverityByLevelRaw) {
    const levKey =
      findKeyCI(data.msgSeverityByLevelRaw, state.levelFilter) ??
      state.levelFilter;
    const per = data.msgSeverityByLevelRaw[levKey] || {};
    const labels = Object.keys(per);
    return {
      labels,
      data: labels.map((k) => Number(per[k] || 0)),
      keys: labels,
      colors: labels.map(colorForMsgSeverity),
    };
  }

  if (state.subtypeFilter && data.msgSeverityBySubtypeRaw) {
    const subKey =
      findKeyCI(data.msgSeverityBySubtypeRaw, state.subtypeFilter) ??
      state.subtypeFilter;
    const per = data.msgSeverityBySubtypeRaw[subKey] || {};
    const labels = Object.keys(per);
    return {
      labels,
      data: labels.map((k) => Number(per[k] || 0)),
      keys: labels,
      colors: labels.map(colorForMsgSeverity),
    };
  }

  if (state.logDescriptionFilter && data.severityByLogDescRaw) {
    const logKey =
      findKeyCI(data.severityByLogDescRaw, state.logDescriptionFilter) ??
      state.logDescriptionFilter;
    const perSev = data.severityByLogDescRaw[logKey] || {};
    const labels = Object.keys(perSev);
    return {
      labels,
      data: labels.map((k) => Number(perSev[k] || 0)),
      keys: labels,
      colors: labels.map(colorForMsgSeverity),
    };
  }

  const m = normalizeMapValues(data.msgSeverityCountsRaw);
  const keys = Object.keys(m);
  return {
    labels: keys,
    data: keys.map((k) => Number(m[k] || 0)),
    keys,
    colors: keys.map(colorForMsgSeverity),
  };
}

/* =========================================================
 *  LEVEL / SUBTYPE (barras)
 * =======================================================*/
export function levelDataForCurrentFilter(state) {
  if (state.deviceFilter && data.deviceByLevelRaw) {
    const devKey = data.canonicalDeviceKey(state.deviceFilter);
    const map = {};
    Object.entries(data.deviceByLevelRaw).forEach(
      ([level, perDev]) => {
        map[level] = Number((perDev || {})[devKey] || 0);
      },
    );
    const labels = Object.keys(map);
    return { labels, data: labels.map((k) => map[k]), keys: labels };
  }
  if (state.actionFilter && data.actionByLevelRaw) {
    const per = data.actionByLevelRaw;
    const map = {};
    Object.entries(per || {}).forEach(([level, perAct]) => {
      const real =
        findKeyCI(perAct, state.actionFilter) ?? state.actionFilter;
      map[level] = Number((perAct || {})[real] || 0);
    });
    const labels = Object.keys(map);
    return { labels, data: labels.map((k) => map[k]), keys: labels };
  }
  if (state.severityFilter && data.severityByLevelRaw) {
    const per = data.severityByLevelRaw;
    const map = {};
    Object.entries(per || {}).forEach(([level, perSev]) => {
      const realSev =
        findKeyCI(perSev, state.severityFilter) || state.severityFilter;
      map[level] = Number((perSev || {})[realSev] || 0);
    });
    const labels = Object.keys(map);
    return { labels, data: labels.map((k) => map[k]), keys: labels };
  }

  if (state.hourFilter && data.levelCountsByHourRaw) {
    const map = data.levelCountsByHourRaw[state.hourFilter] || {};
    const labels = Object.keys(map);
    return { labels, data: labels.map((k) => Number(map[k] || 0)), keys: labels };
  }

  if (state.msgSeverityFilter && data.levelByMsgSeverityRaw) {
    const msgKey =
      findKeyCI(data.levelByMsgSeverityRaw, state.msgSeverityFilter) ??
      state.msgSeverityFilter;
    const per = data.levelByMsgSeverityRaw[msgKey] || {};
    const labels = Object.keys(per);
    return { labels, data: labels.map((k) => Number(per[k] || 0)), keys: labels };
  }

  if (state.subtypeFilter && data.levelBySubtypeRaw) {
    const stKey =
      findKeyCI(data.levelBySubtypeRaw, state.subtypeFilter) ??
      state.subtypeFilter;
    const per = data.levelBySubtypeRaw[stKey] || {};
    const labels = Object.keys(per);
    return { labels, data: labels.map((k) => Number(per[k] || 0)), keys: labels };
  }

  const m = normalizeMapValues(data.levelCountsRaw);
  const labels = Object.keys(m);
  return { labels, data: labels.map((k) => Number(m[k] || 0)), keys: labels };
}

export function subtypeDataForCurrentFilter(state) {
  if (state.deviceFilter && data.deviceBySubtypeRaw) {
    const devKey = data.canonicalDeviceKey(state.deviceFilter);
    const map = {};
    Object.entries(data.deviceBySubtypeRaw).forEach(
      ([sub, perDev]) => {
        map[sub] = Number((perDev || {})[devKey] || 0);
      },
    );
    const labels = Object.keys(map);
    return { labels, data: labels.map((k) => map[k]), keys: labels };
  }
  if (state.actionFilter && data.actionBySubtypeRaw) {
    const per = data.actionBySubtypeRaw;
    const map = {};
    Object.entries(per || {}).forEach(([sub, perAct]) => {
      const real =
        findKeyCI(perAct, state.actionFilter) ?? state.actionFilter;
      map[sub] = Number((perAct || {})[real] || 0);
    });
    const labels = Object.keys(map);
    return { labels, data: labels.map((k) => map[k]), keys: labels };
  }

  if (state.msgSeverityFilter && data.subtypeByMsgSeverityRaw) {
    const msgKey =
      findKeyCI(data.subtypeByMsgSeverityRaw, state.msgSeverityFilter) ??
      state.msgSeverityFilter;
    const per = data.subtypeByMsgSeverityRaw[msgKey] || {};
    const labels = Object.keys(per);
    return { labels, data: labels.map((k) => Number(per[k] || 0)), keys: labels };
  }

  if (state.hourFilter && data.subtypeByHourRaw) {
    const map = data.subtypeByHourRaw[state.hourFilter] || {};
    const labels = Object.keys(map);
    return { labels, data: labels.map((k) => Number(map[k] || 0)), keys: labels };
  }

  if (state.levelFilter && data.subtypeByLevelRaw) {
    const levKey =
      findKeyCI(data.subtypeByLevelRaw, state.levelFilter) ??
      state.levelFilter;
    const per = data.subtypeByLevelRaw[levKey] || {};
    const labels = Object.keys(per);
    return { labels, data: labels.map((k) => Number(per[k] || 0)), keys: labels };
  }

  if (state.severityFilter && data.severityBySubtypeRaw) {
    const per = data.severityBySubtypeRaw;
    const map = {};
    Object.entries(per || {}).forEach(([sub, perSev]) => {
      const realSev =
        findKeyCI(perSev, state.severityFilter) || state.severityFilter;
      map[sub] = Number((perSev || {})[realSev] || 0);
    });
    const labels = Object.keys(map);
    return { labels, data: labels.map((k) => map[k]), keys: labels };
  }

  const m = normalizeMapValues(data.subtypeCountsRaw);
  const labels = Object.keys(m);
  return { labels, data: labels.map((k) => Number(m[k] || 0)), keys: labels };
}

/* =========================================================
 *  LOG DESCRIPTION (barras)
 * =======================================================*/
export function logDescriptionDataForCurrentFilter(state) {
  if (state.deviceFilter && data.deviceByLogDescRaw) {
    const devKey = data.canonicalDeviceKey(state.deviceFilter);
    const map = {};
    Object.entries(data.deviceByLogDescRaw).forEach(
      ([desc, perDev]) => {
        map[desc] = Number((perDev || {})[devKey] || 0);
      },
    );
    const keys = Object.keys(map);
    return { labels: keys, data: keys.map((k) => map[k]), keys };
  }
  if (state.actionFilter && data.actionByLogDescRaw) {
    const map = {};
    Object.entries(data.actionByLogDescRaw).forEach(
      ([desc, perAct]) => {
        const per = perAct || {};
        const real =
          findKeyCI(per, state.actionFilter) ?? state.actionFilter;
        map[desc] = Number(per[real] || 0);
      },
    );
    const keys = Object.keys(map);
    return { labels: keys, data: keys.map((k) => map[k]), keys };
  }
  if (state.severityFilter && data.severityByLogDescRaw) {
    const map = {};
    Object.entries(data.severityByLogDescRaw).forEach(
      ([desc, perSev]) => {
        const realSev =
          findKeyCI(perSev, state.severityFilter) || state.severityFilter;
        map[desc] = Number((perSev || {})[realSev] || 0);
      },
    );
    const keys = Object.keys(map);
    return { labels: keys, data: keys.map((k) => map[k]), keys };
  }

  const m = normalizeMapValues(data.logDescCountsRaw);
  const keys = Object.keys(m);
  return { labels: keys, data: keys.map((k) => Number(m[k] || 0)), keys };
}

/* =========================================================
 *  TABLA DISPOSITIVOS
 * =======================================================*/
export function deviceRowsForCurrentFilter(state) {
  if (state.hourFilter && data.devByHourRaw?.[state.hourFilter]) {
    return top10(data.devByHourRaw[state.hourFilter]);
  }
  if (
    state.msgSeverityFilter &&
    data.deviceByMsgSeverityRaw?.[state.msgSeverityFilter]
  ) {
    return top10(data.deviceByMsgSeverityRaw[state.msgSeverityFilter] || {});
  }
  if (state.actionFilter && data.deviceByAction?.[state.actionFilter]) {
    return top10(data.deviceByAction[state.actionFilter] || {});
  }
  if (state.levelFilter && data.deviceByLevelRaw) {
    const levKey =
      findKeyCI(data.deviceByLevelRaw, state.levelFilter) ??
      state.levelFilter;
    return top10(data.deviceByLevelRaw[levKey] || {});
  }
  if (state.subtypeFilter && data.deviceBySubtypeRaw) {
    const subKey =
      findKeyCI(data.deviceBySubtypeRaw, state.subtypeFilter) ??
      state.subtypeFilter;
    return top10(data.deviceBySubtypeRaw[subKey] || {});
  }
  if (state.logDescriptionFilter && data.deviceByLogDescRaw) {
    const logKey =
      findKeyCI(data.deviceByLogDescRaw, state.logDescriptionFilter) ??
      state.logDescriptionFilter;
    return top10(data.deviceByLogDescRaw[logKey] || {});
  }

  const bySev = readJSON("device-counts-by-severity") || {};
  if (state.severityFilter && bySev[state.severityFilter]) {
    return top10(bySev[state.severityFilter]);
  }
  return top10(data.deviceCountsAll);
}

/* =========================================================
 *  KPI: HORA PUNTA
 * =======================================================*/
export function getPeakHour(/* state no usado por ahora */) {
  const series = Array.isArray(data.hourData) ? data.hourData : [];

  let arr = series;
  if (!arr.length) {
    const sevByHour = data.sevByHourRaw || {};
    const tmp = new Array(24).fill(0);
    for (const [hh, m] of Object.entries(sevByHour)) {
      const h = Number(hh);
      if (Number.isInteger(h) && h >= 0 && h <= 23) {
        tmp[h] = Object.values(m || {}).reduce(
          (a, b) => a + (Number(b) || 0),
          0,
        );
      }
    }
    arr = tmp;
  }

  let max = -1,
    idx = -1;
  for (let i = 0; i < 24; i++) {
    const v = Number(arr[i] || 0);
    if (v > max) {
      max = v;
      idx = i;
    }
  }
  return {
    hour: idx >= 0 ? String(idx).padStart(2, "0") : null,
    count: Math.max(0, max),
  };
}
