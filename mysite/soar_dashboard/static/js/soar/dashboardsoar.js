// static/js/soar/dashboardsoar.js
import { setupChartJSDefaults } from "/static/js/soar/theme.js";
import { onStateChange } from "/static/js/soar/state.js";
import { preloadEvents } from "/static/js/soar/data.js";
import { computeKPIs } from "/static/js/soar/selectors.js";

// Charts existentes
import { renderSeverity } from "/static/js/soar/charts/severity.js";
import { renderSecAction } from "/static/js/soar/charts/secaction.js";
import { renderCountries } from "/static/js/soar/charts/countries.js";
import { renderTopDevices } from "/static/js/soar/charts/devices.js";
import { renderTopServices } from "/static/js/soar/charts/services.js";
import { renderTrendDaily } from "/static/js/soar/charts/trend_daily.js";
import { renderTrendHourly } from "/static/js/soar/charts/trend_hourly.js";
import { renderDeviceTable } from "/static/js/soar/charts/devicesTable.js";
import { renderTopIPs } from "/static/js/soar/charts/top_ips.js";

// NUEVO
import { renderApplications } from "/static/js/soar/charts/application.js";

function showLoading(on){
  const el = document.getElementById("loading-overlay");
  if (!el) return;
  if (on) el.classList.add("is-active"); else el.classList.remove("is-active");
}

function renderKPIs(){
  const { total, topDevice, domSeverity, topCountryToday } = computeKPIs();
  const byId = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  byId("kpi-total", total);
  byId("kpi-top-device", topDevice);
  byId("kpi-dom-sev", (domSeverity||"").toUpperCase());
  byId("kpi-top-country", topCountryToday);
}

function renderAll(){
  renderSeverity();
  renderSecAction();
  renderCountries();
  renderTopDevices();
  renderTopServices();
  renderApplications();     // ← NUEVO
  renderTrendDaily();
  renderTrendHourly();
  renderTopIPs("src");
  renderTopIPs("dst");
  renderDeviceTable();
  renderKPIs();
}

async function boot(){
  try{
    showLoading(true);
    setupChartJSDefaults(Chart);
    await preloadEvents();
    renderAll();
    onStateChange(() => renderAll());
  } finally {
    showLoading(false);
  }
}
boot();
