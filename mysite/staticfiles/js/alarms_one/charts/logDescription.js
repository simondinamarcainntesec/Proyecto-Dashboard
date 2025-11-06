// charts/logDescription.js
import { actions } from "../state.js";
import { EMPH } from "../theme.js";

let logDescChart;

function trunc(s, n = 18) {
  const t = String(s ?? "");
  return t.length > n ? t.slice(0, n - 1) + "…" : t;
}

/**
 * Dibuja el bar chart de Log Description mostrando SIEMPRE los Top N (default 10)
 * tras aplicar cualquier filtro (device, action, severity, hour, msgSeverity).
 */
export function renderLogDescriptionBar(ds, activeKey = "", topN = 10) {
  const ctx = document.getElementById("logDescBar");
  if (!ctx) return;

  // 1) Normaliza y ordena desc por valor
  const labelsIn = Array.isArray(ds?.labels) ? ds.labels : [];
  const dataIn = Array.isArray(ds?.data) ? ds.data : [];
  const pairs = labelsIn.map((label, i) => ({
    label: String(label ?? "N/A"),
    value: Number(dataIn[i] ?? 0),
  }));
  pairs.sort((a, b) => b.value - a.value);

  // 2) Top N (por valor)
  const top = pairs.slice(0, topN);
  const labels = top.map(p => p.label);
  const data = top.map(p => p.value);

  // 3) Config Chart.js
  const cfg = {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Log Description",
          data,
          borderWidth: 1.5,
          // Colores suaves; si quieres, cámbialos a tu paleta
          backgroundColor: "rgba(96, 165, 250, 0.35)",
          borderColor: "rgba(96, 165, 250, 0.95)",
          hoverBackgroundColor: "rgba(96, 165, 250, 0.55)",
          hoverBorderColor: "rgba(96, 165, 250, 1)",
        },
      ],
    },
    options: {
      animation: false,
      onClick: (_, elements) => {
        if (!elements || !elements.length) return;
        const idx = elements[0].index;
        const key = labels[idx];
        actions.toggleLogDescription(key);
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => (items?.[0] ? String(items[0].label) : ""),
            label: (item) => `Cantidad: ${item.formattedValue}`,
          },
          titleColor: EMPH,
          bodyColor: EMPH,
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
      maintainAspectRatio: false,
      responsive: true,
    },
  };

  // 4) Update / Init
  if (logDescChart) {
    logDescChart.data.labels = labels;
    logDescChart.data.datasets[0].data = data;
    logDescChart.update();
  } else {
    logDescChart = new window.Chart(ctx, cfg);
  }
}