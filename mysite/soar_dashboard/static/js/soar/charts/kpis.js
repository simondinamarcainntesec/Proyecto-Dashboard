import { computeKPIs } from "/static/js/soar/selectors.js";

export function renderKPIs(){
  const k = computeKPIs();
  const set = (id,val)=>{ const el=document.getElementById(id); if(el) el.textContent = val; };
  set("kpi-total",        k.total ?? 0);
  set("kpi-pct-blocked", `${k.pctBlocked ?? 0}%`);
  set("kpi-top-device",   k.topDevice ?? "N/A");
  set("kpi-dom-sev",      (k.domSeverity ?? "n/a").toUpperCase());
  set("kpi-top-country",  k.topCountryToday ?? "N/A");
}
