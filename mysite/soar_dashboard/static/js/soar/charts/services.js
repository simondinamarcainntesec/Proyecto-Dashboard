// charts/top-services.js
import { AXIS, GRID } from "/static/js/soar/theme.js";
import { actions, getState } from "/static/js/soar/state.js";
import { selectTopServicesPayload } from "/static/js/soar/selectors.js";
import { collectAlarmIdsForCurrentFilter, ensureHeaderButton, showAlarms } from "/static/js/soar/helpers/alarms-helper.js";

let chart;
const norm = (s) => String(s ?? "").trim().toLowerCase();

export function renderTopServices() {
  const payload = selectTopServicesPayload(10, true);

  const el = document.getElementById("chartServices");
  if (!el) return;
  const ctx = el.getContext("2d");

  const labels = (payload.labels || []).slice();
  const values = (payload.data || []).slice();
  const active = norm(getState().serviceFilter || "");

  const backgroundColors = labels.map((lbl) =>
    active && norm(lbl) !== active ? "rgba(255,255,255,0.18)" : "#10B981"
  );

  const conf = {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Eventos",
        data: values,
        backgroundColor: backgroundColors,
        borderColor: "#e5e7eb",
        hoverBorderColor: "#e5e7eb",
        borderWidth: 2,
        hoverBorderWidth: 2,
        borderSkipped: false,
        borderRadius: 6,
        barThickness: "flex",
        categoryPercentage: 0.8,
        barPercentage: 0.7,
      }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 600, easing: "easeOutQuart" },
      plugins: { legend: { display: false }, tooltip: { intersect: false } },
      elements: { bar: { borderSkipped: false } },
      scales: {
        x: { beginAtZero: true, ticks: { color: AXIS }, grid: { color: GRID } },
        y: {
          type: "category",
          ticks: { color: AXIS, callback: (_v, i) => labels[i] ?? _v },
          grid: { color: GRID },
        },
      },
    },
  };

  if (!chart) {
    chart = new Chart(ctx, conf);

    // Toggle al hacer click en una barra
    ctx.canvas.onclick = (evt) => {
      const els = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!els.length) return;
      const idx = els[0].index;
      actions.toggleService?.(labels[idx]);
    };
    ctx.canvas.style.cursor = "pointer";

    // Botón "Ver alarmas" (esquina superior derecha del card)
    ensureHeaderButton(ctx.canvas, "btn-see-alarms-services", () => {
      // extra: si hay un servicio activo, lo reforzamos; si no, usamos filtros tal cual
      const activeSvc = norm(getState().serviceFilter || "");
      const ids = collectAlarmIdsForCurrentFilter(activeSvc ? (r) => norm(r?.service) === activeSvc : undefined);
      showAlarms(ids);
    });
    return;
  }

  // Update
  chart.data.labels = labels;
  const ds = chart.data.datasets[0];
  ds.data = values;
  ds.backgroundColor = backgroundColors;
  chart.options.scales.y.ticks.callback = (_v, i) => labels[i] ?? _v;
  chart.update();
}
