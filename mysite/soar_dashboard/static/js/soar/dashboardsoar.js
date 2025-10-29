import { setupChartJSDefaults } from "/static/js/soar/theme.js";
import { onStateChange } from "/static/js/soar/state.js";
import { getEvents, preloadEvents } from "/static/js/soar/data.js";
import { computeKPIs } from "/static/js/soar/selectors.js";

// Charts
import { renderSeverity } from "/static/js/soar/charts/severity.js";
import { renderSecAction } from "/static/js/soar/charts/secaction.js";
import { renderCountries } from "/static/js/soar/charts/countries.js";
import { renderTopDevices } from "/static/js/soar/charts/devices.js";
import { renderTopServices } from "/static/js/soar/charts/services.js";
import { renderTopProto } from "/static/js/soar/charts/proto.js";
import { renderDeviceTable } from "/static/js/soar/charts/devicesTable.js";

function showLoading(on){
  const el = document.getElementById("loading-overlay");
  if (!el) return;
  if (on) el.classList.add("is-active"); else el.classList.remove("is-active");
}

function renderKPIs(){
  const { total, pctBlocked, topDevice, domSeverity, topCountryToday } = computeKPIs();
  const byId = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };

  byId("kpi-total", total);
  byId("kpi-blocked", `${pctBlocked}%`);
  byId("kpi-top-device", topDevice);
  byId("kpi-dom-sev", domSeverity.toUpperCase());
  byId("kpi-top-country", topCountryToday); // ← ahora ignora fechas N/A
}

async function boot(){
  try{
    showLoading(true);
    setupChartJSDefaults(Chart);
    await preloadEvents(); // lee #soar-events

    // primer render
    renderSeverity();
    renderSecAction();
    renderCountries();
    renderTopDevices();
    renderTopServices();
    renderTopProto();
    renderDeviceTable();
    renderKPIs();

    // suscribirse a cambios de estado: re-render todo
    onStateChange(() => {
      renderSeverity();
      renderSecAction();
      renderCountries();
      renderTopDevices();
      renderTopServices();
      renderTopProto();
      renderDeviceTable();
      renderKPIs();
    });
  } finally {
    showLoading(false);
  }
}

boot();
