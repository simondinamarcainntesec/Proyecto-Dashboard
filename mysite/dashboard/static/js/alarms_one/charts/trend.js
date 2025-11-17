// charts/trend.js
import { TXT, AXIS, GRID } from "../theme.js";
import { actions } from "../state.js";

let chart;

// Formatea a "DD-MM" desde "YYYY-MM-DD" (u otros formatos comunes).
function fmtDDMM(label) {
  const s = String(label || "").trim();

  // ISO: 2025-11-03 -> 03-11
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
    return `${s.slice(8,10)}-${s.slice(5,7)}`;
  }

  // DD/MM/YYYY -> DD-MM
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(s)) {
    return `${s.slice(0,2)}-${s.slice(3,5)}`;
  }

  // DD-MM (ya correcto)
  if (/^\d{2}-\d{2}$/.test(s)) return s;

  // Fallback: intentar Date y formatear
  const d = new Date(s);
  if (!isNaN(d.getTime())) {
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    return `${dd}-${mm}`;
  }

  // Último recurso: dejar tal cual
  return s;
}

export function renderTrend(conf) {
  const ctx = document.getElementById("trendChart").getContext("2d");

  const opts = {
    animation: { duration: 600, easing: "easeOutQuart" },
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: {
        position: "top",
        labels: { color: TXT },
        onClick: (e, item) => {
          const sev = String(item.text).trim();
          actions.toggleSeverity(sev);
        },
      },
      tooltip: { enabled: true },
    },
    scales: {
      x: {
        ticks: {
          color: AXIS,
          autoSkip: false,        // ← mostrar TODOS los días
          minRotation: 55,        // ← diagonal
          maxRotation: 55,        // ← diagonal fija
          padding: 6,
          font: { size: 11 },
          callback: (value, index) => {
            const raw = conf?.labels?.[index];
            return fmtDDMM(raw);
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
  };

  if (!chart) {
    chart = new Chart(ctx, { type: "line", data: conf, options: opts });
  } else {
    chart.data = conf;
    chart.options = opts;
    chart.update();
  }
}
