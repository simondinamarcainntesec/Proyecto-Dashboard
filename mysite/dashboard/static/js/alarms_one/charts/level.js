// charts/level.js
import { getState, onStateChange, actions } from "../state.js";
import { levelDataForCurrentFilter } from "../selectors.js";
import { AXIS, GRID } from "../theme.js";

let chart;
let currentKeys = []; // clave real por índice visual

export function mountLevelBar(canvasId = "levelBar") {
  const canvas = document.getElementById(canvasId);
  if (!canvas) {
    console.warn(`[Level] No se encontró canvas #${canvasId}`);
    return () => {};
  }
  const ctx = canvas.getContext("2d");

  // Config base
  const opts = {
    responsive: true,
    animation: { duration: 500, easing: "easeOutQuart" },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          // Asegura que el título del tooltip coincida con la etiqueta visible
          title(items) {
            return items.map(i => (chart?.data?.labels?.[i.dataIndex] ?? ""));
          },
          label(ctx) {
            const val = ctx.parsed.y ?? ctx.parsed; // barra vertical
            // Muestra "Level: X" o "Cantidad: X" según prefieras
            return `Cantidad: ${val}`;
          }
        }
      }
    },
    scales: {
      x: {
        ticks: { color: AXIS },
        grid: { color: GRID }
      },
      y: {
        beginAtZero: true,
        ticks: { color: AXIS },
        grid: { color: GRID }
      }
    },
    onClick(evt, _elements, _chart) {
      // Busca el elemento exacto clickeado
      const points = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!points || !points.length) return;
      const idx = points[0].index;
      const key = currentKeys[idx];    // clave real (no la etiqueta formateada)
      if (!key) return;

      actions.toggleLevel(key);        // ← aplica el filtro de Level
    }
  };

  // Crea el chart vacío
  chart = new Chart(ctx, {
    type: "bar",
    data: { labels: [], datasets: [{ label: "Level", data: [], backgroundColor: "#A855F7" }] },
    options: opts,
  });

  // Función de render (se llama al inicio y en cada cambio de estado)
  const render = () => {
    const st = getState();
    const { labels, data, keys } = levelDataForCurrentFilter(st);

    currentKeys = Array.isArray(keys) ? keys.slice() : labels.slice(); // respaldo de claves exactas
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.update();
  };

  // Render inicial + suscripción reactiva
  render();
  const off = onStateChange(render);

  // Devuelve cleanup
  return () => {
    off && off();
    if (chart) { chart.destroy(); chart = null; }
  };
}
