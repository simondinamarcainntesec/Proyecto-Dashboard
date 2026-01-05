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

function norm(s) { return String(s ?? "").trim().toLowerCase(); }

/* =========================
 * "Nice ticks" enteros
 * ========================= */
function niceStep(maxValue, targetTicks = 7) {
  const max = Math.max(0, Number(maxValue) || 0);
  if (max <= 10) return 1;

  const raw = max / targetTicks;
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const normv = raw / pow;

  let mult;
  if (normv <= 1) mult = 1;
  else if (normv <= 2) mult = 2;
  else if (normv <= 5) mult = 5;
  else mult = 10;

  return Math.max(1, Math.round(mult * pow));
}
function ceilToStep(v, step) {
  const n = Math.max(0, Number(v) || 0);
  const s = Math.max(1, Number(step) || 1);
  return Math.ceil(n / s) * s;
}

/**
 * renderActionBar(payload, activeKey?)
 * - Atenúa todas las barras ≠ activeKey con rgba(255,255,255,0.18)
 * - Borde blanco siempre visible
 * - Sin decimales (ticks + tooltip)
 */
export function renderActionBar(payload, activeKey) {
  const { labels = [], data = [], keys = [] } = payload;
  const el = document.getElementById("actionBar");
  if (!el) return;

  // activeKey por state si no viene
  const stateKey = (getState()?.actionFilter ?? "").toString();
  const focusKey = (activeKey ?? stateKey).toString();

  // Colores con efecto de foco
  const backgroundColors = keys.map((k) => {
    if (focusKey && norm(k) !== norm(focusKey)) return "rgba(255,255,255,0.18)";
    return withAlpha(colorForActionKey(k), "FF");
  });

  // Borde blanco siempre
  const BORDER = "#e5e7eb";

  const maxVal = Math.max(0, ...(data || []).map((v) => Number(v || 0)));
  const step = niceStep(maxVal, 7);
  const suggestedMax = ceilToStep(maxVal, step);

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
        borderSkipped: false,
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
            label: (item) => `Cantidad: ${Math.round(item.parsed?.x ?? item.raw ?? 0)}`,
          },
        },
      },
      elements: { bar: { borderWidth: 2, borderSkipped: false } },
      scales: {
        x: {
          beginAtZero: true,
          suggestedMax,
          ticks: {
            color: AXIS,
            stepSize: step,
            precision: 0,
            callback: (v) => String(Math.round(v)),
          },
          grid: { color: GRID },
        },
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
    const ctx = el.getContext("2d");
    chart = new Chart(ctx, conf);
    ctx.canvas.onclick = (evt) => {
      const elp = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!elp?.length) return;
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
