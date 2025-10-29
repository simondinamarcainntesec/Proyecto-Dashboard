import { AXIS, GRID } from "/static/js/soar/theme.js";
import { selectTrendByHourPayload } from "/static/js/soar/selectors.js";

let chart;
export function renderTrendHourly(){
  const payload = selectTrendByHourPayload();
  const el = document.getElementById("chartTrendHourly"); if(!el) return;
  const ctx = el.getContext("2d");
  const labels = payload.labels||[], data = payload.data||[];

  const conf = {
    type:"line",
    data:{ labels, datasets:[{ label:"Alarmas", data, tension:0.25, fill:false, borderColor:"#A855F7", backgroundColor:"#A855F7", pointRadius:3, pointHoverRadius:5, borderWidth:2 }]},
    options:{ animation:{ duration:600, easing:"easeOutQuart" }, plugins:{ legend:{ display:false } },
      scales:{ x:{ ticks:{ color:AXIS }, grid:{ color:GRID } }, y:{ beginAtZero:true, ticks:{ color:AXIS }, grid:{ color:GRID } } }
    }
  };

  if(!chart) chart = new Chart(ctx, conf);
  else { chart.data.labels = labels; chart.data.datasets[0].data = data; chart.update("none"); }
}
