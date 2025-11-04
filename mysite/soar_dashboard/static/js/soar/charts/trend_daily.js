// static/js/soar/charts/trend_daily.js
import { TXT, AXIS, GRID } from "/static/js/soar/theme.js";
import { selectTrendByDatePayload } from "/static/js/soar/selectors.js";

let chart;

export function renderTrendDaily() {
  // Respeta filtros externos; el propio gráfico NO filtra al click
  const payload = selectTrendByDatePayload();
  const el = document.getElementById("chartTrendDaily");
  if (!el) return;

  const ctx = el.getContext("2d");
  const labels = Array.isArray(payload.labels) ? payload.labels.slice() : [];
  const data   = Array.isArray(payload.data)   ? payload.data.slice()   : [];

  const dataConf = {
    labels,
    datasets: [
      {
        label: "Alarmas",
        data,
        tension: 0.25,              // curva suave
        fill: false,
        borderColor: "#60A5FA",
        backgroundColor: "#60A5FA",
        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2,
      },
    ],
  };

  const opts = {
    responsive: true,
    maintainAspectRatio: false,

    // 🎞️ Animaciones visibles (mismo “feeling”)
    animation: { duration: 600, easing: "easeOutQuart" },
    animations: {
      // anima cualquier número que cambie (y-values, etc.)
      numbers: {
        type: "number",
        duration: 600,
        easing: "easeOutQuart",
      },
      // anima la tensión de la línea para que se perciba el “transition”
      tension: {
        duration: 600,
        easing: "easeOutQuart",
        from: 0.35, // parte un poco más curvada
        to:   0.25, // vuelve a la tensión final
      },
    },

    // 🧭 Interacción tipo trend.js
    interaction: { mode: "index", intersect: false },

    // 🏷️ Leyenda arriba con color de texto consistente
    plugins: {
      legend: {
        position: "top",
        labels: { color: TXT },
        // 🚫 Mantener gráfico estático: la leyenda no hace toggle ni filtra
        onClick: () => {},
      },
      tooltip: { enabled: true },
    },

    // 📈 Ejes con paleta del tema
    scales: {
      x: { type: "category", ticks: { color: AXIS }, grid: { color: GRID } },
      y: { beginAtZero: true, ticks: { color: AXIS }, grid: { color: GRID } },
    },

    // 🔒 Sin manejo de click en el canvas
    events: ["mousemove", "mouseout", "touchstart", "touchmove", "touchend"],
  };

  if (!chart) {
    chart = new Chart(ctx, { type: "line", data: dataConf, options: opts });
  } else {
    chart.data = dataConf;
    chart.options = opts;
    chart.update(); // 👈 fuerza animación en cada actualización
  }

  // Cursor normal (no “manito”) para reforzar que no es clickeable
  ctx.canvas.style.cursor = "default";
  // Asegura que no haya quedado algún handler viejo
  ctx.canvas.onclick = null;
}
