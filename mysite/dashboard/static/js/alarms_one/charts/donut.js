// charts/donut.js
import { safeLabel } from "../utils.js";
import { TXT, colorFor } from "../theme.js";
import { actions } from "../state.js";

let chart;

export function renderDonut(state, counts) {
  const ctx = document.getElementById("severityDonut").getContext("2d");
  const labels = Object.keys(counts);
  const values = labels.map((k) => Number(counts[k] || 0));
  const colors = labels.map((k) =>
    !state.severityFilter || String(k).toLowerCase() === String(state.severityFilter).toLowerCase()
      ? colorFor(k)
      : "rgba(255,255,255,0.18)"
  );

  const titleText =
    state.severityFilter ? `Severidad: ${safeLabel(state.severityFilter)}`
    : state.actionFilter   ? `Acción: ${state.actionFilter}`
    : state.deviceFilter   ? `Dispositivo: ${state.deviceFilter}`
    : state.msgSeverityFilter ? `Msg severity: ${state.msgSeverityFilter}`
    : "Severidad";

  const titleColor = state.severityFilter ? colorFor(state.severityFilter) : TXT;

  const conf = {
    type: "doughnut",
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderColor: "#e5e7eb", borderWidth: 2, hoverOffset: 8 }] },
    options: {
      cutout: "62%",
      animation: { duration: 600, easing: "easeOutQuart" },
      plugins: {
        title: { display: true, text: titleText, color: titleColor, font: { size: 16, weight: "700" }, padding: { top: 4, bottom: 8 } },
        legend: { display: false },
        tooltip: { enabled: true },
      },
    },
  };

  if (!chart) {
    chart = new Chart(ctx, conf);
    ctx.canvas.onclick = (evt) => {
      const el = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!el.length) return;
      const idx = el[0].index;
      const sev = labels[idx];
      actions.toggleSeverity(sev);
    };
  } else {
    chart.data = conf.data;
    chart.options = conf.options;
    chart.update();
  }
}
