import { TXT, AXIS, GRID } from "/static/js/soar/theme.js";
import { selectTrendByDatePayload } from "/static/js/soar/selectors.js";
import { ensureHeaderButton, collectAlarmIdsForCurrentFilter, showAlarms } from "/static/js/soar/helpers/alarms-helper.js";

let chart;

export function renderTrendDaily() {
  // Respeta filtros externos; este gráfico NO aplica filtros propios al click
  const payload = selectTrendByDatePayload();
  const el = document.getElementById("chartTrendDaily");
  if (!el) return;

  const ctx = el.getContext("2d");
  const labels = Array.isArray(payload.labels) ? payload.labels.slice() : [];
  const data   = Array.isArray(payload.data)   ? payload.data.slice()   : [];

  const dataConf = {
    labels,
    datasets: [{
      label: "Alarmas",
      data,
      tension: 0.25,
      fill: false,
      borderColor: "#60A5FA",
      backgroundColor: "#60A5FA",
      pointRadius: 3,
      pointHoverRadius: 5,
      borderWidth: 2
    }],
  };

  const opts = {
    responsive: true,
    maintainAspectRatio: false,
    // Animación consistente con el resto
    animation: { duration: 600, easing: "easeOutQuart" },
    animations: {
      numbers: { type: "number", duration: 600, easing: "easeOutQuart" },
      tension: { duration: 600, easing: "easeOutQuart", from: 0.35, to: 0.25 },
    },
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { position: "top", labels: { color: TXT }, onClick: () => {} },
      tooltip: { enabled: true },
    },
    scales: {
      x: { type: "category", ticks: { color: AXIS }, grid: { color: GRID } },
      y: { beginAtZero: true, ticks: { color: AXIS }, grid: { color: GRID } },
    },
    // sin clicks del usuario (solo vista)
    events: ["mousemove", "mouseout", "touchstart", "touchmove", "touchend"],
  };

  if (!chart) {
    chart = new Chart(ctx, { type: "line", data: dataConf, options: opts });

    // Botón “Ver alarmas” arriba-derecha (mismos helpers)
    ensureHeaderButton(ctx.canvas, "btn-see-alarms-daily", () => {
      const ids = collectAlarmIdsForCurrentFilter(); // respeta TODO lo que haya en state
      showAlarms(ids);
    });
  } else {
    chart.data = dataConf;
    chart.options = opts;
    chart.update();
  }

  // Cursor normal (no clickeable)
  ctx.canvas.style.cursor = "default";
  ctx.canvas.onclick = null;
}
