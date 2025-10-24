// dashboard.js
import { setupChartJSDefaults } from "./theme.js";
import { $ } from "./utils.js";
import { getState, onStateChange } from "./state.js";
import "./data.js";
import {
  getActiveCounts,
  getActiveCountsForDonut,
  calcKpis,
  trendDataForCurrentFilter,
  actionDataForCurrentFilter,
  msgSeverityDataForCurrentFilter,
  // === NUEVO ===
  levelDataForCurrentFilter,      // (se mantiene importado si lo usas en otros lados)
  subtypeDataForCurrentFilter,
  logDescriptionDataForCurrentFilter,
} from "./selectors.js";

import { renderDonut } from "./charts/donut.js";
import { renderTrend } from "./charts/trend.js";
import { renderActionBar } from "./charts/actions.js";
import { renderMsgSeverityBar } from "./charts/msgSeverity.js";
import { renderHourly } from "./charts/hourly.js";
import { renderDeviceTable } from "./charts/devicesTable.js";
// === NUEVO ===
// REEMPLAZA el render clásico por el montaje reactivo de Level:
import { mountLevelBar } from "./charts/level.js";

import { renderSubtypeBar } from "./charts/subtype.js";
import { renderLogDescriptionBar } from "./charts/logDescription.js";

// ======================================================
// 1) Inicialización global
// ======================================================
console.log("[dashboard] Iniciando dashboard AlarmsOne...");

setupChartJSDefaults(window.Chart);
console.log("[dashboard] Chart.js detectado:", !!window.Chart);

// ======================================================
// 2) Render de KPIs y actualización general
// ======================================================
function renderKPIs() {
  const { total, high, devices } = calcKpis(getState());
  $("#kpi-total").textContent = total;
  $("#kpi-high").textContent = high;
  $("#kpi-devices").textContent = devices;
}

function updateAll() {
  const st = getState();
  console.log("[dashboard] Estado actual:", st);

  renderKPIs();
  renderTrend(trendDataForCurrentFilter(st));
  renderDonut(st, getActiveCountsForDonut(st));
  renderDeviceTable(st);
  renderActionBar(actionDataForCurrentFilter(st));
  renderMsgSeverityBar(msgSeverityDataForCurrentFilter(st), st.msgSeverityFilter);
  renderHourly(st);

  // === IMPORTANTE ===
  // Level ahora se actualiza solo (subscribe) mediante mountLevelBar(),
  // por eso NO lo renderizamos aquí para evitar recrearlo cada vez.
  // renderLevelBar(levelDataForCurrentFilter(st), st.levelFilter);  ← eliminado

  // Subtype y LogDescription siguen con el flujo tradicional por ahora
  renderSubtypeBar(subtypeDataForCurrentFilter(st), st.subtypeFilter);
  renderLogDescriptionBar(logDescriptionDataForCurrentFilter(st), st.logDescriptionFilter);

  console.log("[dashboard] Gráficos actualizados correctamente ✅");
}

// ======================================================
// 3) Comportamiento UX (filtros, tabla)
// ======================================================
function wireDateFilter() {
  const form = $("#date-filter");
  if (!form) return;
  const from = form.querySelector('input[name="from"]');
  const to = form.querySelector('input[name="to"]');
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
        if (type === "number") return asc ? Number(av) - Number(bv) : Number(bv) - Number(av);
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
      tbody.innerHTML = "";
      rows.forEach((r) => tbody.appendChild(r));
    });
  });
}

// ======================================================
// 4) Boot (inicio al cargar el documento)
// ======================================================
let unmountLevel = null;

function boot() {
  console.log("[dashboard] DOM listo → inicializando...");
  wireDateFilter();
  wireTableSort();

  // Monta Level UNA sola vez. Internamente:
  // - se subscribe a onStateChange
  // - maneja onClick → actions.toggleLevel(key)
  // - re-renderiza sin recrear el canvas/chart
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
  console.log("[dashboard] Cambio detectado en filtros → refrescando...");
  updateAll();
});

// (Opcional) Si en al