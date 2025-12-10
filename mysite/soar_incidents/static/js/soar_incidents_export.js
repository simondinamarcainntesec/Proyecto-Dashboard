// static/js/soar_incidents_export.js
// Menú desplegable de exportación CSV para SOAR – Incidentes

(function () {
  function getTodayStr() {
    const now = new Date();
    return now.toISOString().slice(0, 10); // YYYY-MM-DD
  }

  function getFilename(scope) {
    const dateStr = getTodayStr();
    const suffix = scope === "all" ? "todos" : "actuales";
    return `soar_incidentes_${suffix}_${dateStr}.csv`;
  }

  // Loader simple (usa el overlay global si existe)
  function showLoader(message) {
    try {
      if (
        window.InntesecPageLoader &&
        typeof window.InntesecPageLoader.show === "function"
      ) {
        window.InntesecPageLoader.show(message || "Generando archivo…");
        return;
      }
    } catch (e) {
      console.warn("[SOAR Export] InntesecPageLoader.show no disponible", e);
    }

    const ov = document.getElementById("loading-overlay");
    if (ov) {
      ov.classList.add("is-active");
      ov.style.opacity = "1";
      ov.style.visibility = "visible";
    }
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
      console.warn("[SOAR Export] InntesecPageLoader.hide no disponible", e);
    }

    const ov = document.getElementById("loading-overlay");
    if (ov) {
      ov.classList.remove("is-active");
      ov.style.opacity = "0";
      ov.style.visibility = "hidden";
    }
  }

  async function doExport(url, scope) {
    if (!url) {
      console.warn("[SOAR Export] URL vacía para scope:", scope);
      return;
    }

    showLoader(
      scope === "all"
        ? "Generando CSV con todos los incidentes…"
        : "Generando CSV con los incidentes actuales…"
    );

    try {
      const resp = await fetch(url, {
        method: "GET",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });

      if (!resp.ok) {
        throw new Error("HTTP " + resp.status);
      }

      const blob = await resp.blob();

      // Intentar leer filename del header
      let filename = getFilename(scope);
      const disp = resp.headers.get("Content-Disposition");
      if (disp) {
        const m = /filename="?([^"]+)"?/i.exec(disp);
        if (m && m[1]) {
          filename = m[1];
        }
      }

      const urlBlob = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = urlBlob;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        URL.revokeObjectURL(urlBlob);
        a.remove();
      }, 2000);
    } catch (err) {
      console.error("[SOAR Export] Error al exportar CSV", err);
      alert("No se pudo generar el archivo. Intenta nuevamente.");
    } finally {
      hideLoader();
    }
  }

  function setupExportMenu() {
    const toggleBtn = document.getElementById("soarExportToggleBtn");
    const menu = document.getElementById("soarExportMenu");

    if (!toggleBtn || !menu) {
      console.warn(
        "[SOAR Export] No se encontró el botón o el menú de exportación"
      );
      return;
    }

    let isOpen = false;

    function openMenu() {
      if (isOpen) return;
      menu.classList.add("is-open");
      toggleBtn.setAttribute("aria-expanded", "true");
      menu.setAttribute("aria-hidden", "false");
      isOpen = true;
    }

    function closeMenu() {
      if (!isOpen) return;
      menu.classList.remove("is-open");
      toggleBtn.setAttribute("aria-expanded", "false");
      menu.setAttribute("aria-hidden", "true");
      isOpen = false;
    }

    function toggleMenu() {
      if (isOpen) {
        closeMenu();
      } else {
        openMenu();
      }
    }

    // Click en la flecha
    toggleBtn.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      toggleMenu();
    });

    // Click en opciones del menú
    menu.addEventListener("click", function (ev) {
      const btn = ev.target.closest("button[data-export-url]");
      if (!btn) return;

      ev.preventDefault();

      const url = btn.dataset.exportUrl || "";
      const scope = btn.dataset.exportScope || "current";

      closeMenu();
      doExport(url, scope);
    });

    // Cerrar al hacer click fuera
    document.addEventListener("click", function (ev) {
      if (!isOpen) return;
      if (
        ev.target === toggleBtn ||
        toggleBtn.contains(ev.target) ||
        menu.contains(ev.target)
      ) {
        return;
      }
      closeMenu();
    });

    // Cerrar con ESC
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") {
        closeMenu();
      }
    });

    console.log("[SOAR Export] Menú de exportación inicializado");
  }

  document.addEventListener("DOMContentLoaded", setupExportMenu);
})();

