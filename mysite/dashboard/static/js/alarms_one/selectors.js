// selectors.js
import {
  normalizeCountsLabels,
  findKeyCI,
  norm,
  normalizeMapValues,
  readJSON,
  prettyActionLabel,
} from "./utils.js";
import data from "./data.js";
import { colorFor, colorForMsgSeverity } from "./theme.js";

export function getActiveCounts(state) {
  const byMsg = state.msgSeverityFilter && severityCountsForMsgSeverity(state.msgSeverityFilter);
  const byDev = state.deviceFilter && severityCountsForDevice(state.deviceFilter);
  const byAct = state.actionFilter && severityCountsForAction(state.actionFilter);
  const byHour = state.hourFilter && severityCountsForHour(state.hourFilter);

  let base = byMsg || byDev || byAct || byHour || data.severityCounts;
  base = normalizeCountsLabels(base);
  base = applySeveritySlice(base, state.severityFilter);

  if (!base || Object.keys(base).length === 0) return { "N/A": 0 };
  return base;
}

export function calcKpis(state) {
  const counts = getActiveCounts(state);
  let total = Object.values(counts).reduce((a, b) => a + (Number(b) || 0), 0);

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

export function trendDataForCurrentFilter(state) {
  const { canonicalDeviceKey } = data;

  if (state.deviceFilter && data.trendByDevice[canonicalDeviceKey(state.deviceFilter)]) {
    const dk = canonicalDeviceKey(state.deviceFilter);
    return {
      labels: data.trendLabels,
      datasets: [
        {
          label: dk,
          data: data.trendByDevice[dk],
          borderColor: "#60A5FA",
          backgroundColor: "rgba(96,165,250,0.18)",
          borderWidth: 3,
          pointRadius: 3,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.35,
        },
      ],
    };
  }
  if (state.actionFilter && data.trendByAction[state.actionFilter]) {
    return {
      labels: data.trendLabels,
      datasets: [
        {
          label: `Acción: ${prettyActionLabel(state.actionFilter)}`,
          data: data.trendByAction[state.actionFilter],
          borderColor: "#8B5CF6",
          backgroundColor: "rgba(139,92,246,0.20)",
          borderWidth: 3,
          pointRadius: 3,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.35,
        },
      ],
    };
  }
  if (state.msgSeverityFilter && data.trendByMsgSeverityRaw[state.msgSeverityFilter]) {
    return {
      labels: data.trendLabels,
      datasets: [
        {
          label: `Msg severity: ${state.msgSeverityFilter}`,
          data: data.trendByMsgSeverityRaw[state.msgSeverityFilter],
          borderColor: "#F43F5E",
          backgroundColor: "rgba(244,63,94,0.20)",
          borderWidth: 3,
          pointRadius: 3,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.35,
        },
      ],
    };
  }
  if (state.hourFilter && data.trendByHourRaw[state.hourFilter]) {
    return {
      labels: data.trendLabelsHour,
      datasets: [
        {
          label: `Hora ${state.hourFilter}:00`,
          data: data.trendByHourRaw[state.hourFilter],
          borderColor: "#22C55E",
          backgroundColor: "rgba(34,197,94,0.20)",
          borderWidth: 3,
          pointRadius: 3,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.35,
        },
      ],
    };
  }
  const datasets = Object.keys(data.severityTrendsMap).map((sev) => {
    const sevKey = String(sev).trim();
    const hidden =
      state.severityFilter &&
      sevKey.toLowerCase() !== String(state.severityFilter).trim().toLowerCase();
    const base = colorFor(sevKey);
    return {
      label: sevKey,
      data:
        (data.severityTrendsMap[sev] && data.severityTrendsMap[sev].data) ||
        new Array(data.trendLabels.length).fill(0),
      borderColor: base,
      backgroundColor: base + "33",
      pointBackgroundColor: base,
      pointBorderColor: base,
      borderWidth: 3,
      pointRadius: hidden ? 0 : 3,
      pointHoverRadius: hidden ? 0 : 5,
      fill: true,
      tension: 0.35,
      hidden,
    };
  });
  return { labels: data.trendLabels, datasets };
}

// acción → dataset barra
export function actionDataForCurrentFilter(state) {
  const { canonicalDeviceKey } = data;

  if (state.deviceFilter && data.actionByDev[canonicalDeviceKey(state.deviceFilter)]) {
    const m = data.actionByDev[canonicalDeviceKey(state.deviceFilter)];
    const keys = Object.keys(m);
    return { labels: keys.map(prettyActionLabel), data: keys.map((k) => Number(m[k] || 0)), keys };
  }
  if (state.severityFilter) {
    const realSev = findKeyCI(data.sevToAct, state.severityFilter);
    if (realSev && data.sevToAct[realSev]) {
      const m = data.sevToAct[realSev];
      const keys = Object.keys(m);
      return { labels: keys.map(prettyActionLabel), data: keys.map((k) => Number(m[k] || 0)), keys };
    }
  }
  if (state.msgSeverityFilter && data.actionByMsgSeverityRaw[state.msgSeverityFilter]) {
    const m = data.actionByMsgSeverityRaw[state.msgSeverityFilter];
    const keys = Object.keys(m);
    return { labels: keys.map(prettyActionLabel), data: keys.map((k) => Number(m[k] || 0)), keys };
  }
  if (state.hourFilter && data.actByHourNorm[state.hourFilter]) {
    const m = data.actByHourNorm[state.hourFilter];
    const keys = Object.keys(m);
    return { labels: keys.map(prettyActionLabel), data: keys.map((k) => Number(m[k] || 0)), keys };
  }
  const m = normalizeMapValues(data.actionCountsRaw);
  const keys = Object.keys(m);
  return { labels: keys.map(prettyActionLabel), data: keys.map((k) => Number(m[k] || 0)), keys };
}

// msg_severity → dataset barra
export function msgSeverityDataForCurrentFilter(state) {
  const { canonicalDeviceKey } = data;

  if (state.deviceFilter && data.deviceByMsgSeverityRaw) {
    const devKey = canonicalDeviceKey(state.deviceFilter);
    const map = {};
    Object.entries(data.deviceByMsgSeverityRaw).forEach(([msg, perDev]) => {
      map[msg] = Number((perDev || {})[devKey] || 0);
    });
    const keys = Object.keys(map);
    return { labels: keys, data: keys.map((k) => map[k]), keys, colors: keys.map(colorForMsgSeverity) };
  }
  if (state.severityFilter && data.severityByMsgSeverityRaw) {
    const map = {};
    Object.entries(data.severityByMsgSeverityRaw).forEach(([msg, perSev]) => {
      const k = findKeyCI(perSev, state.severityFilter) || state.severityFilter;
      map[msg] = Number((perSev || {})[k] || 0);
    });
    const keys = Object.keys(map);
    return { labels: keys, data: keys.map((k) => map[k]), keys, colors: keys.map(colorForMsgSeverity) };
  }
  if (state.actionFilter && data.actionByMsgSeverityRaw) {
    const map = {};
    Object.entries(data.actionByMsgSeverityRaw).forEach(([msg, perAct]) => {
      const per = perAct || {};
      const real = findKeyCI(per, state.actionFilter) ?? state.actionFilter;
      map[msg] = Number(per[real] || 0);
    });
    const keys = Object.keys(map);
    return { labels: keys, data: keys.map((k) => map[k]), keys, colors: keys.map(colorForMsgSeverity) };
  }
  if (state.hourFilter && data.msgSeverityByHourRaw && data.msgSeverityByHourRaw[state.hourFilter]) {
    const m = data.msgSeverityByHourRaw[state.hourFilter] || {};
    const keys = Object.keys(m);
    return { labels: keys, data: keys.map((k) => Number(m[k] || 0)), keys, colors: keys.map(colorForMsgSeverity) };
  }
  const m = normalizeMapValues(data.msgSeverityCountsRaw);
  const keys = Object.keys(m);
  return { labels: keys, data: keys.map((k) => Number(m[k] || 0)), keys, colors: keys.map(colorForMsgSeverity) };
}

// tabla de dispositivos
export function deviceRowsForCurrentFilter(state) {
  if (state.hourFilter && data.devByHourRaw[state.hourFilter]) {
    const m = data.devByHourRaw[state.hourFilter];
    return top10(m);
  }
  if (state.msgSeverityFilter && data.deviceByMsgSeverityRaw[state.msgSeverityFilter]) {
    const m = data.deviceByMsgSeverityRaw[state.msgSeverityFilter] || {};
    return top10(m);
  }
  if (state.actionFilter && data.deviceByAction[state.actionFilter]) {
    const m = data.deviceByAction[state.actionFilter] || {};
    return top10(m);
  }
  const bySev = readJSON("device-counts-by-severity") || {};
  if (state.severityFilter && bySev[state.severityFilter]) {
    return top10(bySev[state.severityFilter]);
  }
  return top10(data.deviceCountsAll);
}

// ===== privados =====
function top10(m) {
  return Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, 10);
}

function applySeveritySlice(counts, severityFilter) {
  if (!severityFilter) return counts;
  const realKey = findKeyCI(counts, severityFilter) || severityFilter;
  const v = Number(counts[realKey] || 0);
  return { [realKey]: v };
}

function severityCountsForDevice(device) {
  const dev = data.canonicalDeviceKey(device);
  const out = {};
  const bySevFull = data.deviceBySevFullRaw || {};
  Object.keys(bySevFull).forEach((sev) => {
    const m = bySevFull[sev] || {};
    out[String(sev).trim()] = Number(m[dev] || 0);
  });
  return out;
}

function severityCountsForAction(actionKey) {
  const m = data.actToSev[actionKey] || {};
  const out = {};
  Object.keys(m).forEach((sev) => (out[sev] = Number(m[sev] || 0)));
  return out;
}

function severityCountsForHour(hour) {
  const m = data.sevByHourRaw && data.sevByHourRaw[hour] ? data.sevByHourRaw[hour] : {};
  const out = {};
  Object.keys(m).forEach((sev) => (out[String(sev).trim()] = Number(m[sev] || 0)));
  return out;
}

function severityCountsForMsgSeverity(msg) {
  const m =
    data.severityByMsgSeverityRaw && data.severityByMsgSeverityRaw[msg]
      ? data.severityByMsgSeverityRaw[msg]
      : {};
  const out = {};
  Object.keys(m).forEach((sev) => (out[String(sev).trim()] = Number(m[sev] || 0)));
  return out;
}
