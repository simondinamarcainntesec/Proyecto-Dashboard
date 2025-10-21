// charts/hourly.js
import data from "../data.js";
import { AXIS, GRID } from "../theme.js";
import { findKeyCI } from "../utils.js";
import { actions } from "../state.js";

let chart;

export function renderHourly(state) {
  const el = document.getElementById("hourlyChart");
  if (!el) return;
  const ctx = el.getContext("2d");

  let series = data.hourData.slice();
  let label = "Alarmas (por hora, rango actual)";

  if (state.deviceFilter) {
    const dk = data.canonicalDeviceKey(state.deviceFilter);
    series = data.hourLabels.map((h) => {
      const m = data.devByHourRaw[h] || {};
      return Number(m[dk] || 0);
    });
    label = `Alarmas por hora — Dispositivo: ${dk}`;
  } else if (state.severityFilter) {
    series = data.hourLabels.map((h) => {
      const m = data.sevByHourRaw[h] || {};
      const hk = findKeyCI(m, state.severityFilter) || state.severityFilter;
      return Number(m[hk] || 0);
    });
    label = `Alarmas por hora — Severidad: ${state.severityFilter}`;
  } else if (state.actionFilter) {
    series = data.hourLabels.map((h) => {
      const m = data.actByHourNorm[h] || {};
      return Number(m[state.actionFilter] || 0);
    });
    label = `Alarmas por hora — Acción: ${state.actionFilter}`;
  } else if (state.msgSeverityFilter) {
    series = data.hourLabels.map((h) => {
      const m = data.msgSeverityByHourRaw[h] || {};
      return Number(m[state.msgSeverityFilter] || 0);
    });
    label = `Alarmas por hora — Msg Severity: ${state.msgSeverityFilter}`;
  }

  const conf = {
    type: "bar",
    data: { labels: data.hourLabels.map((h) => `${h}:00`), datasets: [{ label, data: series, borderWidth: 2, backgroundColor: "#22C55E", borderColor: "#e5e7eb" }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 600, easing: "easeOutQuart" },
      plugins: { legend: { display: false }, tooltip: { enabled: true } },
      scales: {
        x: { ticks: { color: AXIS, autoSkip: false, maxRotation: 0, minRotation: 0 }, grid: { color: GRID } },
        y: { beginAtZero: true, ticks: { color: AXIS }, grid: { color: GRID } },
      },
    },
  };

  if (!chart) {
    chart = new Chart(ctx, conf);
    ctx.canvas.onclick = (evt) => {
      const points = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!points.length) return;
      const idx = points[0].index;
      const h = data.hourLabels[idx];
      actions.toggleHour(h);
    };
  } else {
    chart.data = conf.data;
    chart.options = conf.options;
    chart.update();
  }
}
