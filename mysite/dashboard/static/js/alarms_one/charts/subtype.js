// charts/subtype.js
import { actions } from "../state.js";
import { colorFor } from "../theme.js";

let subtypeChart;

function trunc(s, n = 14) {
  const t = String(s ?? "");
  return t.length > n ? t.slice(0, n - 1) + "…" : t;
}
function eqCI(a, b) {
  return String(a).trim().toLowerCase() === String(b).trim().toLowerCase();
}

export function renderSubtypeBar(ds, activeKey = "") {
  const ctx = document.getElementById("subtypeBar");
  if (!ctx) return;

  // Normaliza dataset
  const labels = Array.isArray(ds?.labels) ? ds.labels.map(String) : [];
  const data = labels.map((_, i) => Number((ds?.data || [])[i] || 0));

  // Colores (resalta si hay filtro activo)
  const bg = labels.map((l) => (activeKey && eqCI(l, activeKey) ? colorFor(l) : colorFor(l) + "99"));
  const border = labels.map((l) => colorFor(l));

  const cfg = {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Subtype",
          data,
          backgroundColor: bg,
          borderColor: border,
          borderWidth: 1.5,
          hoverBackgroundColor: border,
          hoverBorderColor: border,
        },
      ],
    },
    options: {
      animation: false,
      maintainAspectRatio: false,
      responsive: true,
      indexAxis: "x",
      onClick: (_, elements) => {
        if (!elements || !elements.length) return;
        const idx = elements[0].index;
        const key = labels[idx];
        actions.toggleSubtype?.(key);
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => (items?.[0] ? String(items[0].label) : ""),
            label: (item) => `Cantidad: ${item.formattedValue}`,
          },
        },
      },
      scales: {
        x: {
          type: "category",
          offset: true,
          ticks: {
            autoSkip: false,
            maxRotation: 0,
            minRotation: 0,
            padding: 6,
            font: { size: 12, weight: "700" },
            callback: (_, i) => trunc(labels[i]),
          },
          grid: { display: false },
        },
        y: {
          beginAtZero: true,
        },
      },
      layout: { padding: { bottom: 6 } },
      categoryPercentage: 0.8,
      barPercentage: 0.9,
    },
  };

  if (subtypeChart) {
    subtypeChart.data.labels = labels;
    subtypeChart.data.datasets[0].data = data;
    subtypeChart.data.datasets[0].backgroundColor = bg;
    subtypeChart.data.datasets[0].borderColor = border;
    subtypeChart.update();
  } else {
    subtypeChart = new window.Chart(ctx, cfg);
  }
}
