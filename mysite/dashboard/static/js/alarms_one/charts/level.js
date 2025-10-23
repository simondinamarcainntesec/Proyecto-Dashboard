
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
  notice: "#8B5CF6",       // purple
  alert: "#10B981",        // emerald
  error: "#F59E0B",        // amber
  information: "#3B82F6",  // blue
  critical: "#EF4444",     // red
  "n/a": "#06B6D4",        // cyan
  warning: "#F97316",      // orange
};
const DEFAULT_COLOR = "#9CA3AF"; // gris fallback
const withAlpha = (hex, alphaHex = "CC") =>
  (hex || DEFAULT_COLOR).slice(0, 7) + alphaHex;

let chart;
let canvas;
let mounted = false;

const pretty = (k) => LEVEL_NAME_MAP[String(k ?? "").trim()] || String(k ?? "");
const colorForPretty = (name) =>
  COLOR_BY_NAME[String(name ?? "").trim().toLowerCase()] || DEFAULT_COLOR;

function buildDataset() {
  const { labels: rawLabels, data: values = [], keys: rawKeys } =
    levelDataForCurrentFilter(getState());


  const keys =
    Array.isArray(rawKeys) && rawKeys.length === (rawLabels || []).length
      ? rawKeys.map(String)
      : (rawLabels || []).map(String);


  const prettyNames = keys.map((k) => pretty(k));


  const fill = prettyNames.map((p) => withAlpha(colorForPretty(p)));
  const stroke = prettyNames.map((p) => colorForPretty(p));


  const labelToKey = Object.fromEntries(prettyNames.map((p, i) => [p, keys[i]]));


  const series = prettyNames.map((_, i) => Number(values[i] || 0));

  return { labels: prettyNames, series, fill, stroke, labelToKey };
}

function render() {
  const { labels, series, fill, labelToKey } = buildDataset();

  const cfg = {
    type: "bar",
    data: {
      labels, 
      datasets: [
        {
          label: "Level",
          data: series,                
          backgroundColor: fill,      
          borderColor: "#e5e7eb",      
          borderWidth: 2,
          hoverBorderColor: "#e5e7eb",
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
            label: (item) => `Cantidad: ${item.formattedValue}`,
          },
        },
      },
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
          ticks: { color: AXIS },
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
      const hits = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
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
