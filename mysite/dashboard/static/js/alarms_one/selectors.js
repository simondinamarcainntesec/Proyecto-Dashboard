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
function top10(m) { return Object.entries(m).sort((a,b)=>b[1]-a[1]).slice(0,10); }

function applySeveritySlice(counts, severityFilter) {
  if (!severityFilter) return counts;
  const realKey = findKeyCI(counts, severityFilter) || severityFilter;
  const v = Number(counts[realKey] || 0);
  return { [realKey]: v };
}

// pivots → severidad (para donut/KPI)
function sevForDevice(device) {
  const dev = data.canonicalDeviceKey(device);
  const out = {};
  Object.keys(data.deviceBySevFullRaw || {}).forEach((sev) => {
    const m = (data.deviceBySevFullRaw[sev] || {});
    out[String(sev).trim()] = Number(m[dev] || 0);
  });
  return out;
}
function sevForAction(actionKey) {
  const m = data.actToSev[actionKey] || {};
  const out = {}; Object.keys(m).forEach((sev) => out[sev] = Number(m[sev] || 0));
  return out;
}
function sevForHour(hour) {
  const m = data.sevByHourRaw?.[hour] || {};
  const out = {}; Object.keys(m).forEach((sev)=> out[String(sev).trim()] = Number(m[sev]||0));
  return out;
}
function sevForMsgSeverity(msg) {
  const m = data.severityByMsgSeverityRaw?.[msg] || {};
  const out = {}; Object.keys(m).forEach((sev)=> out[String(sev).trim()] = Number(m[sev]||0));
  return out;
}
function sevForLevel(level) {
  const real = findKeyCI(data.severityByLevelRaw, level) ?? level;
  const per = data.severityByLevelRaw?.[real] || {};
  const out = {}; Object.keys(per).forEach((sev)=> out[String(sev).trim()] = Number(per[sev]||0));
  return out;
}
function sevForSubtype(subtype) {
  const real = findKeyCI(data.severityBySubtypeRaw, subtype) ?? subtype;
  const per = data.severityBySubtypeRaw?.[real] || {};
  const out = {}; Object.keys(per).forEach((sev)=> out[String(sev).trim()] = Number(per[sev]||0));
  return out;
}
function sevForLogDesc(desc) {
  const real = findKeyCI(data.severityByLogDescRaw, desc) ?? desc;
  const per = data.severityByLogDescRaw?.[real] || {};
  const out = {}; Object.keys(per).forEach((sev)=> out[String(sev).trim()] = Number(per[sev]||0));
  return out;
}

// filtro activo (prioridad única)
function activePivot(state) {
  return (
    state.deviceFilter && ["device", state.deviceFilter] ||
    state.actionFilter && ["action", state.actionFilter] ||
    state.hourFilter && ["hour", state.hourFilter] ||
    state.msgSeverityFilter && ["msg", state.msgSeverityFilter] ||
    state.levelFilter && ["level", state.levelFilter] ||
    state.subtypeFilter && ["subtype", state.subtypeFilter] ||
    state.logDescriptionFilter && ["logdesc", state.logDescriptionFilter] ||
    state.severityFilter && ["severity", state.severityFilter] ||
    ["none",""]
  );
}

/* =========================================================
 *  DONUT / KPIs
 * =======================================================*/
export function getActiveCounts(state) {
  const [kind, key] = activePivot(state);

  let base;
  switch (kind) {
    case "device":  base = sevForDevice(key); break;
    case "action":  base = sevForAction(key); break;
    case "hour":    base = sevForHour(key); break;
    case "msg":     base = sevForMsgSeverity(key); break;
    case "level":   base = sevForLevel(key); break;
    case "subtype": base = sevForSubtype(key); break;
    case "logdesc": base = sevForLogDesc(key); break;
    default:        base = data.severityCounts; break; // si el pivot ya es severity, luego se recorta
  }

  base = normalizeCountsLabels(base);
  base = applySeveritySlice(base, state.severityFilter);
  if (!base || Object.keys(base).length === 0) return { "N/A": 0 };
  return base;
}

export function calcKpis(state) {
  const counts = getActiveCounts(state);
  let total = Object.values(counts).reduce((a, b) => a + (Number(b) || 0), 0);

  // Ajuste device → usa total del device
  if (state.deviceFilter && !state.severityFilter) {
    const dk = data.canonicalDeviceKey(state.deviceFilter);
    if (data.deviceCountsAll && Object.prototype.hasOwnProperty.call(data.deviceCountsAll, dk)) {
      total = Number(data.deviceCountsAll[dk] || 0);
    }
  }
  const high = (counts["high"] || 0) + (counts["critical"] || 0);
  const devices = state.deviceFilter ? 1 : Object.keys(data.deviceCountsAll).length;
  return { total, high, devices };
}

/* =========================================================
 *  (NUEVO) SEVERIDAD ALARMA (barra) → cambia a MSG_SEVERITY si hay level
 * =======================================================*/
// << NUEVO: función para el bar de “Severidad Alarma”
export function severityBarDataForCurrentFilter(state) {
  // CASO 1: Hay un level seleccionado
  // => mostrar msg_severity (campo msg_severity del modelo) para ese level
  if (state.levelFilter && data.msgSeverityByLevelRaw) {
    // data.msgSeverityByLevelRaw viene de build_msg_severity_by_level
    // {
    //   "notice": { "high": 1485, "medium": 972, ... },
    //   "critical": { "high": 983, ... },
    //   ...
    // }

    const levKey =
      findKeyCI(data.msgSeverityByLevelRaw, state.levelFilter) ??
      state.levelFilter;

    const per = data.msgSeverityByLevelRaw[levKey] || {};

    const labels = Object.keys(per); // ["high","medium","low",...]
    const values = labels.map(k => Number(per[k] || 0));

    return {
      labels,
      data: values,
      keys: labels,   // importante para el click handler
      mode: "msg",    // <- esto le dice al chart "estoy mostrando msg_severity"
    };
  }

  // CASO 2: No hay level seleccionado
  // => mostramos severidad clásica (campo severity, el de tu donut)
  //    Esto mantiene tu comportamiento anterior cuando nadie clickeó nada.
  const m = normalizeMapValues(data.severityCounts);
  const labels = Object.keys(m);
  const values = labels.map(k => Number(m[k] || 0));

  return {
    labels,
    data: values,
    keys: labels,
    mode: "severity", // <- ahora esto explícitamente significa "campo severity"
  };
}


/* =========================================================
 *  TREND (Alarmas por día)
 * =======================================================*/
export function trendDataForCurrentFilter(state) {
  // Helper local para armar la config del chart
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

  // === Helpers de totales ===
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
    (Array.isArray(data.trendData) && data.trendData.length)
      ? data.trendData
      : sumSeveritySeries();

  // === Filtros específicos (igual que antes) ===
  if (state.deviceFilter && data.trendByDevice?.[canonicalDeviceKey(state.deviceFilter)]) {
    const dk = canonicalDeviceKey(state.deviceFilter);
    return baseTrend(data.trendLabels, [
      { label: dk, data: data.trendByDevice[dk], color: "#60A5FA" },
    ]);
  }
  if (state.actionFilter && data.trendByAction?.[state.actionFilter]) {
    return baseTrend(data.trendLabels, [
      { label: `Acción: ${prettyActionLabel(state.actionFilter)}`, data: data.trendByAction[state.actionFilter], color: "#8B5CF6" },
    ]);
  }
  if (state.hourFilter && data.trendByHourRaw?.[state.hourFilter]) {
    const series = data.trendByHourRaw[state.hourFilter] || [];
    return baseTrend(data.trendLabelsHour, [
      { label: `Hora ${state.hourFilter}:00`, data: series, color: "#0EA5E9" },
    ]);
  }
  if (state.msgSeverityFilter && data.trendByMsgSeverityRaw?.[state.msgSeverityFilter]) {
    return baseTrend(data.trendLabels, [
      { label: `Severidad Alarma: ${state.msgSeverityFilter}`, data: data.trendByMsgSeverityRaw[state.msgSeverityFilter], color: "#F43F5E" },
    ]);
  }
  if (state.levelFilter && data.trendByLevel?.[state.levelFilter]) {
    return baseTrend(data.trendLabels, [
      { label: `Level: ${state.levelFilter}`, data: data.trendByLevel[state.levelFilter], color: "#0EA5E9" },
    ]);
  }
  if (state.subtypeFilter && data.trendBySubtype?.[state.subtypeFilter]) {
    return baseTrend(data.trendLabels, [
      { label: `Subtype: ${state.subtypeFilter}`, data: data.trendBySubtype[state.subtypeFilter], color: "#22C55E" },
    ]);
  }

  // === Si hay filtro de severidad puntual ===
  if (state.severityFilter) {
    const want = String(state.severityFilter).trim().toLowerCase();
    const map = data.severityTrendsMap || {};
    const matchKey = Object.keys(map).find(
      (k) => String(k).trim().toLowerCase() === want
    );
    const series = (matchKey && map[matchKey]?.data?.length)
      ? map[matchKey].data
      : new Array(labels.length).fill(0);
    return baseTrend(labels, [
      { label: matchKey || want, data: series, color: "#60A5FA" },
    ]);
  }

  // === Default: TOTAL (sin desgloses) ===
  return baseTrend(labels, [
    { label: "Alarmas por día", data: totalSeries, color: "#60A5FA" },
  ]);
}


/* =========================================================
 *  HOURLY (Alarmas por hora)
 * =======================================================*/
export function hourDataForCurrentFilter(state) {
  const labels = data.hourLabels || [];          // "00".."23"
  let series = data.hourData || [];              // total por hora
  let label = "Alarmas (por hora, rango actual)";

  // ── PRIORIDAD ABSOLUTA: SUBTYPE
  if (state.subtypeFilter) {
    const json = data.hourSeriesBySubtypeRaw || {};
    const keys = Object.keys(json || {});
    console.debug("[hourly] subtypeFilter:", state.subtypeFilter, "keys json:", keys.length ? keys.slice(0,5) : keys);

    if (keys.length) {
      const subKey = findKeyCI(json, state.subtypeFilter) ?? state.subtypeFilter;
      const arr = json[subKey] || [];
      console.debug("[hourly] usando hour-series-by-subtype →", subKey, "len:", arr?.length);

      series = Array.isArray(arr) ? labels.map((_, i) => Number(arr[i] || 0)) : labels.map(() => 0);
      label = `Alarmas por hora — Subtype: ${subKey}`;
      return { labels, data: series, label };
    }

    // Fallback si por alguna razón el JSON exclusivo no está disponible
    const map = data.subtypeByHourRaw || {};
    console.debug("[hourly] fallback subtypeByHourRaw");
    series = labels.map((h) => Number((map[h] || {})[state.subtypeFilter] || 0));
    label = `Alarmas por hora — Subtype: ${state.subtypeFilter}`;
    return { labels, data: series, label };
  }

  // Device
  if (state.deviceFilter && data.devByHourRaw) {
    const dk = data.canonicalDeviceKey(state.deviceFilter);
    series = labels.map((h) => Number((data.devByHourRaw[h] || {})[dk] || 0));
    label = `Alarmas por hora — Dispositivo: ${dk}`;
    return { labels, data: series, label };
  }

  // Severidad
  if (state.severityFilter && data.sevByHourRaw) {
    series = labels.map((h) => {
      const m = data.sevByHourRaw[h] || {};
      const hk = findKeyCI(m, state.severityFilter) || state.severityFilter;
      return Number(m[hk] || 0);
    });
    label = `Alarmas por hora — Severidad: ${state.severityFilter}`;
    return { labels, data: series, label };
  }

  // Acción
  if (state.actionFilter && data.actByHourNorm) {
    series = labels.map((h) => Number((data.actByHourNorm[h] || {})[state.actionFilter] || 0));
    label = `Alarmas por hora — Acción: ${state.actionFilter}`;
    return { labels, data: series, label };
  }

  // Msg Severity
  if (state.msgSeverityFilter && data.msgSeverityByHourRaw) {
    series = labels.map((h) => Number((data.msgSeverityByHourRaw[h] || {})[state.msgSeverityFilter] || 0));
    label = `Alarmas por hora — Msg Severity: ${state.msgSeverityFilter}`;
    return { labels, data: series, label };
  }

  // Level
  if (state.levelFilter && data.levelCountsByHourRaw) {
    series = labels.map((h) => Number((data.levelCountsByHourRaw[h] || {})[state.levelFilter] || 0));
    label = `Alarmas por hora — Level: ${state.levelFilter}`;
    return { labels, data: series, label };
  }

  // Default
  return { labels, data: series, label };
}

/* =========================================================
 *  ACCIONES (barra)
 * =======================================================*/
export function actionDataForCurrentFilter(state) {
  const { canonicalDeviceKey } = data;

  if (state.deviceFilter && data.actionByDev?.[canonicalDeviceKey(state.deviceFilter)]) {
    const m = data.actionByDev[canonicalDeviceKey(state.deviceFilter)];
    const keys = Object.keys(m);
    return { labels: keys.map(prettyActionLabel), data: keys.map(k => Number(m[k] || 0)), keys };
  }
  if (state.severityFilter) {
    const realSev = findKeyCI(data.sevToAct, state.severityFilter);
    if (realSev && data.sevToAct[realSev]) {
      const m = data.sevToAct[realSev];
      const keys = Object.keys(m);
      return { labels: keys.map(prettyActionLabel), data: keys.map(k => Number(m[k] || 0)), keys };
    }
  }
  if (state.msgSeverityFilter && data.actionByMsgSeverityRaw?.[state.msgSeverityFilter]) {
    const m = data.actionByMsgSeverityRaw[state.msgSeverityFilter];
    const keys = Object.keys(m);
    return { labels: keys.map(prettyActionLabel), data: keys.map(k => Number(m[k] || 0)), keys };
  }
  if (state.hourFilter && data.actByHourNorm?.[state.hourFilter]) {
    const m = data.actByHourNorm[state.hourFilter];
    const keys = Object.keys(m);
    return { labels: keys.map(prettyActionLabel), data: keys.map(k => Number(m[k] || 0)), keys };
  }
  // NUEVOS: Level/Subtype/LogDesc
  if (state.levelFilter && data.actionByLevelRaw) {
    const levKey = findKeyCI(data.actionByLevelRaw, state.levelFilter) ?? state.levelFilter;
    const per = data.actionByLevelRaw[levKey] || {};
    const keys = Object.keys(per);
    return { labels: keys.map(prettyActionLabel), data: keys.map(k => Number(per[k] || 0)), keys };
  }
  if (state.subtypeFilter && data.actionBySubtypeRaw) {
    const subKey = findKeyCI(data.actionBySubtypeRaw, state.subtypeFilter) ?? state.subtypeFilter;
    const per = data.actionBySubtypeRaw[subKey] || {};
    const keys = Object.keys(per);
    return { labels: keys.map(prettyActionLabel), data: keys.map(k => Number(per[k] || 0)), keys };
  }
  if (state.logDescriptionFilter && data.actionByLogDescRaw) {
    const logKey = findKeyCI(data.actionByLogDescRaw, state.logDescriptionFilter) ?? state.logDescriptionFilter;
    const per = data.actionByLogDescRaw[logKey] || {};
    const keys = Object.keys(per);
    return { labels: keys.map(prettyActionLabel), data: keys.map(k => Number(per[k] || 0)), keys };
  }

  const m = normalizeMapValues(data.actionCountsRaw);
  const keys = Object.keys(m);
  return { labels: keys.map(prettyActionLabel), data: keys.map(k => Number(m[k] || 0)), keys };
}

/* =========================================================
 *  MSG SEVERITY (barra)
 * =======================================================*/
export function msgSeverityDataForCurrentFilter(state) {
  const { canonicalDeviceKey } = data;

  // Device → msg_severity por dispositivo
  if (state.deviceFilter && data.deviceByMsgSeverityRaw) {
    const devKey = canonicalDeviceKey(state.deviceFilter);
    const map = {};
    Object.entries(data.deviceByMsgSeverityRaw).forEach(([msg, perDev]) => {
      map[msg] = Number((perDev || {})[devKey] || 0);
    });
    const keys = Object.keys(map);
    return { labels: keys, data: keys.map(k => map[k]), keys, colors: keys.map(colorForMsgSeverity) };
  }

  // Severidad base → distribución de msg_severity dentro de esa severidad (si existe)
  if (state.severityFilter && data.severityByMsgSeverityRaw) {
    const map = {};
    Object.entries(data.severityByMsgSeverityRaw).forEach(([msg, perSev]) => {
      const k = findKeyCI(perSev, state.severityFilter) || state.severityFilter;
      map[msg] = Number((perSev || {})[k] || 0);
    });
    const keys = Object.keys(map);
    return { labels: keys, data: keys.map(k => map[k]), keys, colors: keys.map(colorForMsgSeverity) };
  }

  // Acción → msg_severity por acción
  if (state.actionFilter && data.actionByMsgSeverityRaw) {
    const map = {};
    Object.entries(data.actionByMsgSeverityRaw).forEach(([msg, perAct]) => {
      const per = perAct || {};
      const real = findKeyCI(per, state.actionFilter) ?? state.actionFilter;
      map[msg] = Number(per[real] || 0);
    });
    const keys = Object.keys(map);
    return { labels: keys, data: keys.map(k => map[k]), keys, colors: keys.map(colorForMsgSeverity) };
  }

  // Hora → msg_severity por hora
  if (state.hourFilter && data.msgSeverityByHourRaw?.[state.hourFilter]) {
    const m = data.msgSeverityByHourRaw[state.hourFilter] || {};
    const keys = Object.keys(m);
    return { labels: keys, data: keys.map(k => Number(m[k] || 0)), keys, colors: keys.map(colorForMsgSeverity) };
  }

  // NUEVO: Level → msg_severity por level (usa JSON exclusivo)
  if (state.levelFilter && data.msgSeverityByLevelRaw) {
    const levKey = findKeyCI(data.msgSeverityByLevelRaw, state.levelFilter) ?? state.levelFilter;
    const per = data.msgSeverityByLevelRaw[levKey] || {};
    const labels = Object.keys(per);
    return { labels, data: labels.map(k => Number(per[k] || 0)), keys: labels, colors: labels.map(colorForMsgSeverity) };
  }

  // NUEVO: Subtype → msg_severity por subtype (usa JSON exclusivo)
  if (state.subtypeFilter && data.msgSeverityBySubtypeRaw) {
    const subKey = findKeyCI(data.msgSeverityBySubtypeRaw, state.subtypeFilter) ?? state.subtypeFilter;
    const per = data.msgSeverityBySubtypeRaw[subKey] || {};
    const labels = Object.keys(per);
    return { labels, data: labels.map(k => Number(per[k] || 0)), keys: labels, colors: labels.map(colorForMsgSeverity) };
  }

  // (Opcional) Log Description → si quieres que también filtre por msg_severity,
  // crea un JSON similar en backend. Por ahora dejamos la rama original si la usabas:
  if (state.logDescriptionFilter && data.severityByLogDescRaw) {
    const logKey = findKeyCI(data.severityByLogDescRaw, state.logDescriptionFilter) ?? state.logDescriptionFilter;
    const perSev = data.severityByLogDescRaw[logKey] || {};
    const labels = Object.keys(perSev);
    return { labels, data: labels.map(k => Number(perSev[k] || 0)), keys: labels, colors: labels.map(colorForMsgSeverity) };
  }

  // Default global: msg_severity total
  const m = normalizeMapValues(data.msgSeverityCountsRaw);
  const keys = Object.keys(m);
  return { labels: keys, data: keys.map(k => Number(m[k] || 0)), keys, colors: keys.map(colorForMsgSeverity) };
}


/* =========================================================
 *  LEVEL / SUBTYPE (barras)
 * =======================================================*/
export function levelDataForCurrentFilter(state) {
  if (state.deviceFilter && data.deviceByLevelRaw) {
    const devKey = data.canonicalDeviceKey(state.deviceFilter);
    const map = {};
    Object.entries(data.deviceByLevelRaw).forEach(([level, perDev]) => {
      map[level] = Number((perDev || {})[devKey] || 0);
    });
    const labels = Object.keys(map);
    return { labels, data: labels.map(k=>map[k]), keys: labels };
  }
  if (state.actionFilter && data.actionByLevelRaw) {
    const per = data.actionByLevelRaw;
    const map = {};
    Object.entries(per || {}).forEach(([level, perAct]) => {
      const real = findKeyCI(perAct, state.actionFilter) ?? state.actionFilter;
      map[level] = Number((perAct || {})[real] || 0);
    });
    const labels = Object.keys(map);
    return { labels, data: labels.map(k=>map[k]), keys: labels };
  }
  if (state.severityFilter && data.severityByLevelRaw) {
    const per = data.severityByLevelRaw;
    const map = {};
    Object.entries(per || {}).forEach(([level, perSev]) => {
      const realSev = findKeyCI(perSev, state.severityFilter) || state.severityFilter;
      map[level] = Number((perSev || {})[realSev] || 0);
    });
    const labels = Object.keys(map);
    return { labels, data: labels.map(k=>map[k]), keys: labels };
  }

  // << NUEVO: Hora → Level
  if (state.hourFilter && data.levelCountsByHourRaw) {
    const map = data.levelCountsByHourRaw[state.hourFilter] || {};
    const labels = Object.keys(map);
    return { labels, data: labels.map(k => Number(map[k] || 0)), keys: labels };
  }
  // Msg severity → Level
  if (state.msgSeverityFilter && data.levelByMsgSeverityRaw) {
    const msgKey = findKeyCI(data.levelByMsgSeverityRaw, state.msgSeverityFilter) ?? state.msgSeverityFilter;
    const per = data.levelByMsgSeverityRaw[msgKey] || {};
    const labels = Object.keys(per);
    return { labels, data: labels.map(k => Number(per[k] || 0)), keys: labels };
  }


  // Subtype → Level (NUEVO)
  if (state.subtypeFilter && data.levelBySubtypeRaw) {
    const stKey = findKeyCI(data.levelBySubtypeRaw, state.subtypeFilter) ?? state.subtypeFilter;
    const per = data.levelBySubtypeRaw[stKey] || {};
    const labels = Object.keys(per);
    return { labels, data: labels.map(k => Number(per[k] || 0)), keys: labels };
  }

  const m = normalizeMapValues(data.levelCountsRaw);
  const labels = Object.keys(m);
  return { labels, data: labels.map(k => Number(m[k] || 0)), keys: labels };

}

export function subtypeDataForCurrentFilter(state) {
  if (state.deviceFilter && data.deviceBySubtypeRaw) {
    const devKey = data.canonicalDeviceKey(state.deviceFilter);
    const map = {};
    Object.entries(data.deviceBySubtypeRaw).forEach(([sub, perDev]) => {
      map[sub] = Number((perDev || {})[devKey] || 0);
    });
    const labels = Object.keys(map);
    return { labels, data: labels.map(k=>map[k]), keys: labels };
  }
  if (state.actionFilter && data.actionBySubtypeRaw) {
    const per = data.actionBySubtypeRaw;
    const map = {};
    Object.entries(per || {}).forEach(([sub, perAct]) => {
      const real = findKeyCI(perAct, state.actionFilter) ?? state.actionFilter;
      map[sub] = Number((perAct || {})[real] || 0);
    });
    const labels = Object.keys(map);
    return { labels, data: labels.map(k=>map[k]), keys: labels };
  }
    // Msg severity → Subtype
  if (state.msgSeverityFilter && data.subtypeByMsgSeverityRaw) {
    const msgKey = findKeyCI(data.subtypeByMsgSeverityRaw, state.msgSeverityFilter) ?? state.msgSeverityFilter;
    const per = data.subtypeByMsgSeverityRaw[msgKey] || {};
    const labels = Object.keys(per);
    return { labels, data: labels.map(k => Number(per[k] || 0)), keys: labels };
  }


  // << NUEVO: Hora → Subtype
  if (state.hourFilter && data.subtypeByHourRaw) {
    const map = data.subtypeByHourRaw[state.hourFilter] || {};
    const labels = Object.keys(map);
    return { labels, data: labels.map(k => Number(map[k] || 0)), keys: labels };
  }

  // Level → Subtype
  if (state.levelFilter && data.subtypeByLevelRaw) {
    const levKey = findKeyCI(data.subtypeByLevelRaw, state.levelFilter) ?? state.levelFilter;
    const per = data.subtypeByLevelRaw[levKey] || {};
    const labels = Object.keys(per);
    return { labels, data: labels.map(k => Number(per[k] || 0)), keys: labels };
  }

  if (state.severityFilter && data.severityBySubtypeRaw) {
    const per = data.severityBySubtypeRaw;
    const map = {};
    Object.entries(per || {}).forEach(([sub, perSev]) => {
      const realSev = findKeyCI(perSev, state.severityFilter) || state.severityFilter;
      map[sub] = Number((perSev || {})[realSev] || 0);
    });
    const labels = Object.keys(map);
    return { labels, data: labels.map(k=>map[k]), keys: labels };
  }
  const m = normalizeMapValues(data.subtypeCountsRaw);
  const labels = Object.keys(m);
  return { labels, data: labels.map(k => Number(m[k] || 0)), keys: labels };
}

/* =========================================================
 *  LOG DESCRIPTION (barras)
 * =======================================================*/
export function logDescriptionDataForCurrentFilter(state) {
  if (state.deviceFilter && data.deviceByLogDescRaw) {
    const devKey = data.canonicalDeviceKey(state.deviceFilter);
    const map = {};
    Object.entries(data.deviceByLogDescRaw).forEach(([desc, perDev]) => {
      map[desc] = Number((perDev || {})[devKey] || 0);
    });
    const keys = Object.keys(map);
    return { labels: keys, data: keys.map(k => map[k]), keys };
  }
  if (state.actionFilter && data.actionByLogDescRaw) {
    const map = {};
    Object.entries(data.actionByLogDescRaw).forEach(([desc, perAct]) => {
      const per = perAct || {};
      const real = findKeyCI(per, state.actionFilter) ?? state.actionFilter;
      map[desc] = Number(per[real] || 0);
    });
    const keys = Object.keys(map);
    return { labels: keys, data: keys.map(k => map[k]), keys };
  }
  if (state.severityFilter && data.severityByLogDescRaw) {
    const map = {};
    Object.entries(data.severityByLogDescRaw).forEach(([desc, perSev]) => {
      const realSev = findKeyCI(perSev, state.severityFilter) || state.severityFilter;
      map[desc] = Number((perSev || {})[realSev] || 0);
    });
    const keys = Object.keys(map);
    return { labels: keys, data: keys.map(k => map[k]), keys };
  }

  const m = normalizeMapValues(data.logDescCountsRaw);
  const keys = Object.keys(m);
  return { labels: keys, data: keys.map(k => Number(m[k] || 0)), keys };
}

/* =========================================================
 *  TABLA DISPOSITIVOS
 * =======================================================*/
export function deviceRowsForCurrentFilter(state) {
  if (state.hourFilter && data.devByHourRaw?.[state.hourFilter]) {
    return top10(data.devByHourRaw[state.hourFilter]);
  }
  if (state.msgSeverityFilter && data.deviceByMsgSeverityRaw?.[state.msgSeverityFilter]) {
    return top10(data.deviceByMsgSeverityRaw[state.msgSeverityFilter] || {});
  }
  if (state.actionFilter && data.deviceByAction?.[state.actionFilter]) {
    return top10(data.deviceByAction[state.actionFilter] || {});
  }
  if (state.levelFilter && data.deviceByLevelRaw) {
    const levKey = findKeyCI(data.deviceByLevelRaw, state.levelFilter) ?? state.levelFilter;
    return top10(data.deviceByLevelRaw[levKey] || {});
  }
  if (state.subtypeFilter && data.deviceBySubtypeRaw) {
    const subKey = findKeyCI(data.deviceBySubtypeRaw, state.subtypeFilter) ?? state.subtypeFilter;
    return top10(data.deviceBySubtypeRaw[subKey] || {});
  }
  if (state.logDescriptionFilter && data.deviceByLogDescRaw) {
    const logKey = findKeyCI(data.deviceByLogDescRaw, state.logDescriptionFilter) ?? state.logDescriptionFilter;
    return top10(data.deviceByLogDescRaw[logKey] || {});
  }

  const bySev = readJSON("device-counts-by-severity") || {};
  if (state.severityFilter && bySev[state.severityFilter]) {
    return top10(bySev[state.severityFilter]);
  }
  return top10(data.deviceCountsAll);
}

// Nuevo: mismos datos que getActiveCounts pero SIN recortar por severityFilter
export function getActiveCountsForDonut(state) {
  const [kind, key] = activePivot(state);

  let base;
  switch (kind) {
    case "device":  base = sevForDevice(key); break;
    case "action":  base = sevForAction(key); break;
    case "hour":    base = sevForHour(key); break;
    case "msg":     base = sevForMsgSeverity(key); break;
    case "level":   base = sevForLevel(key); break;
    case "subtype": base = sevForSubtype(key); break;
    case "logdesc": base = sevForLogDesc(key); break;
    default:        base = data.severityCounts; break;
  }

  base = normalizeCountsLabels(base);
  // OJO: aquí NO llamamos a applySeveritySlice
  if (!base || Object.keys(base).length === 0) return { "N/A": 0 };
  return base;
}
