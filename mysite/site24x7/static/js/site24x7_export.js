// static/js/site24x7_export.js
// Exporta la vista de monitores Site24x7 a PDF (captura visual completa)
// y CSV (datos de la tabla).

(function () {
  // =============== Helpers nombre de archivo ===============

  function getExportBaseSlug() {
    // 1) data-page-slug en el área principal (igual que dashboard)
    const area = document.getElementById("dashboard-export-area");
    if (area && area.dataset.pageSlug) {
      return area.dataset.pageSlug;
    }

    // 2) data-page-slug en el body (por si se usa ahí)
    if (document.body && document.body.dataset.pageSlug) {
      return document.body.dataset.pageSlug;
    }

    // 3) Intentar deducirlo desde la URL: /site24x7/xxx/
    const path = window.location.pathname || "";
    const m = path.match(/\/site24x7\/([^/]+)/);
    if (m && m[1]) {
      return m[1];
    }

    // 4) Fallback genérico
    return "site24x7_monitores";
  }

  function getTodayStr() {
    const now = new Date();
    return now.toISOString().slice(0, 10); // YYYY-MM-DD
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

  // ================= CSV (desde tabla de monitores) =================

  function collectMonitorsData() {
    const rows = [];
    const trs = document.querySelectorAll("#tbl-site24x7-monitors tbody tr");

    trs.forEach((tr) => {
      if (tr.querySelector("td.center")) return; // fila "sin monitores"

      const ds = tr.dataset || {};
      const statusName =
        ds.statusName || (tr.cells[0] ? tr.cells[0].innerText.trim() : "");
      const monitorName =
        ds.monitorName || (tr.cells[1] ? tr.cells[1].innerText.trim() : "");
      const monitorType =
        ds.monitorType || (tr.cells[2] ? tr.cells[2].innerText.trim() : "");
      const lastPolled =
        ds.lastPolled || (tr.cells[3] ? tr.cells[3].innerText.trim() : "");

      rows.push({
        statusName,
        monitorName,
        monitorType,
        lastPolled,
      });
    });

    return rows;
  }

  function buildCsv() {
    const data = collectMonitorsData();
    const rows = [];

    rows.push(["Estado", "Nombre del monitor", "Tipo", "Último sondeo"]);

    data.forEach((r) => {
      rows.push([
        r.statusName || "",
        r.monitorName || "",
        r.monitorType || "",
        r.lastPolled || "",
      ]);
    });

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
    forceHideGlobalLoader();

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

  // ================= PDF – captura visual =================

  function exportPdf() {
    const area =
      document.getElementById("dashboard-export-area") ||
      document.querySelector(".wrap") ||
      document.querySelector(".content");

    if (!area) {
      alert("No se encontró el área de monitores a exportar.");
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

    // Aseguramos que el overlay no tape nada
    forceHideGlobalLoader();
    document.body.classList.add("exporting-pdf");

    const bodyBg =
      getComputedStyle(document.body).backgroundColor || "#020617";

    const originalBg = area.style.backgroundColor;
    if (!originalBg) {
      area.style.backgroundColor = bodyBg;
    }

    html2canvasFn(area, {
      scale: 1.4, // misma idea que en dashboard_export.js
      useCORS: true,
      backgroundColor: bodyBg,
      scrollY: -window.scrollY,
    })
      .then((canvas) => {
        const cw = canvas.width;
        const ch = canvas.height;

        if (!cw || !ch || !isFinite(cw) || !isFinite(ch)) {
          throw new Error("Canvas inválido: " + cw + "x" + ch);
        }

        // px -> mm (96 px ≈ 25.4 mm)
        const pxToMm = 0.264583;
        let widthMm = cw * pxToMm;
        let heightMm = ch * pxToMm;

        widthMm = Math.max(10, widthMm);
        heightMm = Math.max(10, heightMm);

        const orientation = widthMm >= heightMm ? "landscape" : "portrait";

        const pdf = new jsPDF(orientation, "mm", [widthMm, heightMm]);

        const imgData = canvas.toDataURL("image/jpeg", 0.92);
        pdf.addImage(imgData, "JPEG", 0, 0, widthMm, heightMm);
        pdf.save(filename);
      })
      .catch((err) => {
        console.error("Error generando PDF", err);
        alert("Ocurrió un problema generando el PDF.");
      })
      .finally(() => {
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

