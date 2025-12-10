// static/js/alarms_one/dashboard_export.js
// Exporta el dashboard (histórico / realtime / SOAR) a PDF (captura visual completa)
// y CSV (datos agregados) usando un nombre de archivo basado en el slug de la
// página + la fecha actual: <slug>_YYYY-MM-DD.{pdf,csv}

(function () {
  function safeParseScript(id, fallback) {
    const el = document.getElementById(id);
    if (!el) return fallback;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      console.warn("No se pudo parsear JSON de", id, e);
      return fallback;
    }
  }

  // =============== Helpers nombre de archivo ===============

  function getExportBaseSlug() {
    // 1) data-page-slug en el área principal (recomendado)
    const area = document.getElementById("dashboard-export-area");
    if (area && area.dataset.pageSlug) {
      return area.dataset.pageSlug;
    }

    // 2) data-page-slug en el body (por si se usa ahí)
    if (document.body && document.body.dataset.pageSlug) {
      return document.body.dataset.pageSlug;
    }

    // 3) Intentar deducirlo desde la URL: /dashboard/xxx/
    const path = window.location.pathname || "";
    const m = path.match(/\/dashboard\/([^/]+)/);
    if (m && m[1]) {
      return m[1];
    }

    // 4) Fallback genérico
    return "dashboard";
  }

  function getTodayStr() {
    // YYYY-MM-DD basado en hora local del navegador
    const now = new Date();
    return now.toISOString().slice(0, 10);
  }

  function getExportFileName(ext) {
    const slug = getExportBaseSlug();
    const dateStr = getTodayStr();
    return `${slug}_${dateStr}.${ext}`;
  }

  // =============== Loader (forzar ocultar) ===============

  function forceHideGlobalLoader() {
    const ov = document.getElementById("loading-overlay");
    if (!ov) return;
    ov.classList.remove("is-active");
    ov.style.opacity = "0";
    ov.style.visibility = "hidden";
  }

  // ================= CSV =================

  function buildCsvForSoar(events) {
    const rows = [];
    rows.push([
      "Alarm ID",
      "Fecha",
      "Hora",
      "Dispositivo",
      "Servicio",
      "Protocolo",
      "País origen",
      "IP Origen",
      "IP Destino",
      "AO Tag",
      "Severidad",
      "Acción seguridad",
      "Acción",
      "Aplicación",
    ]);

    events.forEach((e) => {
      rows.push([
        e.alarm_id ?? "",
        e.date ?? "",
        e.time ?? "",
        e.device ?? "",
        e.service ?? "",
        e.proto ?? "",
        e.srccountry ?? "",
        e.srcip ?? "",
        e.dstip ?? "",
        e.aotag ?? "",
        e.severity ?? "",
        e.security_action ?? "",
        e.action ?? "",
        e.Application ?? "",
      ]);
    });

    return rows;
  }

  function buildCsvForAlarms() {
    const rows = [];
    rows.push(["Sección", "Etiqueta", "Valor"]);

    // 1) Alarmas por día
    const trendLabels = safeParseScript("trend-labels", []);
    const trendData = safeParseScript("trend-data", []);
    if (Array.isArray(trendLabels) && Array.isArray(trendData)) {
      trendLabels.forEach((label, i) => {
        rows.push(["Alarmas por día", label, trendData[i] ?? ""]);
      });
    }

    // 2) Alarmas por hora
    const hourLabels = safeParseScript("hour-labels", []);
    const hourData = safeParseScript("hour-data", []);
    if (Array.isArray(hourLabels) && Array.isArray(hourData)) {
      hourLabels.forEach((label, i) => {
        rows.push(["Alarmas por hora", label, hourData[i] ?? ""]);
      });
    }

    // 3) Severidad (donut)
    const severityCounts = safeParseScript("severity-counts", {});
    Object.entries(severityCounts || {}).forEach(([label, value]) => {
      rows.push(["Severidad", label, value]);
    });

    // 4) Acciones
    const actionCounts = safeParseScript("action-counts", {});
    Object.entries(actionCounts || {}).forEach(([label, value]) => {
      rows.push(["Acciones", label, value]);
    });

    // 5) Level
    const levelCounts = safeParseScript("level-counts", {});
    Object.entries(levelCounts || {}).forEach(([label, value]) => {
      rows.push(["Level", label, value]);
    });

    // 6) Subtype
    const subtypeCounts = safeParseScript("subtype-counts", {});
    Object.entries(subtypeCounts || {}).forEach(([label, value]) => {
      rows.push(["Subtype", label, value]);
    });

    // 7) Severidad Alarma (msg_severity)
    const msgSeverityCounts = safeParseScript("msg-severity-counts", {});
    Object.entries(msgSeverityCounts || {}).forEach(([label, value]) => {
      rows.push(["Severidad Alarma", label, value]);
    });

    // 8) Dispositivos recientes
    const deviceCounts = safeParseScript("device-counts", {});
    Object.entries(deviceCounts || {}).forEach(([label, value]) => {
      rows.push(["Dispositivos recientes", label, value]);
    });

    return rows;
  }

  function buildCsv() {
    // Si estamos en SOAR, usamos el JSON "soar-events"
    const soarEvents = safeParseScript("soar-events", null);
    let rows;
    if (Array.isArray(soarEvents) && soarEvents.length > 0) {
      rows = buildCsvForSoar(soarEvents);
    } else {
      // Dashboards de Alarmas (histórico / realtime)
      rows = buildCsvForAlarms();
    }

    const csvLines = rows.map((row) =>
      row
        .map((value) => {
          const s =
            value === null || value === undefined ? "" : String(value);
          if (/[",\n]/.test(s)) {
            return '"' + s.replace(/"/g, '""') + '"';
          }
          return s;
        })
        .join(",")
    );

    return csvLines.join("\r\n");
  }

  function downloadCsv() {
    forceHideGlobalLoader(); // por si algún script lo activó

    try {
      const csv = buildCsv();
      const filename = getExportFileName("csv");

      const blob = new Blob([csv], {
        type: "text/csv;charset=utf-8;",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } finally {
      forceHideGlobalLoader();
    }
  }

  // ================= PDF – página del tamaño exacto del dashboard =================

  function exportPdf() {
    const area =
      document.getElementById("dashboard-export-area") ||
      document.querySelector(".grid-main") ||
      document.querySelector(".content");

    if (!area) {
      alert("No se encontró el área del dashboard a exportar.");
      return;
    }

    const html2canvasFn = window.html2canvas;
    if (!html2canvasFn) {
      alert("No se encontró la librería html2canvas.");
      return;
    }

    const jsPdfNamespace = window.jspdf;
    const jsPDF = jsPdfNamespace && jsPdfNamespace.jsPDF;
    if (!jsPDF) {
      alert("No se encontró la librería jsPDF.");
      return;
    }

    const filename = getExportFileName("pdf");

    // Asegurarnos de que el overlay NO esté activo ni afecte la captura
    forceHideGlobalLoader();
    // Ocultar chips de filtro mientras se genera el PDF
    document.body.classList.add("exporting-pdf");

    const bodyBg =
      getComputedStyle(document.body).backgroundColor || "#020617";

    const originalBg = area.style.backgroundColor;
    if (!originalBg) {
      area.style.backgroundColor = bodyBg;
    }

    html2canvasFn(area, {
      scale: 1.4, // resolución buena, sin llegar al monstruo de 60MB
      useCORS: true,
      backgroundColor: bodyBg,
      scrollY: -window.scrollY,
    })
      .then((canvas) => {
        const cw = canvas.width;
        const ch = canvas.height;

        console.log("[export] canvas size:", cw, ch);

        if (!cw || !ch || !isFinite(cw) || !isFinite(ch)) {
          throw new Error("Canvas inválido: " + cw + "x" + ch);
        }

        // px -> mm (96 px ≈ 25.4 mm)
        const pxToMm = 0.264583;
        let widthMm = cw * pxToMm;
        let heightMm = ch * pxToMm;

        // Evitar valores ridículos
        widthMm = Math.max(10, widthMm);
        heightMm = Math.max(10, heightMm);

        const orientation = widthMm >= heightMm ? "landscape" : "portrait";

        // El PDF tendrá exactamente el tamaño del dashboard → sin márgenes blancos
        const pdf = new jsPDF(orientation, "mm", [widthMm, heightMm]);

        const imgData = canvas.toDataURL("image/jpeg", 0.92); // JPEG para reducir peso
        pdf.addImage(imgData, "JPEG", 0, 0, widthMm, heightMm);
        pdf.save(filename);
      })
      .catch((err) => {
        console.error("Error generando PDF", err);
        alert("Ocurrió un problema generando el PDF.");
      })
      .finally(() => {
        // Restaurar estado visual
        document.body.classList.remove("exporting-pdf");
        area.style.backgroundColor = originalBg;
        forceHideGlobalLoader();
      });
  }

  // ================= Menú export =================

  function setupExportMenu() {
    const btnToggle = document.getElementById("btn-export-toggle");
    const menu = document.getElementById("export-menu");
    if (!btnToggle || !menu) return;

    btnToggle.addEventListener("click", function (ev) {
      ev.stopPropagation();
      menu.classList.toggle("is-open");
      // Asegurarse de que el loader esté oculto si por alguna razón se activó
      forceHideGlobalLoader();
    });

    menu.addEventListener("click", function (ev) {
      const target = ev.target;
      if (!(target instanceof HTMLElement)) return;
      const fmt = target.getAttribute("data-export-format");
      if (!fmt) return;

      ev.preventDefault();
      menu.classList.remove("is-open");

      if (fmt === "pdf") {
        exportPdf();
      } else if (fmt === "csv") {
        downloadCsv();
      }
    });

    document.addEventListener("click", function (ev) {
      if (!menu.classList.contains("is-open")) return;
      const target = ev.target;
      if (!(target instanceof Node)) return;
      if (
        target === menu ||
        target === btnToggle ||
        menu.contains(target) ||
        btnToggle.contains(target)
      ) {
        return;
      }
      menu.classList.remove("is-open");
    });
  }

  document.addEventListener("DOMContentLoaded", setupExportMenu);
})();
