import { getEvents } from "/static/js/soar/data.js";
import { getState } from "/static/js/soar/state.js";
import { prettyActionLabel } from "/static/js/soar/utils.js";

const norm = (s) => String(s ?? "").trim().toLowerCase();
const safe = (s) => (String(s ?? "").trim() || "N/A");
const homog = (v) => {
  const t = String(v ?? "").trim();
  return t ? t : "n/a";
};

// IP helpers
const isPrivateIP = (ip) => {
  const m = String(ip||"").match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!m) return false;
  const [a,b] = [parseInt(m[1],10), parseInt(m[2],10)];
  if (a===10) return true;
  if (a===172 && b>=16 && b<=31) return true;
  if (a===192 && b===168) return true;
  return false;
};

// Fuente heurística
function deriveSource(row){
  const aot = String(row?.aotag || "").trim();
  if (aot) return aot.toLowerCase();
  const dev = String(row?.device || "").trim();
  if (dev) return dev.toLowerCase();
  const app = String(row?.application || "").trim();
  if (app) return app.toLowerCase();
  const dn  = String(row?.displayname || "").trim();
  if (/\blog360\b/i.test(dn)) return "log360";
  if (/\bforti(analyzer|gate)\b/i.test(dn)) return "fortinet";
  return "otros";
}

function passesFilters(row, st, ignore = {}){
  const sev   = norm(homog(row?.severity));
  const ctry  = norm(homog(row?.srccountry));
  const rawA  = row?.security_action ?? row?.action;
  const act   = norm(homog(prettyActionLabel(rawA)));
  const dev   = norm(homog(row?.device));
  const svc   = norm(homog(row?.service));
  const proto = norm(homog(row?.proto));
  const src   = norm(deriveSource(row));
  const ip    = norm(String(row?.srcip || row?.dstip || ""));

  if (!ignore.severity && st.severityFilter && sev   !== norm(st.severityFilter)) return false;
  if (!ignore.country  && st.countryFilter  && ctry  !== norm(st.countryFilter))  return false;
  if (!ignore.action   && st.actionFilter   && act   !== norm(st.actionFilter))   return false;
  if (!ignore.device   && st.deviceFilter   && dev   !== norm(st.deviceFilter))   return false;
  if (!ignore.service  && st.serviceFilter  && svc   !== norm(st.serviceFilter))  return false;
  if (!ignore.proto    && st.protoFilter    && proto !== norm(st.protoFilter))    return false;
  if (!ignore.source   && st.sourceFilter   && src   !== norm(st.sourceFilter))   return false;
  if (!ignore.ip       && st.ipFilter       && ip    !== norm(st.ipFilter))       return false;
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

/* === KPI corregido (arregla la autorreferencia de `c`) === */
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

  // País top del último día válido (ignorar 'N/A')
  const validDated = all
    .map(r => ({ d: String(r?.date ?? "").trim(), c: String(r?.srccountry ?? "").trim() }))
    .filter(x => x.d && norm(x.d) !== "n/a");

  let topCountryToday = "N/A";
  if (validDated.length){
    const lastDay = validDated.map(x => x.d).sort().at(-1);
    const cmap = {};
    for (const r of validDated){
      if (r.d !== lastDay) continue;
      const c = r.c && norm(r.c) !== "n/a" ? r.c : ""; // ← aquí estaba el bug: antes decía norm(c)
      if (!c) continue;
      cmap[c] = (cmap[c] || 0) + 1;
    }
    if (Object.keys(cmap).length){
      topCountryToday = Object.entries(cmap).sort((a,b)=>b[1]-a[1])[0][0];
    } else {
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

/* === NUEVOS SELECTORES === */
export function selectSourcesPayload(topN=10, selfIgnore=false){
  const st = getState(); const events = getEvents(); const map = {};
  for (const r of events){
    if (!passesFilters(r, st, { source: selfIgnore })) continue;
    const key = safe(deriveSource(r));
    map[key]=(map[key]||0)+1;
  }
  const sorted = Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0, topN);
  return { labels: sorted.map(([k])=>k), data: sorted.map(([,v])=>v), keys: sorted.map(([k])=>k) };
}

export function selectTopIPsPayload(which="src", topN=10, selfIgnore=false){
  const st = getState(); const events = getEvents(); const map = {};
  const field = which === "dst" ? "dstip" : "srcip";
  const ignoreKey = "ip";
  for (const r of events){
    const ignores = { }; if (selfIgnore) ignores[ignoreKey] = true;
    if (!passesFilters(r, st, ignores)) continue;
    const ip = safe(r?.[field]);
    if (!ip || ip.toLowerCase()==="n/a") continue;
    map[ip]=(map[ip]||0)+1;
  }
  const sorted = Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0, topN);
  return { labels: sorted.map(([k])=>k), data: sorted.map(([,v])=>v) };
}

export function selectServiceProtoStackPayload(topServices=8){
  const st = getState(); const events = getEvents();
  const serviceCount = {};
  for (const r of events){ if (!passesFilters(r, st, {})) continue;
    const s = safe(homog(r?.service)); serviceCount[s]=(serviceCount[s]||0)+1; }
  const top = new Set(Object.entries(serviceCount).sort((a,b)=>b[1]-a[1]).slice(0, topServices).map(([k])=>k));
  const matrix = {}; const protos = new Set();
  for (const r of events){ if (!passesFilters(r, st, {})) continue;
    const s = safe(homog(r?.service)); if (!top.has(s)) continue;
    const p = safe(homog(r?.proto)); protos.add(p);
    matrix[s] = matrix[s] || {}; matrix[s][p] = (matrix[s][p]||0)+1;
  }
  const labels = Array.from(top);
  const protoKeys = Array.from(protos);
  const datasets = protoKeys.map(pk => ({
    label: pk, data: labels.map(s => matrix[s]?.[pk] || 0)
  }));
  return { labels, datasets };
}

export function selectInternalExternalPayload(){
  const st = getState(); const events = getEvents();
  let internas = 0, externas = 0;
  for (const r of events){
    if (!passesFilters(r, st, {})) continue;
    const ip = String(r?.srcip || "");
    const country = String(r?.srccountry || "");
    const internal = isPrivateIP(ip) || country.toLowerCase()==="reserved";
    if (internal) internas += 1; else externas += 1;
  }
  return { labels:["Internas","Externas"], data:[internas, externas] };
}
