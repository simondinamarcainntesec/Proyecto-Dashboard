// charts/level.js
import { getState, onStateChange, actions } from "../state.js";
import { levelDataForCurrentFilter } from "../selectors.js";
import { AXIS, GRID } from "../theme.js";

const LEVEL_NAME_MAP = {
  "0": "notice",
  "1": "alert",
  "2": "error",
  "3": "information",
  "4": "critical",
  "5": "n/a",
  "6": "warning",
};

const COLOR_BY_NAME = {
  notice: "#8B5CF6",
  alert: "#10B981",
  error: "#F59E0B",
  information: "#3B82F6",
  critical: "#EF4444",
  "n/a": "#06B6D4",
  warning: "#F97316",

  // por si tus "levels" vienen como estados (como en tu screenshot)
  active: "#22C55E",
  dormant: "#F59E0B",
  "dormant, active": "#3B82F6",
};

// Paleta fallback (si aparece un label nuevo no mapeado)
const FALLBACK_PALETTE = [
  "#22C55E", "#3B82F6", "#F59E0B", "#EF4444",
  "#8B5CF6", "#10B981", "#06B6D4", "#F97316",
  "#A855F7", "#14B8A6", "#EAB308", "#FB7185",
];

const DEFAULT_COLOR = "#9CA3AF";
const withAlpha = (hex, alphaHex = "CC") =>
  (hex || DEFAULT_COLOR).slice(0, 7) + alphaHex;

// hash simple para elegir color por texto de forma estable
function hashStr(s) {
  const str = String(s ?? "");
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) | 0;
  return Math.abs(h);
}
function colorFromString(name) {
  const idx = hashStr(name) % FALLBACK_PALETTE.length;
  return FALLBACK_PALETTE[idx] || DEFAULT_COLOR;
}

// ====== TICKS "NICE" (10 en 10 / 100 en 100 / etc.) ======
function niceStep(maxValue, targetTicks = 7) {
  const max = Math.max(0, Number(maxValue) || 0);
  if (max <= 10) return 1;

  const raw = max / targetTicks; // step ideal
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / pow;

  // 1-2-5-10
  let mult;
  if (norm <= 1) mult = 1;
  else if (norm <= 2) mult = 2;
  else if (norm <= 5) mult = 5;
  else mult = 10;

  return Math.max(1, Math.round(mult * pow));
}

function ceilToStep(v, step) {
  const n = Math.max(0, Number(v) || 0);
  const s = Math.max(1, Number(step) || 1);
  return Math.ceil(n / s) * s;
}

let chart;
let canvas;
let mounted = false;

const pretty = (k) => LEVEL_NAME_MAP[String(k ?? "").trim()] || String(k ?? "");
const colorForPretty = (name) => {
  const key = String(name ?? "").trim().toLowerCase();
  return COLOR_BY_NAME[key] || colorFromString(key);
};

function buildDataset() {
  const state = getState();
  const { labels: rawLabels, data: values = [], keys: rawKeys } =
    levelDataForCurrentFilter(state);

  const keys =
    Array.isArray(rawKeys) && rawKeys.length === (rawLabels || []).length
      ? rawKeys.map(String)
      : (rawLabels || []).map(String);

  const prettyNames = keys.map((k) => pretty(k));

  // label mostrado → clave original (para click)
  const labelToKey = Object.fromEntries(prettyNames.map((p, i) => [p, keys[i]]));

  const series = prettyNames.map((_, i) => Number(values[i] || 0));

  // === EFECTO DE FOCO ===
  const activePretty = state.levelFilter ? pretty(state.levelFilter) : null;

  const backgroundColors = prettyNames.map((p) => {
    if (activePretty && p.toLowerCase() !== activePretty.toLowerCase()) {
      return "rgba(255,255,255,0.18)";
    }
    return withAlpha(colorForPretty(p), "FF");
  });

  return { labels: prettyNames, series, backgroundColors, labelToKey };
}

function render() {
  const { labels, series, backgroundColors, labelToKey } = buildDataset();

  const BORDER = "#e5e7eb";

  // ====== step dinámico según el máximo (10/100/500/etc.) ======
  const maxVal = Math.max(0, ...series);
  const step = niceStep(maxVal, 7);
  const suggestedMax = ceilToStep(maxVal, step);

  const cfg = {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Level",
          data: series,
          backgroundColor: backgroundColors,
          borderColor: BORDER,
          hoverBorderColor: BORDER,
          borderWidth: 2,
          hoverBorderWidth: 2,
          borderSkipped: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: "x",
      animation: { duration: 600, easing: "easeOutQuart" },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => (items?.[0] ? String(items[0].label) : ""),
            // sin separadores raros (plano)
            label: (item) => `Cantidad: ${Math.round(item.parsed.y)}`,
          },
        },
      },
      elements: { bar: { borderWidth: 2, borderSkipped: false } },
      scales: {
        x: {
          type: "category",
          ticks: {
            color: AXIS,
            autoSkip: false,
            maxRotation: 0,
            minRotation: 0,
            font: { size: 12, weight: "600" },
            callback: function (value, index) {
              if (typeof this.getLabelForValue === "function") {
                return this.getLabelForValue(value);
              }
              const lbs = this.chart?.data?.labels || [];
              return lbs[index] ?? value;
            },
          },
          grid: { color: GRID },
        },
        y: {
          beginAtZero: true,
          suggestedMax,
          ticks: {
            color: AXIS,
            stepSize: step,
            precision: 0,
            callback: (v) => String(Math.round(v)), // sin puntos (miles)
          },
          grid: { color: GRID },
        },
      },
    },
  };

  if (!chart) {
    const ctx = canvas.getContext("2d");
    chart = new window.Chart(ctx, cfg);
    chart.$levelLabelToKey = labelToKey;

    canvas.onclick = (evt) => {
      if (!chart) return;
      const hits = chart.getElementsAtEventForMode(
        evt,
        "nearest",
        { intersect: true },
        true
      );
      if (!hits?.length) return;
      const idx = hits[0].index;
      const lbl = chart.data.labels?.[idx];
      const key = chart.$levelLabelToKey?.[lbl];
      if (key) actions.toggleLevel?.(key);
    };
  } else {
    chart.data.labels = cfg.data.labels;
    chart.data.datasets[0].data = cfg.data.datasets[0].data;
    chart.data.datasets[0].backgroundColor = cfg.data.datasets[0].backgroundColor;
    chart.data.datasets[0].borderColor = cfg.data.datasets[0].borderColor;
    chart.data.datasets[0].hoverBorderColor = cfg.data.datasets[0].hoverBorderColor;
    chart.options = cfg.options;
    chart.$levelLabelToKey = labelToKey;
    chart.update();
  }
}

export function mountLevelBar(canvasId = "levelBar") {
  if (mounted) return () => {};
  canvas = document.getElementById(canvasId);
  if (!canvas) return () => {};

  render();
  const unsub = onStateChange(() => render());
  mounted = true;

  return function unmount() {
    unsub && unsub();
    if (chart) chart.destroy();
    chart = null;
    mounted = false;
  };
}
