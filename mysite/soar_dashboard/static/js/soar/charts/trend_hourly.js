import { AXIS, GRID } from "/static/js/soar/theme.js";
import { selectTrendByHourPayload } from "/static/js/soar/selectors.js";
import { actions, getState } from "/static/js/soar/state.js";

let chart;

export function renderTrendHourly(){
  // Mantener todas las barras visibles aunque haya filtro de hora
  const payload = selectTrendByHourPayload(true);
  const el = document.getElementById("chartTrendHourly"); if(!el) return;

  const ctx = el.getContext("2d");
  const labels = Array.isArray(payload.labels) ? payload.labels.slice() : [];
  const data   = Array.isArray(payload.data)   ? payload.data.slice()   : [];

  const st = getState();
  // ✅ solo definir activeHH si REALMENTE hay filtro
  const hasHourFilter = st.hourFilter !== undefined && st.hourFilter !== null && String(st.hourFilter).trim() !== "";
  const activeHH = hasHourFilter ? String(st.hourFilter).padStart(2, "0").slice(0, 2) : "";

  const baseColor   = "#A855F7";  // púrpura base
  const activeColor = "#7C3AED";  // púrpura más intenso para la barra activa

  // Sin filtro: todo sólido. Con filtro: activa sólida y resto atenuadas.
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
      // 🔁 misma animación que Acciones
      animation:{ duration:600, easing:"easeOutQuart" },
      plugins:{ legend:{ display:false }, tooltip:{ enabled:true } },
      elements:{ bar:{ borderSkipped:false } },
      // 🔁 mismo “grosor/espaciado” que Acciones
      datasets:{ bar:{ barThickness:"flex", categoryPercentage:0.8, barPercentage:0.7 } },
      scales:{
        x:{ type:"category", ticks:{ color:AXIS, autoSkip:false, maxRotation:0, minRotation:0 }, grid:{ color:GRID } },
        y:{ beginAtZero:true, ticks:{ color:AXIS }, grid:{ color:GRID } }
      },
      onClick:(evt)=>{
        const els = chart.getElementsAtEventForMode(evt,"nearest",{intersect:true},true);
        if (!els.length) return;
        const idx = els[0].index;
        const hh = labels[idx].slice(0,2); // "HH:00" -> "HH"
        actions.toggleHour?.(hh); // tu toggle limpia si se repite
      }
    }
  };

  if(!chart){
    chart = new Chart(ctx, conf);
    ctx.canvas.style.cursor = "pointer";
  } else {
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.data.datasets[0].backgroundColor = bg;
    chart.data.datasets[0].borderColor = border;
    chart.data.datasets[0].hoverBorderColor = border;
    chart.update(); // 👈 anima (no "none")
  }
}
