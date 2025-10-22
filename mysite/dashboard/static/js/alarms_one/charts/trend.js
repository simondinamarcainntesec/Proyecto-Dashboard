// charts/trend.js
import { TXT, AXIS, GRID } from "../theme.js";
import { actions } from "../state.js";

let chart;

export function renderTrend(conf) {
  const ctx = document.getElementById("trendChart").getContext("2d");
  const opts = {
    animation: { duration: 600, easing: "easeOutQuart" },
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: {
        position: "top",
        labels: { color: TXT },
        onClick: (e, item) => {
          const sev = String(item.text).trim();
          actions.toggleSeverity(sev);
        },
      },
      tooltip: { enabled: true },
    },
    scales: {
      x: { ticks: { color: AXIS }, grid: { color: GRID } },
      y: { beginAtZero: true, ticks: { color: AXIS }, grid: { color: GRID } },
    },
  };
  if (!chart) chart = new Chart(ctx, { type: "line", data: conf, options: opts });
  else { chart.data = conf; chart.options = opts; chart.update(); }
}