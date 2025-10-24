// charts/hourly.js
import data from "../data.js";
import { AXIS, GRID } from "../theme.js";
import { findKeyCI } from "../utils.js";
import { actions } from "../state.js";

let chart;

export function renderHourly(state) {
  const el = document.getElementById("hourlyChart");
  if (!el) return;
  const ctx = el.getContext("2d");

  const hourLabels = Array.isArray(data.hourLabels) ? data.hourLabels.slice() : []; // "00".."23"
  const fmtLabels = hourLabels.map((h) => `${h}:00`);

  // --- Helpers ---
  const zeros = (n) => Array.from({ length: n }, () => 0);
  const safeNum = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);

  let series = Array.isArray(data.hourData) ? data.hourData.slice() : zeros(hourLabels.length);
  let label = "Alarmas (por hora, rango actual)";

  // ============================
  // PRIORIDAD ABSOLUTA: SUBTYPE
  // ============================
  if (state.subtypeFilter) {
    if (data.hourSeriesBySubtypeRaw && typeof data.hourSeriesBySubtypeRaw === "object") {
      const subKey =
        findKeyCI(data.hourSeriesBySubtypeRaw, state.subtypeFilter) ?? state.subtypeFilter;
      const arr = data.hourSeriesBySubtypeRaw[subKey] || [];
      series = Array.isArray(arr) ? hourLabels.map((_, i) => safeNum(arr[i])) : zeros(hourLabels.length);
      label = `Alarmas por hora — Subtype: ${subKey}`;
    } else {
      series = hourLabels.map((h) => {
        const bucket = data.subtypeByHourRaw?.[h] || {};
        const sk = findKeyCI(bucket, state.subtypeFilter) || state.subtypeFilter;
        return safeNum(bucket[sk]);
      });
      label = `Alarmas por hora — Subtype: ${state.subtypeFilter}`;
    }

  } else if (state.deviceFilter) {
    const dk = data.canonicalDeviceKey(state.deviceFilter);
    series = hourLabels.map((h) => safeNum((data.devByHourRaw?.[h] || {})[dk]));
    label = `Alarmas por hora — Dispositivo: ${dk}`;

  } else if (state.levelFilter) {
    const hasLevelHourly = !!data.levelCountsByHourRaw && typeof data.levelCountsByHourRaw === "object";
    const trySeries = hasLevelHourly
      ? hourLabels.map((h) => {
          const bucket = data.levelCountsByHourRaw?.[h] || {};
          const lk = findKeyCI(bucket, state.levelFilter) || state.levelFilter;
          return safeNum(bucket[lk]);
        })
      : zeros(hourLabels.length);

    const sum = trySeries.reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0);
    if (sum > 0) {
      series = trySeries;
      label = `Alarmas por hora — Level: ${state.levelFilter}`;
    } else {
      series = Array.isArray(data.hourData) ? data.hourData.slice() : zeros(hourLabels.length);
      label = "Alarmas (por hora, rango actual)";
      console.info("[hourly] Sin datos por level; usando serie global.");
    }

  } else if (state.severityFilter) {
    series = hourLabels.map((h) => {
      const m = data.sevByHourRaw?.[h] || {};
      const hk = findKeyCI(m, state.severityFilter) || state.severityFilter;
      return safeNum(m[hk]);
    });
    label = `Alarmas por hora — Severidad: ${state.severityFilter}`;

  } else if (state.actionFilter) {
    series = hourLabels.map((h) => safeNum((data.actByHourNorm?.[h] || {})[state.actionFilter]));
    label = `Alarmas por hora — Acción: ${state.actionFilter}`;

  } else if (state.msgSeverityFilter) {
    series = hourLabels.map((h) => safeNum((data.msgSeverityByHourRaw?.[h] || {})[state.msgSeverityFilter]));
    label = `Alarmas por hora — Msg Severity: ${state.msgSeverityFilter}`;
  }

  // ====== EFECTO DE FOCO POR HORA ======
  const activeHour = state.hourFilter ? String(state.hourFilter).trim() : "";
  const baseColor = "#22C55E";
  const bg = fmtLabels.map((_, i) => {
    const hourKey = hourLabels[i]; // "00".. "23"
    if (activeHour && hourKey !== activeHour) return "rgba(255,255,255,0.18)";
    return baseColor; // sólido para la hora activa o si no hay filtro
  });
  const border = fmtLabels.map((_, i) => {
    const hourKey = hourLabels[i];
    if (activeHour && hourKey !== activeHour) return "rgba(229,231,235,0.85)";
    return "#e5e7eb";
  });

  const conf = {
    type: "bar",
    data: {
      labels: fmtLabels,
      datasets: [
        {
          label,
          data: series,
          borderWidth: 2,
          backgroundColor: bg,
          borderColor: border,
          hoverBorderColor: border,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 600, easing: "easeOutQuart" },
      plugins: {
        legend: { display: false },
        tooltip: { enabled: true },
      },
      scales: {
        x: {
          ticks: { color: AXIS, autoSkip: false, maxRotation: 0, minRotation: 0 },
          grid: { color: GRID },
        },
        y: {
          beginAtZero: true,
          ticks: { color: AXIS },
          grid: { color: GRID },
        },
      },
    },
  };

  if (!chart) {
    chart = new Chart(ctx, conf);
    ctx.canvas.onclick = (evt) => {
      const points = chart.getElementsAtEventForMode(evt, "nearest", { intersect: true }, true);
      if (!points.length) return;
      const idx = points[0].index;
      const h = hourLabels[idx]; // usa el valor "00".."23"
      actions.toggleHour?.(h);
    };
  } else {
    chart.data.labels = conf.data.labels;
    chart.data.datasets[0].data = conf.data.datasets[0].data;
    chart.data.datasets[0].label = conf.data.datasets[0].label;
    chart.data.datasets[0].backgroundColor = conf.data.datasets[0].backgroundColor;
    chart.data.datasets[0].borderColor = conf.data.datasets[0].borderColor;
    chart.data.datasets[0].hoverBorderColor = conf.data.datasets[0].hoverBorderColor;
    chart.options = conf.options;
    chart.update();
  }
}
