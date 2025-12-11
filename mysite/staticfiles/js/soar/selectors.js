// static/js/soar/selectors.js
import { getEvents } from "/static/js/soar/data.js";
import { getState } from "/static/js/soar/state.js";
import { prettyActionLabel } from "/static/js/soar/utils.js";

const norm = (s) => String(s ?? "").trim().toLowerCase();
const safe = (s) => (String(s ?? "").trim() || "N/A");
const homog = (v) => {
  const t = String(v ?? "").trim();
  return t ? t : "n/a";
};

// === Helpers de fecha ===
function dateInRange(rowDate, from, to) {
  if (!from && !to) return true;
  const d = String(rowDate || "").trim();
  if (!d) return false;
  if (from && d < from) return false;
  if (to && d > to) return false;
  return true;
}

// Filtro general. `ignore` indica filtros a ignorar para “selfIgnore” en algunos charts.
function passesFilters(row, st, ignore = {}) {
  const sev   = norm(homog(row?.severity));
  const ctry  = norm(homog(row?.srccountry));
  const rawA  = row?.security_action ?? row?.action;
  const act   = norm(homog(prettyActionLabel(rawA)));
  const dev   = norm(homog(row?.device));
  const svc   = norm(homog(row?.service));
  const proto = norm(homog(row?.proto));
  const app   = norm(homog(row?.application));
  const sip   = norm(homog(row?.srcip));
  const dip   = norm(homog(row?.dstip));

  // Fechas y hora
  const rDate = String(row?.date || "").trim();
  const rTime = String(row?.time || "").trim();
  const rHH   = rTime.slice(0, 2);

  if (!ignore.date) {
    const from = st.dateFrom ? String(st.dateFrom).trim() : "";
    const to   = st.dateTo   ? String(st.dateTo).trim()   : "";
    if (!dateInRange(rDate, from, to)) return false;
  }

  if (!ignore.hour && st.hourFilter) {
    const hh = String(st.hourFilter).padStart(2, "0").slice(0, 2);
    if (rHH !== hh) return false;
  }

  if (!ignore.severity && st.severityFilter && sev   !== norm(st.severityFilter)) return false;
  if (!ignore.country  && st.countryFilter  && ctry  !== norm(st.countryFilter))  return false;
  if (!ignore.action   && st.actionFilter   && act   !== norm(st.actionFilter))   return false;
  if (!ignore.device   && st.deviceFilter   && dev   !== norm(st.deviceFilter))   return false;
  if (!ignore.service  && st.serviceFilter  && svc   !== norm(st.serviceFilter))  return false;
  if (!ignore.proto    && st.protoFilter    && proto !== norm(st.protoFilter))    return false;
  if (!ignore.app      && st.applicationFilter && app !== norm(st.applicationFilter)) return false;
  if (!ignore.srcip    && st.srcIPFilter    && sip   !== norm(st.srcIPFilter))    return false;
  if (!ignore.dstip    && st.dstIPFilter    && dip   !== norm(st.dstIPFilter))    return false;

  return true;
}

/* === payloads === */
export function selectSeverityCounts(selfIgnore = false) {
  const st = getState(); const events = getEvents(); const counts = {};
  for (const r of events) {
    if (!passesFilters(r, st, { severity: selfIgnore })) continue;
    const k = norm(homog(r?.severity));
    counts[k] = (counts[k] || 0) + 1;
  }
  return counts;
}

export function selectSecActionPayload(selfIgnore = false) {
  const st = getState(); const events = getEvents(); const map = {};
  for (const r of events) {
    if (!passesFilters(r, st, { action: selfIgnore })) continue;
    const raw = r?.security_action ?? r?.action;
    const key = safe(prettyActionLabel(raw));
    map[key] = (map[key] || 0) + 1;
  }
  const labels = Object.keys(map);
  return { labels, data: labels.map(k => map[k]), keys: labels.slice() };
}

export function selectCountriesPayload(topN = 10, selfIgnore = false) {
  const st = getState(); const events = getEvents(); const map = {};
  for (const r of events) {
    if (!passesFilters(r, st, { country: selfIgnore })) continue;
    const key = safe(homog(r?.srccountry));
    map[key] = (map[key] || 0) + 1;
  }
  const sorted = Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0, topN);
  const labels = sorted.map(([k])=>k);
  return { labels, data: sorted.map(([,v])=>v), keys: labels.slice() };
}

export function selectTopDevicesPayload(topN = 10, selfIgnore = false) {
  const st = getState(); const events = getEvents(); const map = {};
  for (const r of events) {
    if (!passesFilters(r, st, { device: selfIgnore })) continue;
    const key = safe(homog(r?.device));
    map[key]=(map[key]||0)+1;
  }
  const sorted = Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0, topN);
  return { labels: sorted.map(([k])=>k), data: sorted.map(([,v])=>v), keys: sorted.map(([k])=>k) };
}

export function selectTopServicesPayload(topN = 10, selfIgnore = false) {
  const st = getState(); const events = getEvents(); const map = {};
  for (const r of events) {
    if (!passesFilters(r, st, { service: selfIgnore })) continue;
    const key = safe(homog(r?.service));
    map[key]=(map[key]||0)+1;
  }
  const sorted = Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0, topN);
  return { labels: sorted.map(([k])=>k), data: sorted.map(([,v])=>v), keys: sorted.map(([k])=>k) };
}

export function selectTopProtoPayload(topN = 10, selfIgnore = false) {
  const st = getState(); const events = getEvents(); const map = {};
  for (const r of events) {
    if (!passesFilters(r, st, { proto: selfIgnore })) continue;
    const key = safe(homog(r?.proto));
    map[key]=(map[key]||0)+1;
  }
  const sorted = Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0, topN);
  return { labels: sorted.map(([k])=>k), data: sorted.map(([,v])=>v), keys: sorted.map(([k])=>k) };
}

/* === Applications (bar) — usa row.application === */
export function selectTopApplicationsPayload(topN = 10, selfIgnore = false) {
  const st = getState(); const events = getEvents(); const map = {};
  const ignore = selfIgnore ? { app: true } : {};
  for (const r of events) {
    if (!passesFilters(r, st, ignore)) continue;
    const key = safe(homog(r?.application));
    map[key]=(map[key]||0)+1;
  }
  const sorted = Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0, topN);
  return { labels: sorted.map(([k])=>k), data: sorted.map(([,v])=>v), keys: sorted.map(([k])=>k) };
}

/* === Tabla de dispositivos === */
export function deviceRowsForCurrentFilter(){
  const st = getState(); const events = getEvents(); const map = {};
  for (const r of events){
    if (!passesFilters(r, st, {})) continue;
    const k = safe(homog(r?.device));
    map[k]=(map[k]||0)+1;
  }
  return Object.entries(map).sort((a,b)=>b[1]-a[1]);
}

/* tendencias */
export function selectTrendByDatePayload(){
  const st = getState(); const events = getEvents(); const map = new Map();
  for (const r of events){ if (!passesFilters(r, st, {})) continue;
    const d = safe(homog(r?.date)); map.set(d, (map.get(d)||0)+1); }
  const labels = Array.from(map.keys()).sort();
  return { labels, data: labels.map(k => map.get(k)) };
}

export function selectTrendByHourPayload(selfIgnore = false){
  const st = getState(); const events = getEvents(); const buckets = new Array(24).fill(0);
  for (const r of events){
    const ignore = selfIgnore ? { hour: true } : {};
    if (!passesFilters(r, st, ignore)) continue;
    const hh = String(r?.time ?? "").slice(0,2); const i = parseInt(hh,10);
    if (!Number.isNaN(i) && i>=0 && i<=23) buckets[i] += 1;
  }
  const labels = [...Array(24)].map((_,i)=>String(i).padStart(2,"0")+":00");
  return { labels, data: buckets };
}

/* === KPI (sin cambios funcionales) === */
export function computeKPIs() {
  const st = getState();
  const all = getEvents().filter(r => passesFilters(r, st, {}));

  const total = all.length;

  // 1) % bloqueadas
  let blocked = 0;
  for (const r of all) {
    const a = norm(prettyActionLabel(r?.security_action ?? r?.action));
    if (["blocked","block","deny","denied","drop","dropped","timeout","reset"].includes(a)) {
      blocked += 1;
    }
  }
  const pctBlocked = total ? Math.round((blocked / total) * 100) : 0;

  // 2) Top dispositivo
  const dmap = {};
  for (const r of all) {
    const k = safe(homog(r?.device));
    dmap[k] = (dmap[k] || 0) + 1;
  }
  const topDevice = Object.entries(dmap).sort((a, b) => b[1] - a[1])[0]?.[0] || "N/A";

  // 3) Severidad dominante
  const smap = {};
  for (const r of all) {
    const k = norm(homog(r?.severity));
    smap[k] = (smap[k] || 0) + 1;
  }
  const domSeverity = Object.entries(smap).sort((a, b) => b[1] - a[1])[0]?.[0] || "n/a";

  // 4) País top incidentes (mismo criterio que el donut, pero filtrando Reserved/NA)
  const isValidCountry = (c) => {
    const n = norm(c);
    // vacío, "n/a" o "reserved" se ignoran SIEMPRE
    return !!n && n !== "n/a" && n !== "reserved";
  };

  const countryMap = {};
  for (const r of all) {
    const raw = String(r?.srccountry ?? "").trim();
    if (!isValidCountry(raw)) continue;
    countryMap[raw] = (countryMap[raw] || 0) + 1;
  }

  let topCountryToday = "N/A";
  if (Object.keys(countryMap).length) {
    // mismo criterio que el donut: top país del conjunto completo filtrado
    topCountryToday = Object.entries(countryMap).sort((a, b) => b[1] - a[1])[0][0];
  }

  return { total, pctBlocked, topDevice, domSeverity, topCountryToday };
}



// =======================
// Top IPs (src / dst)
// =======================
export function selectTopIPsPayload(kind = "src", topN = 10, selfIgnore = false) {
  const st = getState();
  const events = getEvents();
  const map = {};

  const ignore = {
    ...(selfIgnore ? (kind === "src" ? { srcip: true } : { dstip: true }) : {}),
  };

  for (const r of events) {
    if (!passesFilters(r, st, ignore)) continue;
    const key = safe(homog(kind === "src" ? r?.srcip : r?.dstip));
    if (!key || norm(key) === "n/a") continue;
    map[key] = (map[key] || 0) + 1;
  }

  const sorted = Object.entries(map).sort((a, b) => b[1] - a[1]).slice(0, topN);
  return {
    labels: sorted.map(([k]) => k),
    data:   sorted.map(([, v]) => v),
    keys:   sorted.map(([k]) => k),
  };
}

// Aliases convenientes
export const selectTopSrcIPsPayload = (topN = 10, selfIgnore = false) =>
  selectTopIPsPayload("src", topN, selfIgnore);

export const selectTopDstIPsPayload = (topN = 10, selfIgnore = false) =>
  selectTopIPsPayload("dst", topN, selfIgnore);

/* === NUEVO: alarm_ids visibles con los filtros actuales === */
export function alarmIdsForCurrentFilter() {
  const st = getState();
  const events = getEvents();
  const ids = new Set();
  for (const r of events) {
    if (!passesFilters(r, st, {})) continue;
    const id = String(r?.alarm_id || "").trim();
    if (id) ids.add(id);
  }
  return Array.from(ids);
}
