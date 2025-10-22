// charts/level.js
import { actions } from "../state.js";
import { colorFor } from "../theme.js";

let levelChart;

function trunc(s, n = 30) {
  const t = String(s ?? "");
  return t.length > n ? t.slice(0, n - 1) + "…" : t;
}

function eqCI(a, b) {
  return String(a).trim().toLowerCase() === String(b).trim().toLowerCase();
}

export function renderLevelBar(ds, activeKey = "") {
  const ctx = document.getElementById("levelBar");
  if (!ctx) return;

  const labels = Array.isArray(ds?.labels) ? ds.labels.map(String) : [];
  const data = labels.map((_, i) => Number((ds?.data || [])[i] || 0));
  const bg = labels.map((l) => (activeKey && eqCI(l, activeKey) ? colorFor(l) : colorFor(l) + "99"));
  const border = labels.map((l) => colorFor(l));

  const cfg = {
    type: "bar",
    data: { labels, datasets: [{ label: "Level", data, backgroundColor: bg, borderColor: border, borderWidth: 1.5 }] },
    options: {
      indexAxis: "x",
      onClick: (_, elements) => {
        if (!elements || !elements.length) return;
        const idx = elements[0].index;
        const key = labels[idx];
        actions.toggleLevel(key);
      },
      plugins: { legend: { display: false } },
      scales: {
        x: {
          type: "category",
          ticks: { callback: (_, idx) => trunc(labels[idx]), maxRotation: 0, autoSkip: true },
        },
        y: { beginAtZero: true },
      },
      categoryPercentage: 0.8,
      barPercentage: 0.9,
      animation: false,
      maintainAspectRatio: false,
      responsive: true,
    },
  };

  if (levelChart) {
    levelChart.data.labels = labels;
    levelChart.data.datasets[0].data = data;
    levelChart.data.datasets[0].backgroundColor = bg;
    levelChart.data.datasets[0].borderColor = border;
    levelChart.update();
  } else {
    levelChart = new window.Chart(ctx, cfg);
  }
}
