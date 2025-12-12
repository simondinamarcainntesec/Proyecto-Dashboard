// dashboard.js (HISTÓRICO)
import { setupChartJSDefaults } from "./theme.js";
import { $ } from "./utils.js";
import { getState, onStateChange } from "./state.js";
import "./data.js";

import {
  getPeakHour,
  calcKpis,
  getActiveCountsForDonut,
  trendDataForCurrentFilter,
  actionDataForCurrentFilter,
  msgSeverityDataForCurrentFilter,
  levelDataForCurrentFilter,
  subtypeDataForCurrentFilter,
  logDescriptionDataForCurrentFilter,
} from "./selectors.js";

import { renderDonut } from "./charts/donut.js";
import { renderTrend } from "./charts/trend.js";
import { renderActionBar } from "./charts/actions.js";
import { renderMsgSeverityBar } from "./charts/msgSeverity.js";
import { renderHourly } from "./charts/hourly.js";
import { renderDeviceTable } from "./charts/devicesTable.js";
import { mountLevelBar } from "./charts/level.js";
import { renderSubtypeBar } from "./charts/subtype.js";
import { renderLogDescriptionBar } from "./charts/logDescription.js";

// ======================================================
// 1) Inicialización global
// ======================================================
setupChartJSDefaults(window.Chart);

// ======================================================
// 2) Helpers KPIs
// ======================================================
function formatHourRange(h) {
  const hour = Number(h);
  const hh = String(hour).padStart(2, "0"); // 00..23
  const ampm = hour < 12 ? "am" : "pm";
  return `${hh}:00–${hh}:59 ${ampm}`;
}

function renderKPIs() {
  const state = getState() || {};

  // Total / crítica / dispositivos usando la misma lógica de selectors.js
  const { total, high, devices } = calcKpis(state);

  const elTotal   = $("#kpi-total");
  const elHigh    = $("#kpi-high");
  const elDevices = $("#kpi-devices");

  if (elTotal)   elTotal.textContent   = total ?? 0;
  if (elHigh)    elHigh.textContent    = high ?? 0;
  if (elDevices) elDevices.textContent = devices ?? 0;

  // Hora con más alarmas (usa data.* directamente)
  const { hour } = getPeakHour();
  const elPeak = document.getElementById("kpi-peak-hour");
  if (elPeak) {
    elPeak.textContent = hour == null ? "—" : formatHourRange(hour);
  }
}

// ======================================================
// 3) Render general
// ======================================================
function updateAll() {
  const st = getState();

  // KPIs
  renderKPIs();

  // Trend por día (histórico)
  const trendConf = trendDataForCurrentFilter(st);
  renderTrend(trendConf);

  // Donut de severidad (siempre usando todos los segmentos)
  renderDonut(st, getActiveCountsForDonut(st));

  // Tabla dispositivos
  renderDeviceTable(st);

  // Barras
  renderActionBar(actionDataForCurrentFilter(st));
  renderMsgSeverityBar(
    msgSeverityDataForCurrentFilter(st),
    st.msgSeverityFilter
  );
  renderHourly(st);
  renderSubtypeBar(
    subtypeDataForCurrentFilter(st),
    st.subtypeFilter
  );
  renderLogDescriptionBar(
    logDescriptionDataForCurrentFilter(st),
    st.logDescriptionFilter
  );
}

// ======================================================
// 4) UX (filtros, tabla)
// ======================================================
function wireDateFilter() {
  const form = $("#date-filter");
  if (!form) return;
  const from = form.querySelector('input[name="from"]');
  const to   = form.querySelector('input[name="to"]');
  if (from && to) {
    from.addEventListener("change", () => { to.min = from.value || ""; });
    to.addEventListener("change", () => { from.max = to.value || ""; });
    to.min = from.value || "";
    from.max = to.value || "";
  }
}

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
        if (type === "number") {
          return asc ? Number(av) - Number(bv) : Number(bv) - Number(av);
        }
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
  wireDateFilter();
  wireTableSort();

  // Monta Level UNA sola vez (se subscribe internamente)
  unmountLevel = mountLevelBar("levelBar");

  // Render inicial
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
  updateAll();
});

// ======================================================
// 7) Botón refresh
// ======================================================
(function () {
  const r = document.getElementById("btn-refresh");
  if (!r) return;
  r.addEventListener("click", () => {
    const params = new URLSearchParams(window.location.search);
    params.set("_", Date.now().toString());
    window.location.search = params.toString();
  });
})();
