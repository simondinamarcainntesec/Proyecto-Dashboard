import { getEvents } from "/static/js/soar/data.js";
import { getState } from "/static/js/soar/state.js";
import { prettyActionLabel } from "/static/js/soar/utils.js";

const norm = (s) => String(s ?? "").trim().toLowerCase();
const safe = (s) => (String(s ?? "").trim() || "N/A");

function homog(v){ const t = String(v ?? "").trim(); return t ? t : "n/a"; }

// ignore = { severity: true, country: true, action: true } para “self-ignore”
function passesFilters(row, st, ignore = {}){
  const sev  = norm(homog(row?.severity));
  const ctry = norm(homog(row?.srccountry));
  const raw  = row?.security_action ?? row?.action;
  const act  = norm(homog(prettyActionLabel(raw)));

  if (!ignore.severity && st.severityFilter && sev  !== norm(st.severityFilter)) return false;
  if (!ignore.country  && st.countryFilter  && ctry !== norm(st.countryFilter))  return false;
  if (!ignore.action   && st.actionFilter   && act  !== norm(st.actionFilter))   return false;
  return true;
}

/* === Severity (doughnut) ===
   selfIgnore=true: ignora su propio filtro pero respeta el de país/acción */
export function selectSeverityCounts(selfIgnore = false){
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

/* === Security Action (bar/donut) === */
export function selectSecActionPayload(selfIgnore = false){
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
  const data   = labels.map(k => map[k]);
  const keys   = labels.slice();
  return { labels, data, keys };
}

/* === Countries Top N === */
export function selectCountriesPayload(topN = 10, selfIgnore = false){
  const st = getState();
  const events = getEvents();
  const map = {};
  for (const r of events){
    if (!passesFilters(r, st, { country: selfIgnore })) continue;
    const key = safe(homog(r?.srccountry));
    map[key] = (map[key] || 0) + 1;
  }
  const sorted = Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0, topN);
  const labels = sorted.map(([k]) => k);
  const data   = sorted.map(([,v]) => v);
  const keys   = labels.slice();
  return { labels, data, keys };
}
