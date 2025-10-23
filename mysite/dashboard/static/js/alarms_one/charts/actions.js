// charts/actions.js
import { AXIS, GRID } from "../theme.js";
import { actions } from "../state.js";

let chart;

/* ===========================
 * Paleta y helpers de color
 * =========================*/
const PALETTE = [
  "#8B5CF6", // purple
  "#10B981", // emerald
  "#F59E0B", // amber
  "#3B82F6", // blue
  "#EF4444", // red
  "#06B6D4", // cyan
  "#F97316", // orange
  "#A855F7", // violet
  "#14B8A6", // teal
  "#EAB308", // yellow
  "#2563EB", // indigo
  "#DC2626", // rose
  "#0EA5E9", // sky
  "#22C55E", // green
];
const withAlpha = (hex, a = "CC") => (hex || "#9CA3AF").slice(0, 7) + a;


const COLOR_BY_ACTION = {
  open: "#b6b910ff",
  allow: "#b9ae10ff",
  pass: "#b9b610ff",

  block: "#EF4444",
  blocked: "#EF4444",
  deny: "#EF4444",
  drop: "#EF4444",

  reset: "#F59E0B",
  timeout: "#F59E0B",

  monitor: "#3B82F6",
  alert: "#3B82F6",
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


export function renderActionBar(payload) {
  const { labels = [], data = [], keys = [] } = payload;
  const ctx = document.getElementById("actionBar").getContext("2d");


  const borders = keys.map((k) => "#e5e7eb");                 
  const fills   = keys.map((k) => withAlpha(colorForActionKey(k)));

  const opts = {
    indexAxis: "y", // barras horizontales (como tenías)
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
    scales: {
      x: {
        beginAtZero: true,
        ticks: { color: AXIS },
        grid: { color: GRID },
      },
      y: {
        type: "category",
        ticks: {
          color: AXIS,
          callback: function (_value, index) {
            const lbs = this.chart?.data?.labels || labels;
            return lbs[index] ?? "";
          },
        },
        grid: { color: GRID },
      },
    },
  };

  const conf = {
    type: "bar",
    data: {
      labels: labels.slice(),
      datasets: [
        {
          label: "Acciones",
          data: data.slice(),
          borderWidth: 2,
          backgroundColor: fills,
          borderColor: borders,
          hoverBorderColor: borders,
        },
      ],
    },
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
    chart.data.labels = conf.data.labels;
    chart.data.datasets[0].data = conf.data.datasets[0].data;
    chart.data.datasets[0].backgroundColor = conf.data.datasets[0].backgroundColor;
    chart.data.datasets[0].borderColor = conf.data.datasets[0].borderColor;
    chart.data.datasets[0].hoverBorderColor = conf.data.datasets[0].hoverBorderColor;
    chart.options = conf.options;
    chart.update();
  }
}
