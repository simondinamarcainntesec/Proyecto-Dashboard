import { AXIS, GRID } from "/static/js/soar/theme.js";
import { actions, getState } from "/static/js/soar/state.js";
import { selectTopApplicationsPayload } from "/static/js/soar/selectors.js";

let chart;

export function renderApplications(){
  const payload = selectTopApplicationsPayload(10, true);
  const el = document.getElementById("chartApplications"); if(!el) return;
  const ctx = el.getContext("2d");

  const labels = (payload.labels || []).map(String);
  const data   = payload.data || [];
  const active = (getState().applicationFilter || "").toLowerCase();

  const base = "#06B6D4";
  const bg = labels.map(lbl =>
    !active ? base : (lbl.toLowerCase() === active ? base : "rgba(255,255,255,0.18)")
  );
  const border = labels.map(lbl =>
    !active ? "#e5e7eb" : (lbl.toLowerCase() === active ? "#e5e7eb" : "rgba(229,231,235,0.85)")
  );

  const conf = {
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
      animation: { duration: 600, easing: "easeOutQuart" }, // ← como acciones
      plugins: { legend: { display: false } },
      elements: { bar: { borderSkipped: false } },
      scales: {
        x: {
          type: "category",
          ticks: { color: AXIS, autoSkip: false, maxRotation: 0, minRotation: 0, callback: (v, i) => labels[i] ?? v },
          grid: { color: GRID },
        },
        y: { beginAtZero: true, ticks: { color: AXIS }, grid: { color: GRID } },
      },
      datasets: {
        bar: { barThickness: "flex", categoryPercentage: 0.8, barPercentage: 0.7 }, // ← como acciones
      },
    }
  };

  if(!chart){
    chart = new Chart(ctx, conf);
    ctx.canvas.onclick=(evt)=>{
      const els = chart.getElementsAtEventForMode(evt,"nearest",{intersect:true},true);
      if(!els.length) return;
      const idx = els[0].index;
      actions.toggleApplication?.(labels[idx]);
    };
    ctx.canvas.style.cursor = "pointer";
  } else {
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.data.datasets[0].backgroundColor = bg;
    chart.data.datasets[0].borderColor = border;
    chart.update(); // ← anima como acciones
  }
}
