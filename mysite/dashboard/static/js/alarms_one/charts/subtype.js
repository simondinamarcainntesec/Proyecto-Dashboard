// charts/subtype.js
import data from "../data.js";
import { actions, getState } from "../state.js";
import { colorFor } from "../theme.js";

let subtypeChart;

function trunc(s, n = 14) {
  const t = String(s ?? "");
  return t.length > n ? t.slice(0, n - 1) + "…" : t;
}
function eqCI(a, b) {
  return String(a).trim().toLowerCase() === String(b).trim().toLowerCase();
}

export function renderSubtypeBar(ds, activeKey = "") {
  const ctx = document.getElementById("subtypeBar");
  if (!ctx) return;

  // ==========
  // Fallback: si hay levelFilter y el ds no viene filtrado por level,
  // intenta construirlo desde data.subtypeByLevelRaw (si existe)
  // ==========
  const st = getState();
  let localDS = ds;

  const needLevel = !!st.levelFilter;
  const maybeLevelMap = data.subtypeByLevelRaw || data.subtypeCountsByLevel || null; // acepta ambos nombres

  if (needLevel && maybeLevelMap) {
    // ¿ds ya está filtrado por level? heurística simple: ¿label incluye el level?
    const dsSeemsLevel =
      Array.isArray(ds?.labels) &&
      typeof ds?.data !== "undefined" &&
      // si no hay datos o coincide en longitud pero es todo 0, forzamos fallback
      ds.labels.length > 0;

    if (!dsSeemsLevel) {
      const levKey =
        Object.keys(maybeLevelMap).find((k) => eqCI(k, st.levelFilter)) ||
        st.levelFilter;

      const per = maybeLevelMap[levKey] || {};
      const labelsF = Object.keys(per);
      const dataF = labelsF.map((k) => Number(per[k] || 0));
      localDS = { labels: labelsF, data: dataF, keys: labelsF };
      // Nota: no tocamos activeKey aquí; si ya había subtype activo, se seguirá resaltando
    }
  }

  // Normaliza dataset visible
  const labels = Array.isArray(localDS?.labels) ? localDS.labels.map(String) : [];
  const values = labels.map((_, i) => Number((localDS?.data || [])[i] || 0));

  // Claves REALES (pueden coincidir con labels o no)
  const keys =
    Array.isArray(localDS?.keys) && localDS.keys.length === labels.length
      ? localDS.keys.map(String)
      : labels.slice();

  // Colores (resalta si hay filtro activo)
  const bg = labels.map((_, i) =>
    activeKey && eqCI(keys[i], activeKey) ? colorFor(keys[i]) : colorFor(keys[i]) + "99"
  );
  const border = labels.map((_, i) => colorFor(keys[i]));

  const cfg = {
    type: "bar",
    data: {
      labels, // etiquetas visibles
      datasets: [
        {
          label: "Subtype",
          data: values,
          backgroundColor: bg,
          borderColor: border,
          borderWidth: 1.5,
          hoverBackgroundColor: border,
          hoverBorderColor: border,
        },
      ],
    },
    options: {
      animation: false,
      maintainAspectRatio: false,
      responsive: true,
      indexAxis: "x",
      onClick: (_, elements) => {
        if (!elements || !elements.length) return;
        const idx = elements[0].index;
        const key = keys[idx]; // ← usa la clave real alineada con el backend
        actions.toggleSubtype?.(key);
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            // Título del tooltip = etiqueta visible (no truncada)
            title: (items) => (items?.[0] ? String(items[0].label) : ""),
            label: (item) => `Cantidad: ${item.formattedValue}`,
          },
        },
      },
      scales: {
        x: {
          type: "category",
          offset: true,
          ticks: {
            autoSkip: false,
            maxRotation: 0,
            minRotation: 0,
            padding: 6,
            font: { size: 12, weight: "700" },
            // Ticks truncados solo para el eje (no afecta tooltip ni click)
            callback: (_, i) => trunc(labels[i]),
          },
          grid: { display: false },
        },
        y: { beginAtZero: true },
      },
      layout: { padding: { bottom: 6 } },
      categoryPercentage: 0.8,
      barPercentage: 0.9,
    },
  };

  if (subtypeChart) {
    subtypeChart.data.labels = labels;
    subtypeChart.data.datasets[0].data = values;
    subtypeChart.data.datasets[0].backgroundColor = bg;
    subtypeChart.data.datasets[0].borderColor = border;
    subtypeChart.update();
  } else {
    subtypeChart = new window.Chart(ctx, cfg);
  }
}
