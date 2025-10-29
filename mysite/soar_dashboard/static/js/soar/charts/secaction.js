// static/js/soar/charts/secaction.js
// Barra con borde blanco constante + self-ignore + misma animación suave

import { AXIS, GRID } from "/static/js/soar/theme.js";
import { actions, getState } from "/static/js/soar/state.js";
import { selectSecActionPayload } from "/static/js/soar/selectors.js";

let chart;
const norm = (s) => String(s ?? "").trim().toLowerCase();

export function renderSecAction() {
  // selfIgnore=true → ignora actionFilter al calcularse (el gráfico permanece estable)
  const payload = selectSecActionPayload(true);
  const el = document.getElementById("chartSecAction");
  if (!el) return;
  const ctx = el.getContext("2d");

  const labels = (payload.labels || []).slice();
  const values = (payload.data || []).slice();
  const active = norm(getState().actionFilter || "");

  const backgroundColors = labels.map((lbl) =>
    active && norm(lbl) !== active ? "rgba(255,255,255,0.18)" : "#8B5CF6"
  );

  const conf = {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Eventos",
          data: values,
          backgroundColor: backgroundColors,

          // ✅ contorno blanco constante en todas las barras
          borderColor: "#e5e7eb",
          hoverBorderColor: "#e5e7eb",
          borderWidth: 2,
          hoverBorderWidth: 2,
          borderSkipped: false, // borde en los 4 lados

          // estética y “feel”
          borderRadius: 6,
          barThickness: "flex",
          categoryPercentage: 0.8,
          barPercentage: 0.7,
        },
      ],
    },
    options: {
      animation: { duration: 600, easing: "easeOutQuart" }, // misma animación que la donut
      plugins: {
        legend: { display: false },
        tooltip: { intersect: false },
      },
      elements: {
        bar: {
          borderSkipped: false, // refuerzo global
        },
      },
      scales: {
        y: { beginAtZero: true, ticks: { color: AXIS }, grid: { color: GRID } },
        x: {
          type: "category",
          ticks: {
            color: AXIS,
            callback: (_v, i) => labels[i] ?? _v, // evita 0..n y muestra el texto real
          },
          grid: { color: GRID },
        },
      },
    },
  };

  if (!chart) {
    chart = new Chart(ctx, conf);

    // Click → toggle del filtro (y limpia los otros por la lógica de state)
    ctx.canvas.onclick = (evt) => {
      const els = chart.getElementsAtEventForMode(
        evt,
        "nearest",
        { intersect: true },
        true
      );
      if (!els.length) return;
      const idx = els[0].index;
      actions.toggleAction?.(labels[idx]);
    };

    // guardar geometría para updates más suaves
    chart.$static = { labels: labels.slice(), values: values.slice() };
    return;
  }

  // === actualización sin re-layout si no cambian labels/values ===
  const sameLabels =
    Array.isArray(chart.$static?.labels) &&
    chart.$static.labels.length === labels.length &&
    chart.$static.labels.every((v, i) => v === labels[i]);

  const sameValues =
    Array.isArray(chart.$static?.values) &&
    chart.$static.values.length === values.length &&
    chart.$static.values.every((v, i) => Number(v) === Number(values[i]));

  if (sameLabels && sameValues) {
    const ds = chart.data.datasets[0];
    ds.backgroundColor = backgroundColors;
    ds.data = values;
    // borde blanco constante ya seteado
    chart.options.scales.x.ticks.callback = (_v, i) => labels[i] ?? _v;
    chart.update("none");
  } else {
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.data.datasets[0].backgroundColor = backgroundColors;
    chart.options.scales.x.ticks.callback = (_v, i) => labels[i] ?? _v;
    chart.$static = { labels: labels.slice(), values: values.slice() };
    chart.update();
  }
}
