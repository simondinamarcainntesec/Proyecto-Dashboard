// charts/severity.js — Donut con borde blanco constante + self-ignore
import { TXT, colorFor } from "/static/js/soar/theme.js";
import { actions, getState } from "/static/js/soar/state.js";
import { selectSeverityCounts } from "/static/js/soar/selectors.js";

let chart;
const norm = (s) => String(s ?? "").trim().toLowerCase();

export function renderSeverity(){
  // selfIgnore=true → ignora severityFilter al calcularse (la dona se mantiene completa)
  const counts = selectSeverityCounts(true);
  const el = document.getElementById("chartSeverity");
  if (!el) return;
  const ctx = el.getContext("2d");

  const labels = Object.keys(counts);
  const values = labels.map(k => Number(counts[k] || 0));
  const active = norm(getState().severityFilter || "");

  const backgroundColors = labels.map(k =>
    active && norm(k) !== active ? "rgba(255,255,255,0.18)" : colorFor(k)
  );

  const titleText = active ? `Severidad: ${active}` : "Severidad";
  const titleColor = active ? colorFor(active) : TXT;

  const conf = {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: backgroundColors,
        // ✅ contorno blanco constante
        borderColor: "#e5e7eb",
        hoverBorderColor: "#e5e7eb",
        borderWidth: 2,
        hoverBorderWidth: 2,
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
  };

  if (!chart){
    chart = new Chart(ctx, conf);
    ctx.canvas.onclick = (evt) => {
      const els = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!els.length) return;
      const idx = els[0].index;
      actions.toggleSeverity(labels[idx]); // esto limpia país/acción por la lógica del state
    };
    chart.$static = { labels: labels.slice(), values: values.slice() };
    return;
  }

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
    // borde blanco constante (no cambia)
    chart.options.plugins.title.text = titleText;
    chart.options.plugins.title.color = titleColor;
    chart.update("none");
  } else {
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.data.datasets[0].backgroundColor = backgroundColors;
    chart.options.plugins.title.text = titleText;
    chart.options.plugins.title.color = titleColor;
    chart.$static = { labels: labels.slice(), values: values.slice() };
    chart.update();
  }
}
