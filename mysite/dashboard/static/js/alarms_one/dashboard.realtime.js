// dashboard.realtime.js (TIEMPO REAL) — sin trend
import { setupChartJSDefaults } from "./theme.js";
import { $ } from "./utils.js";
import { getState, onStateChange } from "./state.js";
import "./data.js";

import {
  getActiveCountsForDonut,
  calcKpis,
  actionDataForCurrentFilter,
  msgSeverityDataForCurrentFilter,
  levelDataForCurrentFilter,          // lo mantenemos por coherencia de tipos/exports
  subtypeDataForCurrentFilter,
  logDescriptionDataForCurrentFilter,
} from "./selectors.js";

import { renderDonut } from "./charts/donut.js";
// ❌ NO importamos trend.js en realtime
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
console.log("[realtime] Iniciando dashboard AlarmsOne (tiempo real)...");
setupChartJSDefaults(window.Chart);
console.log("[realtime] Chart.js detectado:", !!window.Chart);

// ======================================================
// 2) Render de KPIs y actualización general
// ======================================================
function renderKPIs() {
  const { total, high, devices } = calcKpis(getState());
  const elTotal = $("#kpi-total");
  const elHigh = $("#kpi-high");
  const elDevices = $("#kpi-devices");
  if (elTotal) elTotal.textContent = total;
  if (elHigh) elHigh.textContent = high;
  if (elDevices) elDevices.textContent = devices;
}

function updateAll() {
  const st = getState();
  console.log("[realtime] Estado actual:", st);

  renderKPIs();

  // ❌ NO hay trend en tiempo real

  // Donut de severidad (usa filtros activos)
  renderDonut(st, getActiveCountsForDonut(st));

  // Tabla dispositivos
  renderDeviceTable(st);

  // Barras de acciones
  renderActionBar(actionDataForCurrentFilter(st));

  // Barras msg_severity
  renderMsgSeverityBar(msgSeverityDataForCurrentFilter(st), st.msgSeverityFilter);

  // Alarmas por hora
  renderHourly(st);

  // Level está montado con subscripción (no re-render explícito aquí)
  // Subtype y Log Description
  renderSubtypeBar(subtypeDataForCurrentFilter(st), st.subtypeFilter);
  renderLogDescriptionBar(logDescriptionDataForCurrentFilter(st), st.logDescriptionFilter);

  console.log("[realtime] Gráficos actualizados correctamente ✅");
}

// ======================================================
// 3) Utilidades UI (tabla)
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
// 4) Boot
// ======================================================
let unmountLevel = null;

function boot() {
  console.log("[realtime] DOM listo → inicializando...");
  wireTableSort();

  // Monta Level UNA sola vez
  unmountLevel = mountLevelBar("levelBar");

  // Render inicial del resto
  updateAll();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}

// ======================================================
// 5) Redibujo ante cambios de filtros
// ======================================================
onStateChange(() => {
  console.log("[realtime] Cambio detectado en filtros → refrescando...");
  updateAll();
});

// ======================================================
// 6) Botón refresh (si lo tienes en la topbar)
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
