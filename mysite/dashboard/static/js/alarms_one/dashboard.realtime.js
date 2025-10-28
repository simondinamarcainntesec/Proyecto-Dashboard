// dashboard.realtime.js (Tiempo Real) — sin trend
import { setupChartJSDefaults } from "./theme.js";
import { $ } from "./utils.js";
import { getState, onStateChange } from "./state.js";
import "./data.js";

import {
  getActiveCountsForDonut,
  calcKpis,
  actionDataForCurrentFilter,
  msgSeverityDataForCurrentFilter,
  levelDataForCurrentFilter,     // coherencia de exports
  subtypeDataForCurrentFilter,
  logDescriptionDataForCurrentFilter,
} from "./selectors.js";

import { renderDonut } from "./charts/donut.js";
import { renderActionBar } from "./charts/actions.js";
import { renderMsgSeverityBar } from "./charts/msgSeverity.js";
import { renderHourly } from "./charts/hourly.js";
import { renderDeviceTable } from "./charts/devicesTable.js";
import { mountLevelBar } from "./charts/level.js";
import { renderSubtypeBar } from "./charts/subtype.js";
import { renderLogDescriptionBar } from "./charts/logDescription.js";

// ======================================================
// 0) Helper: ¿hay estado vacío?
//    Si el template renderizó el "empty-state", no montamos gráficos.
// ======================================================
function isEmptyState() {
  return !!document.querySelector(".empty-state");
}

// ======================================================
// 1) Inicialización global (solo si no es empty-state)
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
  // Si hay empty-state, solo cableamos el botón OK y salimos
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

  // Monta Level UNA sola vez (si está en el DOM)
  const levelEl = document.getElementById("levelBar");
  if (levelEl) {
    unmountLevel = mountLevelBar("levelBar");
  }

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
  if (isEmptyState()) return; // no hay nada que refrescar
  console.log("[realtime] Cambio detectado en filtros → refrescando...");
  updateAll();
});

// ======================================================
// 6) Botón refresh (topbar)
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
