// charts/msgSeverity.js
import { colorForMsgSeverity } from "../theme.js";
import { actions } from "../state.js";

let chart;

export function renderMsgSeverityBar(payload, activeKey) {
  const el = document.getElementById("msgSeverityBar");
  if (!el) return;
  const ctx = el.getContext("2d");
  const { labels, data, keys } = payload;

  const backgroundColors = labels.map((label) => {
    if (activeKey && label !== activeKey) return "rgba(255,255,255,0.18)";
    return colorForMsgSeverity(label);
  });

  const conf = {
    type: "bar",
    data: { labels, datasets: [{ label: "Severity Alarm", data, borderWidth: 2, backgroundColor: backgroundColors, borderColor: "#e5e7eb" }] },
    options: {
      indexAxis: "y",
      animation: { duration: 600, easing: "easeOutQuart" },
      plugins: { legend: { display: false }, tooltip: { enabled: true } },
      scales: {
        x: { beginAtZero: true, ticks: { color: "#E5E7EB" }, grid: { color: "rgba(229,231,235,0.14)" } },
        y: { type: "category", ticks: { color: "#E5E7EB", callback: (v, i) => labels[i] }, grid: { color: "rgba(229,231,235,0.14)" } },
      },
    },
  };

  if (!chart) {
    chart = new Chart(ctx, conf);
    ctx.canvas.onclick = (evt) => {
      const elp = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!elp.length) return;
      const idx = elp[0].index;
      actions.toggleMsgSeverity(keys[idx]);
    };
  } else {
    chart.data = conf.data;
    chart.options = conf.options;
    chart.update();
  }
}