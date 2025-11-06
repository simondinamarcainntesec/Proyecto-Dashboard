// data.js
import { readJSON, norm, normalizeMapValues } from "./utils.js";

/* ========== LECTURAS DESDE EL HTML (json_script) ========== */
const trendLabels = readJSON("trend-labels") || [];
const severityTrendsMap = readJSON("severity-trends") || {};
const trendByDevice = readJSON("trend-by-device") || {};
const severityCountsRaw = readJSON("severity-counts") || {};

const deviceCountsAll = readJSON("device-counts") || {};
const actionCountsRaw = readJSON("action-counts") || {};

const actionBySevRaw = readJSON("action-counts-by-severity") || {};
const actionByDevRaw = readJSON("action-counts-by-device") || {};
const trendByActionRaw = readJSON("trend-by-action") || {};
const deviceByActionRaw = readJSON("device-counts-by-action") || {};

const hourLabels = readJSON("hour-labels") || [];
const hourData = readJSON("hour-data") || [];
const sevByHourRaw = readJSON("severity-counts-by-hour") || {};
const devByHourRaw = readJSON("device-counts-by-hour") || {};
const actByHourRaw = readJSON("action-counts-by-hour") || {};
const trendLabelsHour = readJSON("trend-labels-hour") || [];
const trendByHourRaw = readJSON("trend-by-hour") || {};

const msgSeverityCountsRaw = readJSON("msg-severity-counts") || {};
const deviceByMsgSeverityRaw = readJSON("device-counts-by-msg-severity") || {};
const actionByMsgSeverityRaw = readJSON("action-counts-by-msg-severity") || {};
const severityByMsgSeverityRaw = readJSON("severity-counts-by-msg-severity") || {};
const msgSeverityByHourRaw = readJSON("msg-severity-counts-by-hour") || {};
const trendByMsgSeverityRaw = readJSON("trend-by-msg-severity") || {};

const deviceBySevFullRaw = readJSON("device-counts-by-severity-full") || {};

// === LEVEL y SUBTYPE ===
const levelCountsRaw = readJSON("level-counts") || {};
const deviceByLevelRaw = readJSON("device-counts-by-level") || {};
const actionByLevelRaw = readJSON("action-counts-by-level") || {};
const severityByLevelRaw = readJSON("severity-counts-by-level") || {};

const subtypeCountsRaw = readJSON("subtype-counts") || {};
const deviceBySubtypeRaw = readJSON("device-counts-by-subtype") || {};
const actionBySubtypeRaw = readJSON("action-counts-by-subtype") || {};
const severityBySubtypeRaw = readJSON("severity-counts-by-subtype") || {};

// Log Description
const logDescCountsRaw = readJSON("logdesc-counts") || {};
const deviceByLogDescRaw = readJSON("device-counts-by-logdesc") || {};
const actionByLogDescRaw = readJSON("action-counts-by-logdesc") || {};
const severityByLogDescRaw = readJSON("severity-counts-by-logdesc") || {};

// Level → Trend / Hourly / Subtype
const trendByLevel = readJSON("trend-by-level") || {};                 // { level: [c1,c2,...] }
const levelCountsByHourRaw = readJSON("level-counts-by-hour") || {};   // { "00": {level: n}, ... }
const subtypeByLevelRaw = readJSON("subtype-counts-by-level") || {};   // { level: { subtype: n } }

// Subtype → Trend / Hourly
const trendBySubtype = readJSON("trend-by-subtype") || {};             // { subtype: [..] }
const subtypeByHourRaw = readJSON("subtype-counts-by-hour") || {};     // { "00": { subtype: n }, ... }

// Subtype → Level (para cruzar Subtype -> Level)
const levelBySubtypeRaw = readJSON("level-counts-by-subtype") || {};
const msgSeverityByLevelRaw = readJSON("msg-severity-by-level") || {};       // { level: { msg: n } }
const msgSeverityBySubtypeRaw = readJSON("msg-severity-by-subtype") || {};
const levelByMsgSeverityRaw = readJSON("level-by-msg-severity") || {};     // { msg: { level: n } }
const subtypeByMsgSeverityRaw = readJSON("subtype-by-msg-severity") || {};
const hourSeriesBySubtypeRaw = readJSON("hour-series-by-subtype") || {}; // { msg: { subtype: n } }
   // { subtype: { level: n } }

/* ========== NORMALIZACIONES / ÍNDICES ========== */

// trendByAction normalizado por clave
const trendByAction = {};
Object.entries(trendByActionRaw).forEach(([k, arr]) => {
  trendByAction[norm(k)] = Array.isArray(arr) ? arr : [];
});

// deviceByAction con valores numéricos
const deviceByAction = {};
Object.entries(deviceByActionRaw).forEach(([k, m]) => {
  const inner = {};
  Object.entries(m || {}).forEach(([dev, val]) => (inner[dev] = Number(val || 0)));
  deviceByAction[norm(k)] = inner;
});

// actions por device (normaliza claves)
const actionByDev = {};
for (const [dev, m] of Object.entries(actionByDevRaw || {})) {
  actionByDev[dev] = normalizeMapValues(m || {});
}

// actions por hora (normaliza nombres de acciones)
const actByHourNorm = {};
for (const [h, map] of Object.entries(actByHourRaw || {})) {
  actByHourNorm[h] = normalizeMapValues(map || {});
}

// índices sev<->acción
const sevToAct = {};
const actToSev = {};
for (const [sevRaw, inner] of Object.entries(actionBySevRaw || {})) {
  const sevKey = String(sevRaw).trim();
  for (const [actRaw, val] of Object.entries(inner || {})) {
    const a = norm(actRaw);
    const n = Number(val || 0);
    if (!sevToAct[sevKey]) sevToAct[sevKey] = {};
    sevToAct[sevKey][a] = (sevToAct[sevKey][a] || 0) + n;
    if (!actToSev[a]) actToSev[a] = {};
    actToSev[a][sevKey] = (actToSev[a][sevKey] || 0) + n;
  }
}

// Canonicalización device (para clicks en tabla/horas)
const deviceKeys = Object.keys(deviceCountsAll || {});
function canonicalDeviceKey(input) {
  if (!input) return input;
  const needle = String(input).trim().toLowerCase();
  for (const k of deviceKeys) if (k === input) return k;
  for (const k of deviceKeys) if (String(k).trim().toLowerCase() === needle) return k;
  for (const sev of Object.keys(deviceBySevFullRaw || {})) {
    for (const dk of Object.keys(deviceBySevFullRaw[sev] || {})) {
      if (String(dk).trim().toLowerCase() === needle) return dk;
    }
  }
  return input;
}

// severityCounts (adaptando array/dict)
let severityCounts = (() => {
  if (!severityCountsRaw) return {};
  if (Array.isArray(severityCountsRaw)) {
    const out = {};
    severityCountsRaw.forEach((x) => {
      if (x && x.name != null) out[String(x.name).trim()] = Number(x.value || 0);
    });
    return out;
  }
  if (typeof severityCountsRaw === "object") {
    return Object.fromEntries(
      Object.entries(severityCountsRaw).map(([k, v]) => [String(k).trim(), Number(v || 0)])
    );
  }
  return {};
})();

/* ========== EXPORT ========== */
export default {
  trendLabels, severityTrendsMap, trendByDevice,
  severityCounts, deviceCountsAll, actionCountsRaw,
  actionBySevRaw, actionByDev, trendByAction, deviceByAction,

  hourLabels, hourData, sevByHourRaw, devByHourRaw, actByHourNorm,
  trendLabelsHour, trendByHourRaw,

  msgSeverityCountsRaw, deviceByMsgSeverityRaw, actionByMsgSeverityRaw,
  severityByMsgSeverityRaw, msgSeverityByHourRaw, trendByMsgSeverityRaw,

  deviceBySevFullRaw, sevToAct, actToSev, canonicalDeviceKey,

  // LEVEL y SUBTYPE
  levelCountsRaw, deviceByLevelRaw, actionByLevelRaw, severityByLevelRaw,
  subtypeCountsRaw, deviceBySubtypeRaw, actionBySubtypeRaw, severityBySubtypeRaw,

  // LogDesc
  logDescCountsRaw, deviceByLogDescRaw, actionByLogDescRaw, severityByLogDescRaw,

  // Level → Trend / Hourly / Subtype
  trendByLevel,
  levelCountsByHourRaw,
  subtypeByLevelRaw,

  // Subtype → Trend / Hourly
  trendBySubtype,
  subtypeByHourRaw,

  // Subtype → Level
  levelBySubtypeRaw,
  msgSeverityByLevelRaw,
  msgSeverityBySubtypeRaw,
  levelByMsgSeverityRaw,
  subtypeByMsgSeverityRaw,
  hourSeriesBySubtypeRaw,
};
