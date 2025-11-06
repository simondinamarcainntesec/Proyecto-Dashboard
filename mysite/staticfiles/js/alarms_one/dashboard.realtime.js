// dashboard.realtime.js (Tiempo Real) — sin trend
import { setupChartJSDefaults } from "./theme.js";
import { $ } from "./utils.js";
import { getState, onStateChange } from "./state.js";
import "./data.js";

import {
  getActiveCountsForDonut,
  // calcKpis, // <- no lo usamos para evitar que pise los valores
  actionDataForCurrentFilter,
  msgSeverityDataForCurrentFilter,
  levelDataForCurrentFilter,
  subtypeDataForCurrentFilter,
  logDescriptionDataForCurrentFilter,
  getPeakHour,
} from "./selectors.js";

import { renderDonut } from "./charts/donut.js";
import { renderActionBar } from "./charts/actions.js";
import { renderMsgSeverityBar } from "./charts/msgSeverity.js";
import { renderHourly } from "./charts/hourly.js";
import { renderDeviceTable } from "./charts/devicesTable.js";
import { mountLevelBar } from "./charts/level.js";
import { renderSubtypeBar } from "./charts/subtype.js";
import { renderLogDescriptionBar } from "./charts/logDescription.js";

function isEmptyState() { return !!document.querySelector(".empty-state"); }

// ======================================================
// 1) Inicialización global
// ======================================================
console.log("[realtime] Iniciando dashboard AlarmsOne (tiempo real)...");
setupChartJSDefaults(window.Chart);
console.log("[realtime] Chart.js detectado:", !!window.Chart);

// ======================================================
// 2) KPIs
// ======================================================
function formatHourRange(h) {
  const hour = Number(h);
  const hh = String(hour).padStart(2, "0");
  const ampm = hour < 12 ? "am" : "pm";
  return `${hh}:00–${hh}:59 ${ampm}`;
}

// --- Helpers para obtener data venga de donde venga ---
function readJSON(id) {
  try {
    const el = document.getElementById(id);
    if (!el) return null;
    return JSON.parse(el.textContent);
  } catch { return null; }
}

function firstNonEmpty(...objs) {
  for (const o of objs) {
    if (o && typeof o === "object" && Object.keys(o).length) return o;
  }
  return {};
}

function getDataCtx() {
  const st = getState() || {};
  const ctx = st.ctx || st.data || st; // a veces viene anidado

  const sev =
    ctx.severity_counts ||
    ctx.severityCountsRaw ||
    readJSON("severity-counts") ||
    {};

  const msg =
    ctx.msg_severity_counts ||
    ctx.msgSeverityCountsRaw ||
    readJSON("msg-severity-counts") ||
    {};

  const devCounts =
    ctx.device_counts ||
    ctx.deviceCountsAll ||
    readJSON("device-counts") ||
    {};

  return { sev, msg, devCounts };
}

function sumVals(obj) {
  return Object.values(obj || {}).reduce((a, n) => a + Number(n || 0), 0);
}

function renderKPIs() {
  const { sev, msg, devCounts } = getDataCtx();

  const total   = sumVals(sev);
  const high    = Number(msg.critical || 0); // usar CRITICAL de msg_severity
  // Si quieres (high + critical) desde msg_severity, usa:
  // const high = Number(msg.high || 0) + Number(msg.critical || 0);
  const devices = Object.keys(devCounts).length;

  const elTotal   = $("#kpi-total");
  const elHigh    = $("#kpi-high");
  const elDevices = $("#kpi-devices");
  if (elTotal)   elTotal.textContent = total;
  if (elHigh)    elHigh.textContent = high;
  if (elDevices) elDevices.textContent = devices;

  const { hour } = getPeakHour();
  const elPeak = document.getElementById("kpi-peak-hour");
  if (elPeak) elPeak.textContent = (hour == null) ? "—" : formatHourRange(hour);
}

// ======================================================
// 3) Render general
// ======================================================
function updateAll() {
  const st = getState();
  console.log("[realtime] Estado actual:", st);

  // KPIs
  renderKPIs();

  // Donut de severidad
  renderDonut(st, getActiveCountsForDonut(st));

  // Tabla dispositivos
  renderDeviceTable(st);

  // Barras
  renderActionBar(actionDataForCurrentFilter(st));
  renderMsgSeverityBar(msgSeverityDataForCurrentFilter(st), st.msgSeverityFilter);
  renderHourly(st);
  renderSubtypeBar(subtypeDataForCurrentFilter(st), st.subtypeFilter);
  renderLogDescriptionBar(logDescriptionDataForCurrentFilter(st), st.logDescriptionFilter);

  console.log("[realtime] Gráficos actualizados correctamente ✅");
}

// ======================================================
// 4) Utilidades UI (tabla)
// ======================================================
function wireTableSort() {
  const table = document.getElementById("device-table");
  if (!table) return;
  const tbody = table.querySelector("tbody");
  const ths = table.querySelectorAll("thead th");
  ths.forEach((th, idx) => {
    th.addEventListener("click", () => {
      const type = th.getAttribute("data-sort") || "text";
      const rows = Array.from(tbody.querySelectorAll("tr"));
      const asc = !th.classList.contains("sort-asc");
      ths.forEach((t) => t.classList.remove("sort-asc", "sort-desc"));
      th.classList.add(asc ? "sort-asc" : "sort-desc");
      rows.sort((a, b) => {
        const av = a.children[idx].innerText.trim();
        const bv = b.children[idx].innerText.trim();
        if (type === "number") return asc ? Number(av) - Number(bv) : Number(bv) - Number(av);
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
      tbody.innerHTML = "";
      rows.forEach((r) => tbody.appendChild(r));
    });
  });
}

// ======================================================
// 5) Boot
// ======================================================
let unmountLevel = null;

function boot() {
  if (isEmptyState()) {
    const btn = document.getElementById("btn-empty-ok");
    if (btn) btn.addEventListener("click", () => {
      window.location.href = document.getElementById("link-historico")?.getAttribute("href") || "/dashboard/";
    });
    console.log("[realtime] Empty-state: sin gráficos que montar.");
    return;
  }

  console.log("[realtime] DOM listo → inicializando...");
  wireTableSort();

  const levelEl = document.getElementById("levelBar");
  if (levelEl) {
    unmountLevel = mountLevelBar("levelBar");
  }

  updateAll();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}

// ======================================================
// 6) Redibujo ante cambios de filtros
// ======================================================
onStateChange(() => {
  if (isEmptyState()) return;
  console.log("[realtime] Cambio detectado en filtros → refrescando...");
  updateAll();
});

// ======================================================
// 7) Botón refresh (topbar)
// ======================================================
(function () {
  const r = document.getElementById('btn-refresh');
  if (!r) return;
  r.addEventListener('click', () => {
    const params = new URLSearchParams(window.location.search);
    params.set('_', Date.now().toString());
    window.location.search = params.toString();
  });
})();

// ======================================================
// 8) EXPOSE & MIRROR STATE (para los modales)
// ======================================================
(function exposeRealtimeState() {
  window.getState = () => { try { return getState(); } catch { return {}; } };
  function mirrorToBody(st) {
    const b = document.body; if (!b) return;
    b.dataset.severityFilter        = st.severityFilter || "";
    b.dataset.deviceFilter          = st.deviceFilter || "";
    b.dataset.actionFilter          = st.actionFilter || "";
    b.dataset.hourFilter            = st.hourFilter || "";
    b.dataset.msgSeverityFilter     = st.msgSeverityFilter || "";
    b.dataset.levelFilter           = st.levelFilter || "";
    b.dataset.subtypeFilter         = st.subtypeFilter || "";
    b.dataset.logDescriptionFilter  = st.logDescriptionFilter || "";
  }
  try { mirrorToBody(getState()); } catch {}
  onStateChange((st) => { window.__APP_STATE = st; mirrorToBody(st); });
})();
