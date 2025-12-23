// charts/top-ips.js
import { AXIS, GRID } from "/static/js/soar/theme.js";
import { actions, getState } from "/static/js/soar/state.js";
import { selectTopIPsPayload } from "/static/js/soar/selectors.js";
import { collectAlarmIdsForCurrentFilter, ensureHeaderButton, showAlarms } from "/static/js/soar/helpers/alarms-helper.js";

let chartSrc, chartDst;
const norm = (s) => String(s ?? "").trim().toLowerCase();

function buildConf(rawLabels, data, title, activeKey, onCanvasClick) {
  const labels = (rawLabels || []).map(String);
  const base = "#22C55E";
  const bg = labels.map(lbl => !activeKey ? base : (lbl.toLowerCase() === activeKey ? base : "rgba(255,255,255,0.18)"));
  const border = labels.map(lbl => !activeKey ? "#e5e7eb" : (lbl.toLowerCase() === activeKey ? "#e5e7eb" : "rgba(229,231,235,0.85)"));

  return {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Eventos",
        data,
        backgroundColor: bg,
        borderColor: border,
        hoverBorderColor: border,
        borderWidth: 2,
        hoverBorderWidth: 2,
        borderSkipped: false,
        borderRadius: 6,
      }]
    },
    options: {
      indexAxis: "y",                       // barras horizontales
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 600, easing: "easeOutQuart" },
      plugins: { legend: { display: false }, tooltip: { enabled: true } },
      elements: { bar: { borderSkipped: false } },
      scales: {
        x: { beginAtZero: true, ticks: { color: AXIS }, grid: { color: GRID } },
        y: {
          type: "category",
          ticks: {
            color: AXIS,
            autoSkip: false,
            maxRotation: 0,
            minRotation: 0,
            callback: (val, i) => labels[i] ?? val
          },
          grid: { color: GRID }
        },
      },
      datasets: { bar: { barThickness: "flex", categoryPercentage: 0.8, barPercentage: 0.7 } },
      onClick: onCanvasClick,
    },
  };
}

export function renderTopSrcIP(){
  const payload = selectTopIPsPayload("src", 6, true);
  const el = document.getElementById("chartTopSrcIP"); if (!el) return;
  const ctx = el.getContext("2d");

  const labels = payload.labels || [];
  const data   = payload.data   || [];
  const active = norm(getState().srcIPFilter || "");

  const conf = buildConf(labels, data, "Top IP Origen", active, (evt) => {
    const pts = chartSrc.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
    if (!pts.length) return;
    const idx = pts[0].index;
    actions.toggleSrcIP?.(labels[idx]);
  });

  if (!chartSrc) {
    chartSrc = new Chart(ctx, conf);
    ctx.canvas.style.cursor = "pointer";

    ensureHeaderButton(ctx.canvas, "btn-see-alarms-srcip", () => {
      const act = norm(getState().srcIPFilter || "");
      const ids = collectAlarmIdsForCurrentFilter(act ? (r) => norm(r?.srcip) === act : undefined);
      showAlarms(ids);
    });
  } else {
    chartSrc.data.labels = conf.data.labels;
    chartSrc.data.datasets[0].data = conf.data.datasets[0].data;
    chartSrc.data.datasets[0].backgroundColor = conf.data.datasets[0].backgroundColor;
    chartSrc.data.datasets[0].borderColor = conf.data.datasets[0].borderColor;
    chartSrc.update();
  }
}

export function renderTopDstIP(){
  const payload = selectTopIPsPayload("dst", 6, true);
  const el = document.getElementById("chartTopDstIP"); if (!el) return;
  const ctx = el.getContext("2d");

  const labels = payload.labels || [];
  const data   = payload.data   || [];
  const active = norm(getState().dstIPFilter || "");

  const conf = buildConf(labels, data, "Top IP Destino", active, (evt) => {
    const pts = chartDst.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
    if (!pts.length) return;
    const idx = pts[0].index;
    actions.toggleDstIP?.(labels[idx]);
  });

  if (!chartDst) {
    chartDst = new Chart(ctx, conf);
    ctx.canvas.style.cursor = "pointer";

    ensureHeaderButton(ctx.canvas, "btn-see-alarms-dstip", () => {
      const act = norm(getState().dstIPFilter || "");
      const ids = collectAlarmIdsForCurrentFilter(act ? (r) => norm(r?.dstip) === act : undefined);
      showAlarms(ids);
    });
  } else {
    chartDst.data.labels = conf.data.labels;
    chartDst.data.datasets[0].data = conf.data.datasets[0].data;
    chartDst.data.datasets[0].backgroundColor = conf.data.datasets[0].backgroundColor;
    chartDst.data.datasets[0].borderColor = conf.data.datasets[0].borderColor;
    chartDst.update();
  }
}

// wrapper
export function renderTopIPs() { renderTopSrcIP(); renderTopDstIP(); }
