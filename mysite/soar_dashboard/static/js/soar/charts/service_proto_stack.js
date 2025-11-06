import { AXIS, GRID } from "/static/js/soar/theme.js";
import { selectServiceProtoStackPayload } from "/static/js/soar/selectors.js";

let chart;
export function renderServiceProtoStack(){
  const payload = selectServiceProtoStackPayload(8); // top 8 servicios
  const el = document.getElementById("chartServiceProto"); if(!el) return;
  const ctx = el.getContext("2d");

  const labels = payload.labels || [];
  const datasets = (payload.datasets || []).map((ds, i) => ({
    ...ds,
    borderWidth: 1.5,
    borderColor: "#e5e7eb",
    backgroundColor: [
      "#60A5FA","#8B5CF6","#10B981","#F59E0B",
      "#06B6D4","#F97316","#22C55E","#A855F7",
      "#EAB308","#2563EB"
    ][i % 10],
  }));

  const conf = {
    type: "bar",
    data: { labels, datasets },
    options: {
      animation:{ duration:600, easing:"easeOutQuart" },
      plugins:{ legend:{ display:true } },
      responsive:true,
      scales: {
        x: { stacked:true, ticks:{ color:AXIS, callback:(_v,i)=>labels[i]??_v }, grid:{ color:GRID }},
        y: { stacked:true, beginAtZero:true, ticks:{ color:AXIS }, grid:{ color:GRID }},
      },
    }
  };

  if(!chart){ chart = new Chart(ctx, conf); }
  else {
    chart.data.labels = labels;
    chart.data.datasets = datasets;
    chart.update("none");
  }
}
