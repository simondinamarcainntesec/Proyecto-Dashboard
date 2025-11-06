import { AXIS, GRID } from "/static/js/soar/theme.js";
import { actions } from "/static/js/soar/state.js";
import { selectSourcesPayload } from "/static/js/soar/selectors.js";

let chart;
export function renderSources(){
  const payload = selectSourcesPayload(10, true);
  const el = document.getElementById("chartSources"); if(!el) return;
  const ctx = el.getContext("2d");
  const labels = payload.labels||[], data = payload.data||[];

  const conf = {
    type:"bar",
    data:{ labels, datasets:[{ label:"Eventos", data,
      backgroundColor:"#06B6D4",
      borderColor:"#e5e7eb", hoverBorderColor:"#e5e7eb",
      borderWidth:2, hoverBorderWidth:2, borderSkipped:false, borderRadius:6 }]},
    options:{
      indexAxis:"y", animation:{ duration:600, easing:"easeOutQuart" },
      plugins:{ legend:{ display:false } }, elements:{ bar:{ borderSkipped:false } },
      scales:{
        x:{ beginAtZero:true, ticks:{ color:AXIS }, grid:{ color:GRID } },
        y:{ type:"category", ticks:{ color:AXIS, callback:(_v,i)=>labels[i]??_v }, grid:{ color:GRID } }
      }
    }
  };

  if(!chart){
    chart = new Chart(ctx, conf);
    ctx.canvas.onclick=(evt)=>{
      const els = chart.getElementsAtEventForMode(evt,"nearest",{intersect:true},true);
      if(!els.length) return;
      const idx = els[0].index;
      actions.toggleSource?.(labels[idx]);
    };
  } else {
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.options.scales.y.ticks.callback = (_v,i)=>labels[i]??_v;
    chart.update("none");
  }
}
