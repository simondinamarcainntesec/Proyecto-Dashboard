// helpers/alarms-helper.js
import { getState } from "/static/js/soar/state.js";
import { getEvents } from "/static/js/soar/data.js";

const norm = (s) => String(s ?? "").trim().toLowerCase();
const safe = (s) => String(s ?? "").trim();
const homog = (v) => {
  const t = String(v ?? "").trim();
  return t ? t : "n/a";
};

// Aliases mínimos para acción (coincide con otros charts)
const ACTION_ALIASES = {
  "0":"open","1":"blocked","false":"open","true":"blocked",
  "allow":"open","allowed":"open","deny":"blocked","denied":"blocked",
  "block":"blocked","blocked":"blocked","resolved":"resolved","closed":"closed","2":"resolved",
  "drop":"blocked","timeout":"blocked","reset":"blocked"
};
function prettyActionKey(value) {
  const k = norm(value);
  if (ACTION_ALIASES[k]) return ACTION_ALIASES[k];
  if (!k) return "n/a";
  return k;
}

/**
 * rowPassesFilters(r, st)
 * Aplica TODOS los filtros del state.
 */
export function rowPassesFilters(r, st) {
  const sev   = norm(homog(r?.severity));
  const ctry  = norm(homog(r?.srccountry));
  const rawA  = r?.security_action ?? r?.action;
  const act   = prettyActionKey(rawA);
  const dev   = norm(homog(r?.device));
  const svc   = norm(homog(r?.service));
  const proto = norm(homog(r?.proto));
  const app   = norm(homog(r?.application));
  const sip   = norm(homog(r?.srcip));
  const dip   = norm(homog(r?.dstip));

  // fecha/hora
  const rDate = safe(r?.date);
  const rTime = safe(r?.time);
  const rHH   = rTime ? rTime.slice(0, 2) : "";

  // rango fecha
  const from = st.dateFrom ? safe(st.dateFrom) : "";
  const to   = st.dateTo   ? safe(st.dateTo)   : "";
  if (from && (!rDate || rDate < from)) return false;
  if (to   && (!rDate || rDate > to  )) return false;

  // hora exacta
  if (String(st.hourFilter ?? "") !== "") {
    const hh = String(st.hourFilter).padStart(2,"0").slice(0,2);
    if (rHH !== hh) return false;
  }

  if (st.severityFilter    && sev   !== norm(st.severityFilter))    return false;
  if (st.countryFilter     && ctry  !== norm(st.countryFilter))     return false;
  if (st.actionFilter      && act   !== norm(st.actionFilter))      return false;
  if (st.deviceFilter      && dev   !== norm(st.deviceFilter))      return false;
  if (st.serviceFilter     && svc   !== norm(st.serviceFilter))     return false;
  if (st.protoFilter       && proto !== norm(st.protoFilter))       return false;
  if (st.applicationFilter && app   !== norm(st.applicationFilter)) return false;
  if (st.srcIPFilter       && sip   !== norm(st.srcIPFilter))       return false;
  if (st.dstIPFilter       && dip   !== norm(st.dstIPFilter))       return false;

  return true;
}

/**
 * collectAlarmIdsForCurrentFilter(extraPredicate?)
 * - Respeta todos los filtros de state.
 * - extraPredicate(r) opcional para forzar una restricción del gráfico (ej. servicio clickeado).
 */
export function collectAlarmIdsForCurrentFilter(extraPredicate) {
  const st = getState();
  const events = getEvents() || [];

  const ids = new Set();
  for (const r of events) {
    if (!rowPassesFilters(r, st)) continue;
    if (typeof extraPredicate === "function" && !extraPredicate(r)) continue;

    const id = safe(r?.alarm_id || r?.id_alarm || r?.id || r?.alarma_id);
    if (id) ids.add(id);
  }
  return Array.from(ids);
}

/**
 * ensureHeaderButton(containerEl, id, onClick)
 * Coloca un botón en la esquina superior derecha del card.
 */
export function ensureHeaderButton(containerEl, btnId, onClick) {
  if (!containerEl) return null;
  const card = containerEl.closest(".card");
  if (!card) return null;

  // Evitar duplicados
  if (card.querySelector(`#${btnId}`)) return card.querySelector(`#${btnId}`);

  const wrap = document.createElement("div");
  wrap.style.position = "absolute";
  wrap.style.top = "8px";
  wrap.style.right = "12px";
  wrap.style.zIndex = "2";

  const btn = document.createElement("button");
  btn.id = btnId;
  btn.type = "button";
  btn.className = "btn ghost";
  btn.style.display = "inline-flex";
  btn.style.alignItems = "center";
  btn.style.gap = "6px";
  btn.style.fontWeight = "700";
  btn.style.padding = "6px 10px";
  btn.innerHTML = `<span aria-hidden="true">📁</span> Ver Alarmas `;
  btn.addEventListener("click", onClick);

  wrap.appendChild(btn);
  // Asegurar posicionamiento relativo
  card.style.position = card.style.position || "relative";
  card.appendChild(wrap);
  return btn;
}

/**
 * showAlarms(ids)
 * Abre el modal reutilizando el helper global, esperando si no está listo.
 */
export function showAlarms(ids) {
  if (!ids?.length) {
    alert("No hay alarmas para mostrar con el filtro actual.");
    return;
  }
  if (!window.SOAR_Incidents || typeof window.SOAR_Incidents.showForAlarmIds !== "function") {
    window.addEventListener("soar-incidents-ready", () => window.SOAR_Incidents.showForAlarmIds(ids), { once:true });
    return;
  }
  window.SOAR_Incidents.showForAlarmIds(ids);
}
