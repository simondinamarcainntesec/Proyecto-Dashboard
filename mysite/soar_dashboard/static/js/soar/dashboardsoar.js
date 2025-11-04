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
import { renderTopProto } from "/static/js/soar/charts/proto.js";
import { renderDeviceTable } from "/static/js/soar/charts/devicesTable.js";
import { renderTrendDaily } from "/static/js/soar/charts/trend_daily.js";
import { renderTrendHourly } from "/static/js/soar/charts/trend_hourly.js";

// NUEVOS
import { renderSources } from "/static/js/soar/charts/sources.js";
import { renderTopIPs } from "/static/js/soar/charts/top_ips.js";
import { renderServiceProtoStack } from "/static/js/soar/charts/service_proto_stack.js";
import { renderInternalExternal } from "/static/js/soar/charts/internal_external.js";

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
  byId("kpi-dom-sev", (domSeverity || "n/a").toUpperCase());
  byId("kpi-top-country", topCountryToday);
}

function wireRefresh(){
  const btn = document.getElementById("btn-refresh");
  if (!btn) return;
  btn.addEventListener("click", () => location.reload());
}

function wireSectionChips(){
  const chips = document.querySelectorAll(".section-chips .chip");
  const cards = document.querySelectorAll(".grid-main .card[data-groups]");

  const show = (key) => {
    chips.forEach(c => c.classList.remove("active"));
    document.querySelector(`.section-chips .chip[data-sec="${key}"]`)?.classList.add("active");

    cards.forEach(card => {
      const groups = (card.dataset.groups || "").split(",").map(s => s.trim());
      const visible = key === "all" || groups.includes(key);
      card.style.display = visible ? "" : "none";
    });
  };

  chips.forEach(btn => btn.addEventListener("click", () => show(btn.dataset.sec)));
  // estado inicial:
  show("all");
}

function renderAllCharts(){
  // existentes
  renderSeverity();
  renderSecAction();
  renderCountries();
  renderTopDevices();
  renderTopServices();
  renderTopProto();
  renderDeviceTable();
  renderTrendDaily();
  renderTrendHourly();
  // nuevos
  renderSources();
  renderTopIPs();
  renderServiceProtoStack();
  renderInternalExternal();
  // KPIs
  renderKPIs();
}

async function boot(){
  try{
    showLoading(true);
    setupChartJSDefaults(Chart);
    await preloadEvents();
    wireRefresh();
    wireSectionChips();
    renderAllCharts();
    onStateChange(() => renderAllCharts());
  } finally {
    showLoading(false);
  }
}

boot();
