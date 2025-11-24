// static/js/home_alarms_chart.js

document.addEventListener("DOMContentLoaded", function () {
  const canvas = document.getElementById("alarmsTrendChart");
  if (!canvas || typeof Chart === "undefined") return;

  // === Utils ===
  function fmtDDMM(label) {
    const s = String(label || "").trim();

    // ISO: 2025-11-03 -> 03-11
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
      return `${s.slice(8, 10)}-${s.slice(5, 7)}`;
    }

    // DD/MM/YYYY -> DD-MM
    if (/^\d{2}\/\d{2}\/\d{4}$/.test(s)) {
      return `${s.slice(0, 2)}-${s.slice(3, 5)}`;
    }

    // DD-MM
    if (/^\d{2}-\d{2}$/.test(s)) return s;

    const d = new Date(s);
    if (!isNaN(d.getTime())) {
      const dd = String(d.getDate()).padStart(2, "0");
      const mm = String(d.getMonth() + 1).padStart(2, "0");
      return `${dd}-${mm}`;
    }
    return s;
  }

  // Datos desde el template
  let labels = [];
  let seriesTotal = [];
  let seriesCritical = [];

  try {
    labels = JSON.parse(canvas.dataset.labels || "[]");
    seriesTotal = JSON.parse(canvas.dataset.totalSeries || "[]");
    seriesCritical = JSON.parse(canvas.dataset.criticalSeries || "[]");
  } catch (e) {
    console.error("[HOME] Error parseando datos del gráfico:", e);
    return;
  }

  if (!labels.length) return;

  const ctx = canvas.getContext("2d");

  // Colores (mismo look SOAR)
  const TXT  = "#e5e7eb";
  const AXIS = "#e5e7eb";
  const GRID = "rgba(148,163,184,.22)";

  const datasets = [
    {
      label: "Alarmas totales",
      data: seriesTotal,
      tension: 0.25,
      fill: false,
      borderColor: "#60A5FA",
      backgroundColor: "#60A5FA",
      pointRadius: 3,
      pointHoverRadius: 5,
      borderWidth: 2,
      pointStyle: "circle",
    },
  ];

  // solo dibujar críticas si hay algún valor > 0
  const hasCritical =
    Array.isArray(seriesCritical) &&
    seriesCritical.some((v) => Number(v || 0) > 0);

  if (hasCritical) {
    datasets.push({
      label: "Alarmas críticas",
      data: seriesCritical,
      tension: 0.25,
      fill: false,
      borderColor: "#F97373",
      backgroundColor: "#F97373",
      pointRadius: 3,
      pointHoverRadius: 5,
      borderWidth: 2,
      pointStyle: "circle",
    });
  }

  const dataConf = { labels, datasets };

  const opts = {
    responsive: true,
    maintainAspectRatio: false, // usa el alto del contenedor (320px del CSS)
    layout: {
      // margen interno razonable sin alejarlo de los bordes
      padding: { top: 10, right: 10, bottom: 8, left: 8 },
    },
    animation: { duration: 600, easing: "easeOutQuart" },
    animations: {
      numbers: { type: "number", duration: 600, easing: "easeOutQuart" },
      tension: { duration: 600, easing: "easeOutQuart", from: 0.35, to: 0.25 },
    },
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: {
        position: "top",
        labels: {
          color: TXT,
          usePointStyle: true,   // círculos en la leyenda
          boxWidth: 10,
          boxHeight: 10,
          padding: 8,
        },
        onClick: () => {},       // no togglear en home
      },
      tooltip: { enabled: true },
    },
    scales: {
      x: {
        type: "category",
        ticks: {
          color: AXIS,
          autoSkip: false,
          minRotation: 55,
          maxRotation: 55,
          padding: 4,
          font: { size: 11 },
          callback: (value, index) => {
            const raw = labels[index];
            return fmtDDMM(raw);
          },
        },
        grid: { color: GRID },
      },
      y: {
        beginAtZero: true,
        ticks: {
          color: AXIS,
          padding: 4,
        },
        grid: { color: GRID },
      },
    },
    events: ["mousemove", "mouseout", "touchstart", "touchmove", "touchend"],
  };

  new Chart(ctx, { type: "line", data: dataConf, options: opts });

  ctx.canvas.style.cursor = "default";
});
