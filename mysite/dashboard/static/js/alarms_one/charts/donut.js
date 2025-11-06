// charts/donut.js
import { safeLabel } from "../utils.js";
import { TXT, colorFor } from "../theme.js";
import { actions } from "../state.js";

let chart;

function norm(s) { return String(s ?? "").trim().toLowerCase(); }

export function renderDonut(state, counts) {
  const canvas = document.getElementById("severityDonut");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  const labels = Object.keys(counts || {});
  const values = labels.map((k) => Number(counts?.[k] || 0));

  // foco (atenuación)
  const active = state.severityFilter ? norm(state.severityFilter) : "";

  const backgroundColors = labels.map((k) =>
    active && norm(k) !== active ? "rgba(255,255,255,0.18)" : colorFor(k)
  );
  const borderColors = labels.map((k) =>
    active && norm(k) !== active ? "rgba(229,231,235,0.85)" : "#e5e7eb"
  );

  const titleText =
    state.severityFilter ? `Severidad: ${safeLabel(state.severityFilter)}`
    : state.actionFilter   ? `Acción: ${state.actionFilter}`
    : state.deviceFilter   ? `Dispositivo: ${state.deviceFilter}`
    : state.msgSeverityFilter ? `Msg severity: ${state.msgSeverityFilter}`
    : "Severidad";
  const titleColor = state.severityFilter ? colorFor(state.severityFilter) : TXT;

  if (!chart) {
    // Primera creación: dejamos la animación de entrada
    chart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: backgroundColors,
          borderColor: borderColors,
          borderWidth: 2,
          hoverOffset: 8,
        }],
      },
      options: {
        cutout: "62%",
        animation: { duration: 600, easing: "easeOutQuart" },
        plugins: {
          title: {
            display: true,
            text: titleText,
            color: titleColor,
            font: { size: 16, weight: "700" },
            padding: { top: 4, bottom: 8 },
          },
          legend: { display: false },
          tooltip: { enabled: true },
        },
      },
    });

    // Click → toggle de filtro (sin re-creación del gráfico)
    ctx.canvas.onclick = (evt) => {
      const els = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!els.length) return;
      const idx = els[0].index;
      const sev = labels[idx];
      actions.toggleSeverity?.(sev);
    };

    // Guardamos la geometría base para saber si cambió (labels/values)
    chart.$static = { labels: labels.slice(), values: values.slice() };
    return;
  }

  // --- Actualización SIN re-layout ---
  // Si labels/values NO cambiaron, sólo ajustamos colores y el título
  const sameLabels =
    Array.isArray(chart.$static?.labels) &&
    chart.$static.labels.length === labels.length &&
    chart.$static.labels.every((v, i) => v === labels[i]);

  const sameValues =
    Array.isArray(chart.$static?.values) &&
    chart.$static.values.length === values.length &&
    chart.$static.values.every((v, i) => Number(v) === Number(values[i]));

  if (sameLabels && sameValues) {
    // Sólo colores
    const ds = chart.data.datasets[0];
    ds.backgroundColor = backgroundColors;
    ds.borderColor = borderColors;

    // Título
    chart.options.plugins.title.text = titleText;
    chart.options.plugins.title.color = titleColor;

    // Actualiza SIN animación (no “recalcula” visualmente)
    chart.update("none");
  } else {
    // Cambió la geometría (poco frecuente) → actualizamos completo
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.data.datasets[0].backgroundColor = backgroundColors;
    chart.data.datasets[0].borderColor = borderColors;

    chart.options.plugins.title.text = titleText;
    chart.options.plugins.title.color = titleColor;

    chart.$static = { labels: labels.slice(), values: values.slice() };
    chart.update();
  }
}
