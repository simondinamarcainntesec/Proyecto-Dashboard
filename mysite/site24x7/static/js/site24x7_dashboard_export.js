// static/js/site24x7_dashboard_export.js
// Exporta SOLO el card "Dashboard Inn-Monitor" (iframe incluido)
// a PDF como captura visual, usando html2canvas + jsPDF.
// Nombre de archivo: <slug>_YYYY-MM-DD.pdf, donde el slug viene de
// data-page-slug en #dashboard-export-area.

(function () {
  // =============== Helpers nombre de archivo ===============

  function getTodayStr() {
    const now = new Date();
    return now.toISOString().slice(0, 10); // YYYY-MM-DD
  }

  function getExportBaseSlug() {
    // 1) data-page-slug en el área principal (recomendado)
    const area = document.getElementById("dashboard-export-area");
    if (area && area.dataset.pageSlug) {
      return area.dataset.pageSlug;
    }

    // 2) data-page-slug en el body (fallback opcional)
    if (document.body && document.body.dataset.pageSlug) {
      return document.body.dataset.pageSlug;
    }

    // 3) Fallback genérico
    return "Inn-monitor-dashboard";
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

  // =============== PDF – captura SOLO del dashboard Inn-Monitor ===============

  function exportPdf() {
    const area =
      document.getElementById("dashboard-export-area") ||
      document.querySelector(".wrap");

    if (!area) {
      alert("No se encontró el área del dashboard Inn-Monitor a exportar.");
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
    // Opcional: desactivar controles mientras se genera el PDF
    document.body.classList.add("exporting-pdf");

    const bodyBg =
      getComputedStyle(document.body).backgroundColor || "#020617";

    const originalBg = area.style.backgroundColor;
    if (!originalBg) {
      area.style.backgroundColor = bodyBg;
    }

    html2canvasFn(area, {
      scale: 1.4, // buena resolución sin monstruito de 60MB
      useCORS: true,
      backgroundColor: bodyBg,
      scrollY: -window.scrollY,
    })
      .then((canvas) => {
        const cw = canvas.width;
        const ch = canvas.height;

        console.log("[Inn-Monitor export] canvas size:", cw, ch);

        if (!cw || !ch || !isFinite(cw) || !isFinite(ch)) {
          throw new Error("Canvas inválido: " + cw + "x" + ch);
        }

        // px -> mm (96 px ≈ 25.4 mm)
        const pxToMm = 0.264583;
        let widthMm = cw * pxToMm;
        let heightMm = ch * pxToMm;

        // Evitar valores absurdos
        widthMm = Math.max(10, widthMm);
        heightMm = Math.max(10, heightMm);

        const orientation = widthMm >= heightMm ? "landscape" : "portrait";

        // El PDF tendrá exactamente el tamaño del card → sin márgenes blancos
        const pdf = new jsPDF(orientation, "mm", [widthMm, heightMm]);

        const imgData = canvas.toDataURL("image/jpeg", 0.92); // JPEG para bajar peso
        pdf.addImage(imgData, "JPEG", 0, 0, widthMm, heightMm);
        pdf.save(filename);
      })
      .catch((err) => {
        console.error("Error generando PDF de Inn-Monitor", err);
        alert("Ocurrió un problema generando el PDF de Inn-Monitor.");
      })
      .finally(() => {
        // Restaurar estado visual
        document.body.classList.remove("exporting-pdf");
        area.style.backgroundColor = originalBg;
        forceHideGlobalLoader();
      });
  }

  // =============== Menú export (solo PDF) ===============

  function setupExportMenu() {
    const btnToggle = document.getElementById("btn-export-toggle");
    const menu = document.getElementById("export-menu");
    if (!btnToggle || !menu) return;

    btnToggle.addEventListener("click", function (ev) {
      ev.stopPropagation();
      menu.classList.toggle("is-open");
      const isOpen = menu.classList.contains("is-open");
      btnToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      menu.setAttribute("aria-hidden", isOpen ? "false" : "true");
      forceHideGlobalLoader();
    });

    menu.addEventListener("click", function (ev) {
      const target = ev.target.closest("button[data-export-format]");
      if (!target) return;

      ev.preventDefault();
      const fmt = target.getAttribute("data-export-format");
      menu.classList.remove("is-open");
      btnToggle.setAttribute("aria-expanded", "false");
      menu.setAttribute("aria-hidden", "true");

      if (fmt === "pdf") {
        exportPdf();
      }
      // No hay CSV en este dashboard
    });

    document.addEventListener("click", function (ev) {
      if (!menu.classList.contains("is-open")) return;
      const target = ev.target;
      if (
        target === menu ||
        target === btnToggle ||
        menu.contains(target) ||
        btnToggle.contains(target)
      ) {
        return;
      }
      menu.classList.remove("is-open");
      btnToggle.setAttribute("aria-expanded", "false");
      menu.setAttribute("aria-hidden", "true");
    });
  }

  document.addEventListener("DOMContentLoaded", setupExportMenu);
})();
