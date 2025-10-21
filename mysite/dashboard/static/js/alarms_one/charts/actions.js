// charts/actions.js
import { AXIS, GRID } from "../theme.js";
import { actions } from "../state.js";

let chart;

export function renderActionBar(payload) {
  const { labels, data, keys } = payload;
  const ctx = document.getElementById("actionBar").getContext("2d");
  const opts = {
    indexAxis: "y",
    animation: { duration: 600, easing: "easeOutQuart" },
    plugins: { legend: { display: false }, tooltip: { callbacks: { title: (items) => items.map((i) => labels[i.dataIndex]) } } },
    scales: {
      x: { beginAtZero: true, ticks: { color: AXIS }, grid: { color: GRID } },
      y: { ticks: { color: AXIS, callback: (v, i) => labels[i] }, grid: { color: GRID } },
    },
  };
  const conf = {
    type: "bar",
    data: { labels, datasets: [{ label: "Acciones", data, borderWidth: 2, backgroundColor: "#8B5CF6", borderColor: "#e5e7eb" }] },
    options: opts,
  };

  if (!chart) {
    chart = new Chart(ctx, conf);
    ctx.canvas.onclick = (evt) => {
      const el = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!el.length) return;
      const idx = el[0].index;
      actions.toggleAction(keys[idx]);
    };
  } else {
    chart.data = conf.data;
    chart.options = conf.options;
    chart.update();
  }
}
