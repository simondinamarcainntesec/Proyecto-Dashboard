// home_export.js
// Exportación 100% frontend (igual que dashboard_export.js)
// PDF = captura DOM (#home-export-area)
// CSV = genera datos desde atributos y estructuras del Home

(function () {
  document.addEventListener("DOMContentLoaded", function () {
    const toggleBtn = document.getElementById("homeExportToggleBtn");
    const menu = document.getElementById("homeExportMenu");

    if (!toggleBtn || !menu) {
      console.warn("[home_export] No se encontró el botón o el menú de exportación.");
      return;
    }

    let menuOpen = false;

    // ──────────────────────────────────────────────
    // MENÚ DESPLEGABLE
    // ──────────────────────────────────────────────
    function openMenu() {
      menu.classList.add("is-open");
      toggleBtn.setAttribute("aria-expanded", "true");
      menu.setAttribute("aria-hidden", "false");
      menuOpen = true;
    }

    function closeMenu() {
      menu.classList.remove("is-open");
      toggleBtn.setAttribute("aria-expanded", "false");
      menu.setAttribute("aria-hidden", "true");
      menuOpen = false;
    }

    function toggleMenu() {
      menuOpen ? closeMenu() : openMenu();
    }

    // ──────────────────────────────────────────────
    // LOADER GLOBAL
    // ──────────────────────────────────────────────
    function showLoader(message) {
      try {
        if (window.InntesecPageLoader?.show) {
          window.InntesecPageLoader.show(message || "Generando archivo…");
          return;
        }
      } catch (_) {}

      const ov = document.getElementById("loading-overlay");
      if (ov) ov.classList.add("is-active");
    }

    function hideLoader() {
      try {
        if (window.InntesecPageLoader?.hide) {
          window.InntesecPageLoader.hide();
          return;
        }
      } catch (_) {}

      const ov = document.getElementById("loading-overlay");
      if (ov) ov.classList.remove("is-active");
    }

    // ──────────────────────────────────────────────
    // CSV Export
    // ──────────────────────────────────────────────
    function buildCsvFromHome() {
      const rows = [];
      rows.push(["KPI", "Valor"]);

      const kpis = document.getElementById("home-kpis");
      if (kpis) {
        rows.push(["Alarmas", kpis.dataset.kpiTotal || "0"]);
        rows.push(["Críticas", kpis.dataset.kpiCritical || "0"]);
        rows.push(["SOAR", kpis.dataset.kpiSoar || "0"]);
        rows.push(["Telegram", kpis.dataset.kpiTelegram || "0"]);
      }

      // Severidades
      const items = document.querySelectorAll(".severity-item");
      items.forEach((el) => {
        const label = el.dataset.label || "";
        const count = el.dataset.count || "";
        rows.push([`Severidad - ${label}`, count]);
      });

      // Crear CSV
      const csv = rows
        .map((r) =>
          r
            .map((cell) => {
              const s = String(cell).replace(/"/g, '""');
              return `"${s}"`;
            })
            .join(",")
        )
        .join("\n");

      return csv;
    }

    function downloadCsv() {
      showLoader("Generando CSV…");

      try {
        const csv = buildCsvFromHome();
        const today = new Date().toISOString().slice(0, 10);
        const filename = `home_${today}.csv`;

        const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();

        URL.revokeObjectURL(url);
        a.remove();
      } finally {
        hideLoader();
      }
    }

    // ──────────────────────────────────────────────
    // PDF Export (captura del DOM)
    // ──────────────────────────────────────────────
    async function exportPdf() {
      const area = document.getElementById("home-export-area");
      if (!area) {
        alert("No se encontró el área exportable (#home-export-area)");
        return;
      }

      showLoader("Generando PDF…");

      const html2canvasFn = window.html2canvas;
      const jsPDF = window.jspdf?.jsPDF;

      if (!html2canvasFn || !jsPDF) {
        alert("Faltan librerías html2canvas o jsPDF.");
        hideLoader();
        return;
      }

      document.body.classList.add("exporting-pdf");

      try {
        const canvas = await html2canvasFn(area, {
          scale: 1.4,
          useCORS: true,
          scrollY: -window.scrollY,
          backgroundColor: getComputedStyle(document.body).backgroundColor,
        });

        const pxToMm = 0.264583;
        const widthMm = canvas.width * pxToMm;
        const heightMm = canvas.height * pxToMm;

        const orientation = widthMm > heightMm ? "landscape" : "portrait";

        const pdf = new jsPDF(orientation, "mm", [widthMm, heightMm]);
        pdf.addImage(canvas.toDataURL("image/jpeg", 0.92), "JPEG", 0, 0, widthMm, heightMm);

        const today = new Date().toISOString().slice(0, 10);
        pdf.save(`home_${today}.pdf`);
      } catch (err) {
        console.error("[home_export] Error PDF:", err);
        alert("No se pudo generar el PDF.");
      } finally {
        document.body.classList.remove("exporting-pdf");
        hideLoader();
      }
    }

    // ──────────────────────────────────────────────
    // EVENTOS DEL MENÚ
    // ──────────────────────────────────────────────
    toggleBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleMenu();
    });

    menu.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-export-format]");
      if (!btn) return;

      const fmt = btn.dataset.exportFormat;

      closeMenu();

      if (fmt === "pdf") exportPdf();
      else if (fmt === "csv") downloadCsv();
    });

    document.addEventListener("click", () => {
      if (menuOpen) closeMenu();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeMenu();
    });
  });
})();
