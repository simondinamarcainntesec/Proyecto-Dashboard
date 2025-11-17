// charts/trend-hourly.js
import { AXIS, GRID } from "/static/js/soar/theme.js";
import { selectTrendByHourPayload } from "/static/js/soar/selectors.js";
import { actions, getState } from "/static/js/soar/state.js";
import { collectAlarmIdsForCurrentFilter, ensureHeaderButton, showAlarms } from "/static/js/soar/helpers/alarms-helper.js";

let chart;

export function renderTrendHourly(){
  const payload = selectTrendByHourPayload(true);
  const el = document.getElementById("chartTrendHourly"); if(!el) return;

  const ctx = el.getContext("2d");
  const labels = Array.isArray(payload.labels) ? payload.labels.slice() : [];
  const data   = Array.isArray(payload.data)   ? payload.data.slice()   : [];

  const st = getState();
  const hasHourFilter = st.hourFilter !== undefined && st.hourFilter !== null && String(st.hourFilter).trim() !== "";
  const activeHH = hasHourFilter ? String(st.hourFilter).padStart(2,"0").slice(0,2) : "";

  const baseColor   = "#A855F7";
  const activeColor = "#7C3AED";

  const bg = labels.map(l => {
    const hh = l.slice(0,2);
    if (!hasHourFilter) return baseColor;
    return (hh === activeHH) ? activeColor : "rgba(255,255,255,0.18)";
  });
  const border = labels.map(l => {
    const hh = l.slice(0,2);
    if (!hasHourFilter) return "#e5e7eb";
    return (hh === activeHH) ? "#e5e7eb" : "rgba(229,231,235,0.85)";
  });

  const conf = {
    type:"bar",
    data:{
      labels,
      datasets:[{
        label:"Alarmas por hora (rango actual)",
        data,
        backgroundColor:bg,
        borderColor:border,
        hoverBorderColor:border,
        borderWidth:2,
        hoverBorderWidth:2,
        borderSkipped:false,
        borderRadius:6,
      }]
    },
    options:{
      responsive:true,
      maintainAspectRatio:false,
      animation:{ duration:600, easing:"easeOutQuart" },
      plugins:{ legend:{ display:false }, tooltip:{ enabled:true } },
      elements:{ bar:{ borderSkipped:false } },
      datasets:{ bar:{ barThickness:"flex", categoryPercentage:0.8, barPercentage:0.7 } },
      scales:{
        x:{ type:"category", ticks:{ color:AXIS, autoSkip:false, maxRotation:0, minRotation:0 }, grid:{ color:GRID } },
        y:{ beginAtZero:true, ticks:{ color:AXIS }, grid:{ color:GRID } }
      },
      onClick:(evt)=>{
        const els = chart.getElementsAtEventForMode(evt,"nearest",{intersect:true},true);
        if (!els.length) return;
        const idx = els[0].index;
        const hh = labels[idx].slice(0,2);
        actions.toggleHour?.(hh);
      }
    }
  };

  if(!chart){
    chart = new Chart(ctx, conf);
    ctx.canvas.style.cursor = "pointer";

    ensureHeaderButton(ctx.canvas, "btn-see-alarms-hourly", () => {
      // Respetar TODOS los filtros; si hay hourFilter activo ya viene en state.
      const ids = collectAlarmIdsForCurrentFilter(); // sin extra → usa state (incluye hora)
      showAlarms(ids);
    });
  } else {
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.data.datasets[0].backgroundColor = bg;
    chart.data.datasets[0].borderColor = border;
    chart.data.datasets[0].hoverBorderColor = border;
    chart.update();
  }
}
