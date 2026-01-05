// charts/msgSeverity.js
import { colorForMsgSeverity } from "../theme.js";
import { actions, getState } from "../state.js";

let chart;

function norm(s){ return String(s ?? "").trim().toLowerCase(); }

/* =========================
 * "Nice ticks" enteros
 * ========================= */
function niceStep(maxValue, targetTicks = 7) {
  const max = Math.max(0, Number(maxValue) || 0);
  if (max <= 10) return 1;

  const raw = max / targetTicks;
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const normv = raw / pow;

  let mult;
  if (normv <= 1) mult = 1;
  else if (normv <= 2) mult = 2;
  else if (normv <= 5) mult = 5;
  else mult = 10;

  return Math.max(1, Math.round(mult * pow));
}
function ceilToStep(v, step) {
  const n = Math.max(0, Number(v) || 0);
  const s = Math.max(1, Number(step) || 1);
  return Math.ceil(n / s) * s;
}

export function renderMsgSeverityBar(payload, activeKey) {
  const el = document.getElementById("msgSeverityBar");
  if (!el) return;
  const ctx = el.getContext("2d");

  const { labels = [], data = [], keys = [] } = payload;

  // Foco actual (si corresponde)
  const focus = (activeKey ?? getState()?.msgSeverityFilter ?? "").toString();

  // Colores (atenúa lo que no es foco)
  const bg = labels.map((lbl) =>
    focus && norm(lbl) !== norm(focus) ? "rgba(255,255,255,0.18)" : colorForMsgSeverity(lbl)
  );
  const borders = labels.map((lbl) =>
    focus && norm(lbl) !== norm(focus) ? "rgba(229,231,235,0.85)" : "#e5e7eb"
  );

  // step/ticks enteros
  const maxVal = Math.max(0, ...(data || []).map((v) => Number(v || 0)));
  const step = niceStep(maxVal, 7);
  const suggestedMax = ceilToStep(maxVal, step);

  if (!chart) {
    // Creación inicial
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
        plugins: {
          legend: { display: false },
          tooltip: {
            enabled: true,
            callbacks: {
              label: (item) => `Cantidad: ${Math.round(item.parsed?.x ?? item.raw ?? 0)}`,
            },
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            suggestedMax,
            ticks: {
              color: "#E5E7EB",
              stepSize: step,
              precision: 0,
              callback: (v) => String(Math.round(v)),
            },
            grid: { color: "rgba(229,231,235,0.14)" },
          },
          y: {
            type: "category",
            ticks: {
              color: "#E5E7EB",
              callback: (_, i) => (chart?.data?.labels?.[i] ?? ""),
            },
            grid: { color: "rgba(229,231,235,0.14)" },
          },
        },
      },
    });

    // Click → toggle del filtro con la key cruda
    ctx.canvas.onclick = (evt) => {
      const elp = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!elp.length) return;
      const idx = elp[0].index;
      actions.toggleMsgSeverity?.(keys[idx]);
    };

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
    // Solo cambia foco → actualiza colores
    const ds = chart.data.datasets[0];
    ds.backgroundColor = bg;
    ds.borderColor = borders;
    ds.hoverBorderColor = borders;

    // actualizar suggestedMax/step si hiciera falta (por seguridad)
    chart.options.scales.x.suggestedMax = suggestedMax;
    chart.options.scales.x.ticks.stepSize = step;

    chart.update("none");
  } else {
    // Actualización completa
    chart.data.labels = labels.slice();
    chart.data.datasets[0].data = data.slice();
    chart.data.datasets[0].backgroundColor = bg;
    chart.data.datasets[0].borderColor = borders;
    chart.data.datasets[0].hoverBorderColor = borders;

    chart.options.scales.x.suggestedMax = suggestedMax;
    chart.options.scales.x.ticks.stepSize = step;

    chart.$static = { labels: labels.slice(), values: data.slice() };
    chart.update();
  }
}
