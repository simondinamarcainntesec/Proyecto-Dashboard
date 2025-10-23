// charts/subtype.js
import data from "../data.js";
import { actions, getState } from "../state.js";
import { AXIS, GRID } from "../theme.js";

const PALETTE = [
  "#8B5CF6","#10B981","#F59E0B","#3B82F6","#EF4444",
  "#06B6D4","#F97316","#A855F7","#14B8A6","#EAB308",
  "#2563EB","#DC2626","#0EA5E9","#22C55E",
];
const withAlpha = (hex, a = "CC") => (hex || "#9CA3AF").slice(0,7) + a;
const DEFAULT_COLOR = "#9CA3AF";

const COLOR_BY_SUBTYPE = {
  system:"#8B5CF6", vpn:"#10B981", sdwan:"#3B82F6", "n/a":"#6B7280",
  dns:"#06B6D4", webfilter:"#F59E0B", "switch-controller":"#A855F7",
  router:"#22C55E", forward:"#F97316", ssl:"#2563EB", ips:"#EF4444",
};
const hashToIndex = (s, m) => {
  let h = 5381; for (let i=0;i<s.length;i++) h=((h<<5)+h)+s.charCodeAt(i);
  return Math.abs(h) % m;
};
const colorForSubtype = (name) => {
  const k = String(name ?? "").trim().toLowerCase();
  if (!k) return DEFAULT_COLOR;
  return COLOR_BY_SUBTYPE[k] || PALETTE[hashToIndex(k, PALETTE.length)] || DEFAULT_COLOR;
};

let chart;
let currentKeys = [];

const trunc = (s, n=14) => (String(s??"").length>n ? String(s).slice(0,n-1)+"…" : String(s));
const eqCI = (a,b) => String(a).trim().toLowerCase() === String(b).trim().toLowerCase();

export function renderSubtypeBar(ds, activeKey = "") {
  const canvas = document.getElementById("subtypeBar");
  if (!canvas) return;

  // Fallback si hay levelFilter y el dataset no viene cruzado por level
  const st = getState();
  let local = ds;
  const needLevel = !!st.levelFilter;
  const maybeLevelMap = data.subtypeByLevelRaw || data.subtypeCountsByLevel || null;

  if (needLevel && maybeLevelMap) {
    const dsSeemsLevel = Array.isArray(ds?.labels) && typeof ds?.data !== "undefined" && ds.labels.length > 0;
    if (!dsSeemsLevel) {
      const levKey = Object.keys(maybeLevelMap).find((k) => eqCI(k, st.levelFilter)) || st.levelFilter;
      const per = maybeLevelMap[levKey] || {};
      const labelsF = Object.keys(per);
      const dataF = labelsF.map((k) => Number(per[k] || 0));
      local = { labels: labelsF, data: dataF, keys: labelsF };
    }
  }

  const labels = Array.isArray(local?.labels) ? local.labels.map(String) : [];
  const values = labels.map((_, i) => Number((local?.data || [])[i] || 0));

  currentKeys =
    Array.isArray(local?.keys) && local.keys.length === labels.length
      ? local.keys.map(String)
      : labels.slice();

  const fill = currentKeys.map((k) => withAlpha(colorForSubtype(k)));
  const stroke = currentKeys.map((k) => colorForSubtype(k));
  const activeIdx = currentKeys.findIndex((k) => eqCI(k, activeKey));
  if (activeIdx >= 0) fill[activeIdx] = stroke[activeIdx];

  const cfg = {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Subtype",
        data: values,
        backgroundColor: fill,
        borderColor: "#e5e7eb",  // contorno blanco uniforme
        borderWidth: 2,
        hoverBorderColor: "#e5e7eb",
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 600, easing: "easeOutQuart" },
      indexAxis: "x",
      plugins: {
        legend: { display: false },   // igual que las otras barras
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
            padding: 6,
            font: { size: 12, weight: "700" },
            callback: function (_, i) {
              const lbs = this.chart?.data?.labels || labels;
              return trunc(lbs[i]);
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
      layout: { padding: { bottom: 6 } },
      categoryPercentage: 0.8,
      barPercentage: 0.9,
    },
  };

  if (!chart) {
    chart = new window.Chart(canvas, cfg);

    // click en barra → filtro por subtype
    canvas.addEventListener("click", (evt) => {
      if (!chart) return;
      const elp = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!elp?.length) return;
      const idx = elp[0].index;
      const key = currentKeys[idx];
      actions.toggleSubtype?.(key);
    });
  } else {
    chart.data.labels = cfg.data.labels;
    chart.data.datasets[0].data = cfg.data.datasets[0].data;
    chart.data.datasets[0].backgroundColor = cfg.data.datasets[0].backgroundColor;
    chart.data.datasets[0].borderColor = cfg.data.datasets[0].borderColor;
    chart.data.datasets[0].hoverBorderColor = cfg.data.datasets[0].hoverBorderColor;
    chart.options = cfg.options;
    chart.update();
  }
}
