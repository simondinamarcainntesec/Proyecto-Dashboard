// charts/actions.js
import { AXIS, GRID } from "../theme.js";
import { actions, getState } from "../state.js";

let chart;

/* ===========================
 * Paleta y helpers de color
 * =========================*/
const PALETTE = [
  "#8B5CF6", "#10B981", "#F59E0B", "#3B82F6", "#EF4444",
  "#06B6D4", "#F97316", "#A855F7", "#14B8A6", "#EAB308",
  "#2563EB", "#DC2626", "#0EA5E9", "#22C55E",
];
const withAlpha = (hex, a = "CC") => (hex || "#9CA3AF").slice(0, 7) + a;

const COLOR_BY_ACTION = {
  open:   "#b6b910ff",
  allow:  "#b9ae10ff",
  pass:   "#b9b610ff",
  block:  "#EF4444",
  blocked:"#EF4444",
  deny:   "#EF4444",
  drop:   "#EF4444",
  reset:  "#F59E0B",
  timeout:"#F59E0B",
  monitor:"#3B82F6",
  alert:  "#3B82F6",
};

function hashToIndex(str, mod) {
  let h = 5381;
  for (let i = 0; i < str.length; i++) h = ((h << 5) + h) + str.charCodeAt(i);
  return Math.abs(h) % mod;
}
function colorForActionKey(key) {
  const k = String(key ?? "").trim().toLowerCase();
  if (COLOR_BY_ACTION[k]) return COLOR_BY_ACTION[k];
  if (!k) return "#9CA3AF";
  return PALETTE[hashToIndex(k, PALETTE.length)];
}

/**
 * renderActionBar(payload, activeKey?)
 * - Si activeKey no viene, lo toma de getState().actionFilter
 * - Atenúa todas las barras ≠ activeKey con rgba(255,255,255,0.18)
 * - Borde blanco siempre visible (no solo en hover)
 */
export function renderActionBar(payload, activeKey) {
  const { labels = [], data = [], keys = [] } = payload;
  const el = document.getElementById("actionBar");
  if (!el) return;

  // activeKey por state si no viene
  const stateKey = (getState()?.actionFilter ?? "").toString();
  const focusKey = (activeKey ?? stateKey).toString();

  const ctx = el.getContext("2d");
  const norm = (s) => String(s ?? "").trim().toLowerCase();

  // Colores con efecto de foco (igual a msgSeverity)
  const backgroundColors = keys.map((k) => {
    if (focusKey && norm(k) !== norm(focusKey)) return "rgba(255,255,255,0.18)";
    return withAlpha(colorForActionKey(k), "FF");
  });

  // Borde blanco siempre
  const BORDER = "#e5e7eb";

  const conf = {
    type: "bar",
    data: {
      labels: labels.slice(),
      datasets: [{
        label: "Acciones",
        data: data.slice(),
        backgroundColor: backgroundColors,
        borderColor: BORDER,
        hoverBorderColor: BORDER,
        borderWidth: 2,
        hoverBorderWidth: 2,
        borderSkipped: false,   // siempre los 4 lados
      }],
    },
    options: {
      indexAxis: "y",
      animation: { duration: 600, easing: "easeOutQuart" },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: true,
          callbacks: {
            title: (items) => (items?.[0] ? String(items[0].label) : ""),
            label: (item) => `Cantidad: ${item.formattedValue}`,
          },
        },
      },
      elements: {
        bar: { borderWidth: 2, borderSkipped: false }, // refuerzo global
      },
      scales: {
        x: { beginAtZero: true, ticks: { color: AXIS }, grid: { color: GRID } },
        y: {
          type: "category",
          ticks: {
            color: AXIS,
            callback: function (_v, i) {
              const lbs = this.chart?.data?.labels || labels;
              return lbs[i] ?? "";
            },
          },
          grid: { color: GRID },
        },
      },
    },
  };

  if (!chart) {
    chart = new Chart(ctx, conf);
    ctx.canvas.onclick = (evt) => {
      const elp = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!elp.length) return;
      const idx = elp[0].index;
      actions.toggleAction?.(keys[idx]); // usar la key cruda
    };
  } else {
    chart.data.labels = conf.data.labels;
    chart.data.datasets[0].data = conf.data.datasets[0].data;
    chart.data.datasets[0].backgroundColor = conf.data.datasets[0].backgroundColor;
    chart.data.datasets[0].borderColor = conf.data.datasets[0].borderColor;
    chart.data.datasets[0].hoverBorderColor = conf.data.datasets[0].hoverBorderColor;
    chart.options = conf.options;
    chart.update();
  }
}
