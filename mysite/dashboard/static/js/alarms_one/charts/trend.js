// charts/trend.js
import { TXT, AXIS, GRID } from "../theme.js";

let chart;

// Formatea a "DD-MM" desde "YYYY-MM-DD" (u otros formatos comunes).
function fmtDDMM(label) {
  const s = String(label || "").trim();

  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return `${s.slice(8, 10)}-${s.slice(5, 7)}`;
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(s)) return `${s.slice(0, 2)}-${s.slice(3, 5)}`;
  if (/^\d{2}-\d{2}$/.test(s)) return s;

  const d = new Date(s);
  if (!isNaN(d.getTime())) {
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    return `${dd}-${mm}`;
  }

  return s;
}

export function renderTrend(conf) {
  const canvas = document.getElementById("trendChart");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const labels = Array.isArray(conf?.labels) ? conf.labels.slice() : [];

  // Normaliza datasets para que TODOS queden con el look de referencia
  const datasetsIn = Array.isArray(conf?.datasets) ? conf.datasets : [];
  const datasets = datasetsIn.map((ds) => ({
    ...ds,
    tension: 0.25,
    fill: false,                 // sin relleno (como referencia)
    borderColor: "#60A5FA",
    backgroundColor: "#60A5FA",
    pointRadius: 3,
    pointHoverRadius: 5,
    borderWidth: 2,
  }));

  const dataConf = { labels, datasets };

  const opts = {
    responsive: true,
    maintainAspectRatio: false,

    // Animación consistente con la referencia
    animation: { duration: 600, easing: "easeOutQuart" },
    animations: {
      numbers: { type: "number", duration: 600, easing: "easeOutQuart" },
      tension: { duration: 600, easing: "easeOutQuart", from: 0.35, to: 0.25 },
    },

    interaction: { mode: "index", intersect: false },

    plugins: {
      legend: {
        position: "top",
        labels: { color: TXT },
        onClick: () => {}, // no filtra/ni hace toggle al click (como referencia)
      },
      tooltip: { enabled: true },
    },

    scales: {
      x: {
        type: "category",
        ticks: {
          color: AXIS,
          autoSkip: false,   // muestra todos los días
          minRotation: 55,   // diagonal fija
          maxRotation: 55,
          padding: 6,
          font: { size: 11 },
          callback: (value, index) => fmtDDMM(labels[index]),
        },
        grid: { color: GRID },
      },
      y: {
        beginAtZero: true,
        ticks: { color: AXIS },
        grid: { color: GRID },
      },
    },

    // solo eventos “vista” (sin click)
    events: ["mousemove", "mouseout", "touchstart", "touchmove", "touchend"],
  };

  if (!chart) {
    chart = new Chart(ctx, { type: "line", data: dataConf, options: opts });
  } else {
    chart.data = dataConf;
    chart.options = opts;
    chart.update();
  }

  // Cursor normal (no clickeable)
  canvas.style.cursor = "default";
  canvas.onclick = null;
}
