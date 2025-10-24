// charts/msgSeverity.js
import { colorForMsgSeverity } from "../theme.js";
import { actions, getState } from "../state.js";

let chart;

function norm(s){ return String(s ?? "").trim().toLowerCase(); }

export function renderMsgSeverityBar(payload, activeKey) {
  const el = document.getElementById("msgSeverityBar");
  if (!el) return;
  const ctx = el.getContext("2d");

  const { labels = [], data = [], keys = [] } = payload;

  // Si no viene activeKey, usamos el filtro actual del state
  const focus = (activeKey ?? getState()?.msgSeverityFilter ?? "").toString();

  // Colores (atenúa todo lo que no sea el foco)
  const bg = labels.map((lbl) =>
    focus && norm(lbl) !== norm(focus) ? "rgba(255,255,255,0.18)" : colorForMsgSeverity(lbl)
  );
  const borders = labels.map((lbl) =>
    focus && norm(lbl) !== norm(focus) ? "rgba(229,231,235,0.85)" : "#e5e7eb"
  );

  if (!chart) {
    // Creación inicial (animamos solo la primera vez)
    chart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels.slice(),
        datasets: [{
          label: "Severity Alarm",
          data: data.slice(),
          borderWidth: 2,
          backgroundColor: bg,
          borderColor: borders,
          hoverBorderColor: borders,
        }],
      },
      options: {
        indexAxis: "y",
        animation: { duration: 600, easing: "easeOutQuart" },
        plugins: { legend: { display: false }, tooltip: { enabled: true } },
        scales: {
          x: { beginAtZero: true, ticks: { color: "#E5E7EB" }, grid: { color: "rgba(229,231,235,0.14)" } },
          y: {
            type: "category",
            ticks: {
              color: "#E5E7EB",
              callback: (_, i) => labels[i],
            },
            grid: { color: "rgba(229,231,235,0.14)" },
          },
        },
      },
    });

    // Click → toggle del filtro (usamos la clave cruda del payload)
    ctx.canvas.onclick = (evt) => {
      const elp = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!elp.length) return;
      const idx = elp[0].index;
      actions.toggleMsgSeverity?.(keys[idx]);
    };

    // Guardamos geometría para detectar cambios reales
    chart.$static = { labels: labels.slice(), values: data.slice() };
    return;
  }

  // ¿Cambió la geometría?
  const sameLabels =
    Array.isArray(chart.$static?.labels) &&
    chart.$static.labels.length === labels.length &&
    chart.$static.labels.every((v, i) => v === labels[i]);

  const sameValues =
    Array.isArray(chart.$static?.values) &&
    chart.$static.values.length === data.length &&
    chart.$static.values.every((v, i) => Number(v) === Number(data[i]));

  if (sameLabels && sameValues) {
    // Sólo cambia el foco → actualizamos colores sin animación
    const ds = chart.data.datasets[0];
    ds.backgroundColor = bg;
    ds.borderColor = borders;
    ds.hoverBorderColor = borders;
    chart.update("none");
  } else {
    // Cambió labels/data → actualizamos todo (con animación normal)
    chart.data.labels = labels.slice();
    chart.data.datasets[0].data = data.slice();
    chart.data.datasets[0].backgroundColor = bg;
    chart.data.datasets[0].borderColor = borders;
    chart.data.datasets[0].hoverBorderColor = borders;

    chart.$static = { labels: labels.slice(), values: data.slice() };
    chart.update();
  }
}
