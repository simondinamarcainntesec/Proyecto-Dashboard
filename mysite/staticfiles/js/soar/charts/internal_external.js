import { TXT } from "/static/js/soar/theme.js";
import { selectInternalExternalPayload } from "/static/js/soar/selectors.js";

let chart;
export function renderInternalExternal(){
  const payload = selectInternalExternalPayload();
  const el = document.getElementById("chartInternalExternal"); if(!el) return;
  const ctx = el.getContext("2d");

  const labels = payload.labels||[];
  const values = payload.data||[];

  const conf = {
    type: "doughnut",
    data: { labels, datasets: [{ data: values,
      backgroundColor: ["#0EA5E9", "#DC2626"],
      borderColor:"#e5e7eb", hoverBorderColor:"#e5e7eb", borderWidth:2, hoverBorderWidth:2, hoverOffset:8 }] },
    options: {
      cutout:"62%", animation:{ duration:600, easing:"easeOutQuart" },
      plugins:{ title:{ display:true, text:"Internas vs Externas", color:TXT, font:{ size:16, weight:"700" }, padding:{ top:4, bottom:8 } }, legend:{ display:true }, tooltip:{ enabled:true } }
    },
  };

  if(!chart){ chart = new Chart(ctx, conf); }
  else {
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.update("none");
  }
}
