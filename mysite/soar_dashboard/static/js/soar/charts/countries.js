// charts/countries.js — Donut Top Países con el MISMO borde blanco constante
import { TXT } from "/static/js/soar/theme.js";
import { actions, getState } from "/static/js/soar/state.js";
import { selectCountriesPayload } from "/static/js/soar/selectors.js";

let chart;
const norm = (s) => String(s ?? "").trim().toLowerCase();

// paleta estable
const PALETTE = [
  "#60A5FA","#8B5CF6","#10B981","#F59E0B","#06B6D4",
  "#F97316","#22C55E","#EAB308","#2563EB","#DC2626",
  "#0EA5E9","#A855F7"
];
const withAlpha = (hex, a = "FF") => (hex || "#9CA3AF").slice(0,7) + a;

export function renderCountries(){
  // self-ignore → ignora countryFilter al calcularse
  const payload = selectCountriesPayload(10, true);
  const canvas = document.getElementById("chartCountries");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  const labels = (payload.labels || []).slice();
  const values = (payload.data || []).slice();
  const active = norm(getState().countryFilter || "");

  const backgroundColors = labels.map((lbl, i) => {
    const base = PALETTE[i % PALETTE.length];
    return active && norm(lbl) !== active ? "rgba(255,255,255,0.18)" : withAlpha(base,"FF");
  });

  const titleText = active
    ? `País: ${labels.find(l => norm(l)===active) ?? active}`
    : "Top países de origen (srccountry)";

  const conf = {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: backgroundColors,
        // ✅ borde blanco constante en TODAS las porciones
        borderColor: "#e5e7eb",
        hoverBorderColor: "#e5e7eb",
        borderWidth: 2,
        hoverBorderWidth: 2,
        hoverOffset: 8
      }]
    },
    options: {
      cutout: "62%",
      animation: { duration: 600, easing: "easeOutQuart" },
      plugins: {
        title: {
          display: true,
          text: titleText,
          color: TXT,
          font: { size: 16, weight: "700" },
          padding: { top: 4, bottom: 8 }
        },
        legend: { display: false },
        tooltip: { enabled: true }
      }
    }
  };

  if (!chart){
    chart = new Chart(ctx, conf);
    ctx.canvas.onclick = (evt) => {
      const els = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!els.length) return;
      const idx = els[0].index;
      actions.toggleCountry?.(labels[idx]);
    };
    chart.$static = { labels: labels.slice(), values: values.slice() };
    return;
  }

  const sameLabels =
    Array.isArray(chart.$static?.labels) &&
    chart.$static.labels.length === labels.length &&
    chart.$static.labels.every((v, i) => v === labels[i]);

  const sameValues =
    Array.isArray(chart.$static?.values) &&
    chart.$static.values.length === values.length &&
    chart.$static.values.every((v, i) => Number(v) === Number(values[i]));

  if (sameLabels && sameValues) {
    const ds = chart.data.datasets[0];
    ds.backgroundColor = backgroundColors;
    // borde blanco constante (no cambia)
    chart.options.plugins.title.text = titleText;
    chart.update("none");
  } else {
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.data.datasets[0].backgroundColor = backgroundColors;
    chart.options.plugins.title.text = titleText;
    chart.$static = { labels: labels.slice(), values: values.slice() };
    chart.update();
  }
}
