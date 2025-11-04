import { AXIS, GRID } from "/static/js/soar/theme.js";
import { actions } from "/static/js/soar/state.js";
import { selectTopIPsPayload } from "/static/js/soar/selectors.js";

let chartSrc, chartDst;

export function renderTopIPs(){
  // SRC
  {
    const payload = selectTopIPsPayload("src", 10, true);
    const el = document.getElementById("chartTopSrcIP"); if(el){
      const ctx = el.getContext("2d");
      const labels = payload.labels||[], data = payload.data||[];
      const conf = {
        type:"bar",
        data:{ labels, datasets:[{ label:"Eventos (src)", data,
          backgroundColor:"#22C55E",
          borderColor:"#e5e7eb", hoverBorderColor:"#e5e7eb",
          borderWidth:2, hoverBorderWidth:2, borderSkipped:false, borderRadius:6 }]},
        options:{
          animation:{ duration:600, easing:"easeOutQuart" },
          plugins:{ legend:{ display:false } }, elements:{ bar:{ borderSkipped:false } },
          scales:{
            y:{ beginAtZero:true, ticks:{ color:AXIS }, grid:{ color:GRID } },
            x:{ type:"category", ticks:{ color:AXIS, callback:(_v,i)=>labels[i]??_v, autoSkip:true, maxRotation:30, minRotation:0 }, grid:{ color:GRID } }
          }
        }
      };
      if(!chartSrc){
        chartSrc = new Chart(ctx, conf);
        ctx.canvas.onclick=(evt)=>{
          const els = chartSrc.getElementsAtEventForMode(evt,"nearest",{intersect:true},true);
          if(!els.length) return; const idx=els[0].index;
          actions.toggleIP?.(labels[idx]);
        };
      } else {
        chartSrc.data.labels = labels; chartSrc.data.datasets[0].data = data;
        chartSrc.options.scales.x.ticks.callback = (_v,i)=>labels[i]??_v;
        chartSrc.update("none");
      }
    }
  }
  // DST
  {
    const payload = selectTopIPsPayload("dst", 10, true);
    const el = document.getElementById("chartTopDstIP"); if(el){
      const ctx = el.getContext("2d");
      const labels = payload.labels||[], data = payload.data||[];
      const conf = {
        type:"bar",
        data:{ labels, datasets:[{ label:"Eventos (dst)", data,
          backgroundColor:"#F97316",
          borderColor:"#e5e7eb", hoverBorderColor:"#e5e7eb",
          borderWidth:2, hoverBorderWidth:2, borderSkipped:false, borderRadius:6 }]},
        options:{
          animation:{ duration:600, easing:"easeOutQuart" },
          plugins:{ legend:{ display:false } }, elements:{ bar:{ borderSkipped:false } },
          scales:{
            y:{ beginAtZero:true, ticks:{ color:AXIS }, grid:{ color:GRID } },
            x:{ type:"category", ticks:{ color:AXIS, callback:(_v,i)=>labels[i]??_v, autoSkip:true, maxRotation:30, minRotation:0 }, grid:{ color:GRID } }
          }
        }
      };
      if(!chartDst){
        chartDst = new Chart(ctx, conf);
        ctx.canvas.onclick=(evt)=>{
          const els = chartDst.getElementsAtEventForMode(evt,"nearest",{intersect:true},true);
          if(!els.length) return; const idx=els[0].index;
          actions.toggleIP?.(labels[idx]);
        };
      } else {
        chartDst.data.labels = labels; chartDst.data.datasets[0].data = data;
        chartDst.options.scales.x.ticks.callback = (_v,i)=>labels[i]??_v;
        chartDst.update("none");
      }
    }
  }
}
