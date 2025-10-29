import { getEvents } from "/static/js/soar/data.js";
import { getState } from "/static/js/soar/state.js";
import { prettyActionLabel } from "/static/js/soar/utils.js";

const norm = (s) => String(s ?? "").trim().toLowerCase();
const safe = (s) => (String(s ?? "").trim() || "N/A");
const homog = (v) => {
  const t = String(v ?? "").trim();
  return t ? t : "n/a";
};

function passesFilters(row, st, ignore = {}){
  const sev   = norm(homog(row?.severity));
  const ctry  = norm(homog(row?.srccountry));
  const rawA  = row?.security_action ?? row?.action;
  const act   = norm(homog(prettyActionLabel(rawA)));
  const dev   = norm(homog(row?.device));
  const svc   = norm(homog(row?.service));
  const proto = norm(homog(row?.proto));

  if (!ignore.severity && st.severityFilter && sev   !== norm(st.severityFilter)) return false;
  if (!ignore.country  && st.countryFilter  && ctry  !== norm(st.countryFilter))  return false;
  if (!ignore.action   && st.actionFilter   && act   !== norm(st.actionFilter))   return false;
  if (!ignore.device   && st.deviceFilter   && dev   !== norm(st.deviceFilter))   return false;
  if (!ignore.service  && st.serviceFilter  && svc   !== norm(st.serviceFilter))  return false;
  if (!ignore.proto    && st.protoFilter    && proto !== norm(st.protoFilter))    return false;
  return true;
}

/* === existentes === */
export function selectSeverityCounts(selfIgnore=false){
  const st = getState();
  const events = getEvents();
  const counts = {};
  for (const r of events){
    if (!passesFilters(r, st, { severity: selfIgnore })) continue;
    const k = norm(homog(r?.severity));
    counts[k] = (counts[k] || 0) + 1;
  }
  return counts;
}

export function selectSecActionPayload(selfIgnore=false){
  const st = getState();
  const events = getEvents();
  const map = {};
  for (const r of events){
    if (!passesFilters(r, st, { action: selfIgnore })) continue;
    const raw = r?.security_action ?? r?.action;
    const key = safe(prettyActionLabel(raw));
    map[key] = (map[key] || 0) + 1;
  }
  const labels = Object.keys(map);
  return { labels, data: labels.map(k => map[k]), keys: labels.slice() };
}

export function selectCountriesPayload(topN=10, selfIgnore=false){
  const st = getState();
  const events = getEvents();
  const map = {};
  for (const r of events){
    if (!passesFilters(r, st, { country: selfIgnore })) continue;
    const key = safe(homog(r?.srccountry));
    map[key] = (map[key] || 0) + 1;
  }
  const sorted = Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0, topN);
  const labels = sorted.map(([k])=>k);
  return { labels, data: sorted.map(([,v])=>v), keys: labels.slice() };
}

/* === NUEVOS también usados por tabla === */
export function selectTopDevicesPayload(topN=10, selfIgnore=false){
  const st = getState(); const events = getEvents(); const map = {};
  for (const r of events){
    if (!passesFilters(r, st, { device: selfIgnore })) continue;
    const key = safe(homog(r?.device));
    map[key]=(map[key]||0)+1;
  }
  const sorted = Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0, topN);
  return { labels: sorted.map(([k])=>k), data: sorted.map(([,v])=>v), keys: sorted.map(([k])=>k) };
}

export function selectTopServicesPayload(topN=10, selfIgnore=false){
  const st = getState(); const events = getEvents(); const map = {};
  for (const r of events){
    if (!passesFilters(r, st, { service: selfIgnore })) continue;
    const key = safe(homog(r?.service));
    map[key]=(map[key]||0)+1;
  }
  const sorted = Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0, topN);
  return { labels: sorted.map(([k])=>k), data: sorted.map(([,v])=>v), keys: sorted.map(([k])=>k) };
}

export function selectTopProtoPayload(topN=10, selfIgnore=false){
  const st = getState(); const events = getEvents(); const map = {};
  for (const r of events){
    if (!passesFilters(r, st, { proto: selfIgnore })) continue;
    const key = safe(homog(r?.proto));
    map[key]=(map[key]||0)+1;
  }
  const sorted = Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0, topN);
  return { labels: sorted.map(([k])=>k), data: sorted.map(([,v])=>v), keys: sorted.map(([k])=>k) };
}

/* === Tabla de dispositivos (filtrable) === */
export function deviceRowsForCurrentFilter(){
  const st = getState(); const events = getEvents(); const map = {};
  for (const r of events){
    if (!passesFilters(r, st, {})) continue;
    const k = safe(homog(r?.device));
    map[k]=(map[k]||0)+1;
  }
  return Object.entries(map).sort((a,b)=>b[1]-a[1]);
}

/* tendencias & KPIs */
export function selectTrendByDatePayload(){
  const st = getState(); const events = getEvents(); const map = new Map();
  for (const r of events){ if (!passesFilters(r, st, {})) continue;
    const d = safe(homog(r?.date)); map.set(d, (map.get(d)||0)+1); }
  const labels = Array.from(map.keys()).sort();
  return { labels, data: labels.map(k => map.get(k)) };
}

export function selectTrendByHourPayload(){
  const st = getState(); const events = getEvents(); const buckets = new Array(24).fill(0);
  for (const r of events){ if (!passesFilters(r, st, {})) continue;
    const hh = String(r?.time ?? "").slice(0,2); const i = parseInt(hh,10);
    if (!Number.isNaN(i) && i>=0 && i<=23) buckets[i] += 1;
  }
  const labels = [...Array(24)].map((_,i)=>String(i).padStart(2,"0")+":00");
  return { labels, data: buckets };
}

/* === KPI corregido: ignora fecha 'N/A' y elige último día válido === */
export function computeKPIs(){
  const st = getState();
  const all = getEvents().filter(r => passesFilters(r, st, {}));

  const total = all.length;

  // % bloqueadas
  let blocked = 0;
  for (const r of all){
    const a = norm(prettyActionLabel(r?.security_action ?? r?.action));
    if (["blocked","block","deny","denied","drop","dropped","timeout","reset"].includes(a)) blocked += 1;
  }
  const pctBlocked = total ? Math.round((blocked/total)*100) : 0;

  // top device
  const dmap = {}; for (const r of all){ const k = safe(homog(r?.device)); dmap[k]=(dmap[k]||0)+1; }
  const topDevice = Object.entries(dmap).sort((a,b)=>b[1]-a[1])[0]?.[0] || "N/A";

  // severidad dominante
  const smap = {}; for (const r of all){ const k = norm(homog(r?.severity)); smap[k]=(smap[k]||0)+1; }
  const domSeverity = Object.entries(smap).sort((a,b)=>b[1]-a[1])[0]?.[0] || "n/a";

  // País top del último día válido (ignorar 'N/A' en fecha y país)
  const validDated = all
    .map(r => ({ d: String(r?.date ?? "").trim(), c: String(r?.srccountry ?? "").trim() }))
    .filter(x => x.d && norm(x.d) !== "n/a"); // fecha válida

  let topCountryToday = "N/A";
  if (validDated.length){
    const lastDay = validDated.map(x => x.d).sort().at(-1); // YYYY-MM-DD sortable
    const cmap = {};
    for (const r of validDated){
      if (r.d !== lastDay) continue;
      const c = r.c && norm(r.c) !== "n/a" ? r.c : ""; // descarta país N/A
      if (!c) continue;
      cmap[c] = (cmap[c] || 0) + 1;
    }
    if (Object.keys(cmap).length){
      topCountryToday = Object.entries(cmap).sort((a,b)=>b[1]-a[1])[0][0];
    } else {
      // si el último día no tiene países válidos, cae al más frecuente global con fecha válida
      const gmap = {};
      for (const r of validDated){
        const c = r.c && norm(r.c) !== "n/a" ? r.c : "";
        if (!c) continue;
        gmap[c] = (gmap[c] || 0) + 1;
      }
      topCountryToday = Object.entries(gmap).sort((a,b)=>b[1]-a[1])[0]?.[0] || "N/A";
    }
  }

  return { total, pctBlocked, topDevice, domSeverity, topCountryToday };
}
