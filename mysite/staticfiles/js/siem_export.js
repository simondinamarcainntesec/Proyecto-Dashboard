// static/js/siem_export.js
// Exporta las alertas SIEM visibles en la tabla a CSV,
// plano: 1 dato por columna, usando los mismos campos del detalle.

(function () {
  document.addEventListener("DOMContentLoaded", function () {
    const toggleBtn = document.getElementById("siemExportToggleBtn");
    const menu = document.getElementById("siemExportMenu");

    if (!toggleBtn || !menu) {
      console.warn("[siem_export] No se encontró toggleBtn o menú");
      return;
    }

    let menuOpen = false;

    // ───────────── Menú desplegable ─────────────
    function openMenu() {
      if (menuOpen) return;
      menu.classList.add("is-open");
      // Blindaje: si algún CSS no tiene .is-open, igual lo mostramos.
      menu.style.display = "block";
      toggleBtn.setAttribute("aria-expanded", "true");
      menu.setAttribute("aria-hidden", "false");
      menuOpen = true;
    }

    function closeMenu() {
      if (!menuOpen) return;
      menu.classList.remove("is-open");
      menu.style.display = "none";
      toggleBtn.setAttribute("aria-expanded", "false");
      menu.setAttribute("aria-hidden", "true");
      menuOpen = false;
    }

    function toggleMenu() {
      menuOpen ? closeMenu() : openMenu();
    }

    // ───────────── Loader ─────────────
    function showLoader(message) {
      try {
        if (
          window.InntesecPageLoader &&
          typeof window.InntesecPageLoader.show === "function"
        ) {
          window.InntesecPageLoader.show(message || "Generando CSV…");
          return;
        }
      } catch (e) {
        console.warn("[siem_export] InntesecPageLoader.show no disponible", e);
      }

      const ov = document.getElementById("loading-overlay");
      if (ov) ov.classList.add("is-active");
    }

    function hideLoader() {
      try {
        if (
          window.InntesecPageLoader &&
          typeof window.InntesecPageLoader.hide === "function"
        ) {
          window.InntesecPageLoader.hide();
          return;
        }
      } catch (e) {
        console.warn("[siem_export] InntesecPageLoader.hide no disponible", e);
      }

      const ov = document.getElementById("loading-overlay");
      if (ov) ov.classList.remove("is-active");
    }

    // ───────────── Helpers CSV ─────────────
    function escapeCsvField(value) {
      const s = value === null || value === undefined ? "" : String(value);
      if (/[",\n]/.test(s)) {
        return '"' + s.replace(/"/g, '""') + '"';
      }
      return s;
    }

    function getField(obj, key) {
      if (!obj) return "";
      const v = obj[key];
      return v === null || v === undefined ? "" : String(v);
    }

    function buildCsvFromTable() {
      const table = document.getElementById("tbl-siem-alerts");
      if (!table) {
        console.warn("[siem_export] No se encontró la tabla #tbl-siem-alerts");
        return "";
      }

      const tbody = table.querySelector("tbody");
      if (!tbody) {
        console.warn("[siem_export] Tabla sin tbody");
        return "";
      }

      const trs = Array.from(tbody.querySelectorAll("tr"));
      if (!trs.length) {
        console.warn("[siem_export] No hay filas para exportar");
        return "";
      }

      // Campos que queremos en el CSV (label CSV, clave JSON)
      const FIELDS = [
        ["Time", "Time"],
        ["Alert Severity", "Alert Severity"],
        ["Application Details", "Application Details"],
        ["Common Report Name", "Common Report Name"],
        ["Destination Country", "Destination Country"],
        ["Destination IP", "Destination IP"],
        ["Destination Interface", "Destination Interface"],
        ["Destination Port", "Destination Port"],
        ["Display Name", "Display Name"],
        ["Duration", "Duration"],
        ["Event ID", "Event ID"],
        ["Event Name", "Event Name"],
        ["Facility", "Facility"],
        ["Log Source", "Log Source"],
        ["Log Source Type", "Log Source Type"],
        ["Profile Name", "Profile Name"],
        ["Received Bytes", "Received Bytes"],
        ["Sent Bytes", "Sent Bytes"],
        ["Service", "Service"],
        ["Session Id", "Session Id"],
        ["Severity", "Severity"],
        ["Source", "Source"],
        ["Source Country", "Source Country"],
        ["Source IP", "Source IP"],
        ["Source Interface", "Source Interface"],
        ["Source Port", "Source Port"],
        ["Threat Categories", "Threat Categories"],
        ["Threat Reputation", "Threat Reputation"],
        ["Threat Source", "Threat Source"],
        ["Transmission Protocol", "Transmission Protocol"],
        ["Type", "Type"],
        ["uuid", "uuid"],
        // Campo extra: etiqueta de dispositivo construida en el back
        ["Device Label", "__device_label__"],
      ];

      const rows = [];

      // Cabecera CSV
      rows.push(FIELDS.map(([label]) => label));

      // Filas de datos
      trs.forEach((tr) => {
        let alertObj = null;
        const rawJson = tr.dataset.raw || "";

        if (rawJson) {
          try {
            alertObj = JSON.parse(rawJson);
          } catch (e) {
            console.warn(
              "[siem_export] No se pudo parsear data-raw como JSON",
              e
            );
          }
        }

        const row = FIELDS.map(([label, key]) => {
          // Device Label: priorizar data-device del <tr> (por si está más limpio)
          if (key === "__device_label__") {
            const dev = tr.dataset.device || getField(alertObj, key);
            return escapeCsvField(dev);
          }
          const val = getField(alertObj, key);
          return escapeCsvField(val);
        });

        rows.push(row);
      });

      return rows.map((row) => row.join(",")).join("\r\n");
    }

    function downloadCsvCurrent() {
      showLoader("Generando CSV…");
      try {
        const csv = buildCsvFromTable();
        if (!csv) {
          alert("No hay datos para exportar.");
          return;
        }

        const today = new Date().toISOString().slice(0, 10);
        const filename = `siem_alertas_detalle_${today}.csv`;

        const blob = new Blob([csv], {
          type: "text/csv;charset=utf-8;",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();

        setTimeout(() => {
          URL.revokeObjectURL(url);
          a.remove();
        }, 2000);
      } catch (err) {
        console.error("[siem_export] Error generando CSV", err);
        alert("No se pudo generar el CSV. Intenta nuevamente.");
      } finally {
        hideLoader();
      }
    }

    // ───────────── Eventos ─────────────
    toggleBtn.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      toggleMenu();
    });

    menu.addEventListener("click", function (ev) {
      const el = ev.target.closest("button, a");
      if (!el) return;

      const scope = el.dataset.exportScope || "current";
      ev.preventDefault();
      closeMenu();

      if (scope === "current") {
        downloadCsvCurrent();
      }
    });

    document.addEventListener("click", function (ev) {
      if (!menuOpen) return;
      if (ev.target === toggleBtn || menu.contains(ev.target)) return;
      closeMenu();
    });

    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") {
        closeMenu();
      }
    });
  });
})();
