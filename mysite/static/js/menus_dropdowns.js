// static/js/menus_dropdowns.js
document.addEventListener("DOMContentLoaded", () => {
  // =========================
  // Storage (persistencia sidebar)
  // =========================
  const STORAGE_KEY = "inntesec.sidebar.openNavDropdownId"; // null => sin preferencia; "" => ninguno abierto; "id" => ese abierto

  const getStoredOpenId = () => {
    try {
      return localStorage.getItem(STORAGE_KEY); // puede ser null / "" / "..."
    } catch (e) {
      return null;
    }
  };

  const setStoredOpenId = (val) => {
    try {
      if (val === null) localStorage.removeItem(STORAGE_KEY);
      else localStorage.setItem(STORAGE_KEY, String(val));
    } catch (e) {
      // ignore
    }
  };

  // =========================
  // User menu (perfil)
  // =========================
  const userMenu = document.getElementById("userMenu");
  const userButton = document.getElementById("userButton");
  const userDropdown = userMenu ? userMenu.querySelector(".dropdown-menu") : null;

  // =========================
  // Export menu (Home / Site24x7 / etc.)
  // =========================
  const exportToggleBtn =
    document.getElementById("homeExportToggleBtn") ||
    document.getElementById("btn-export-toggle");

  const exportMenu =
    document.getElementById("homeExportMenu") ||
    document.getElementById("export-menu");

  const exportWrapper = exportToggleBtn
    ? exportToggleBtn.closest(".export-wrapper")
    : exportMenu
      ? exportMenu.closest(".export-wrapper")
      : null;

  // =========================
  // Details dropdowns (tenant + sidebar)
  // =========================
  const detailDropdowns = Array.from(document.querySelectorAll("details.tenant-dropdown"));

  // Sidebar nav dropdowns
  const navDropdowns = detailDropdowns.filter((dd) => dd.classList.contains("nav-dropdown"));

  // No-sidebar details (ej: tenant selector topbar)
  const nonNavDetails = detailDropdowns.filter((dd) => !dd.classList.contains("nav-dropdown"));

  // =========================
  // Helpers: identificar cada nav dropdown
  // =========================
  function getNavDropdownId(dd) {
    if (!dd) return "";
    if (dd.dataset.navId) return dd.dataset.navId;

    const summary = dd.querySelector("summary");
    const fromSummaryId = summary && summary.id ? summary.id.trim() : "";
    const fromDetailsId = dd.id ? dd.id.trim() : "";
    const fallback = "navdd-" + navDropdowns.indexOf(dd);

    const id = fromSummaryId || fromDetailsId || fallback;
    dd.dataset.navId = id;
    return id;
  }

  function findNavDropdownById(id) {
    if (!id) return null;
    return navDropdowns.find((dd) => getNavDropdownId(dd) === id) || null;
  }

  // =========================
  // User menu open/close
  // =========================
  const closeUserMenu = () => {
    if (!userMenu) return;
    userMenu.classList.remove("dropdown-open");
    if (userDropdown) userDropdown.style.display = "none"; // fallback
    if (userButton) userButton.setAttribute("aria-expanded", "false");
  };

  const openUserMenu = () => {
    if (!userMenu || !userDropdown) return;
    userMenu.classList.add("dropdown-open");
    userDropdown.style.display = "block"; // fallback
    if (userButton) userButton.setAttribute("aria-expanded", "true");
  };

  // =========================
  // Export open/close
  // =========================
  const closeExportMenu = () => {
    if (!exportWrapper) return;
    exportWrapper.classList.remove("is-open");
    if (exportToggleBtn) exportToggleBtn.setAttribute("aria-expanded", "false");
    if (exportMenu) {
      exportMenu.setAttribute("aria-hidden", "true");
      exportMenu.classList.remove("is-open");
    }
  };

  const openExportMenu = () => {
    if (!exportWrapper) return;
    exportWrapper.classList.add("is-open");
    if (exportToggleBtn) exportToggleBtn.setAttribute("aria-expanded", "true");
    if (exportMenu) {
      exportMenu.setAttribute("aria-hidden", "false");
      exportMenu.classList.add("is-open");
    }
  };

  // =========================
  // Sidebar accordion (SIN animaciones)
  // - Abre uno => cierra los demás (instantáneo)
  // - Cierra => queda cerrado
  // - Persistencia: guarda el último abierto o ninguno
  // =========================
  function closeAllNavDropdownsInstant(except = null) {
    navDropdowns.forEach((dd) => {
      if (except && dd === except) return;
      dd.removeAttribute("open");
    });
  }

  // Interceptar click del summary SOLO en nav-dropdowns (sin animación)
  navDropdowns.forEach((dd) => {
    const summary = dd.querySelector("summary");
    if (!summary) return;

    summary.addEventListener("click", (e) => {
      // Evitar toggle nativo para mantener control tipo acordeón
      e.preventDefault();
      e.stopPropagation();

      const isOpen = dd.hasAttribute("open");

      if (isOpen) {
        // Cerrar
        dd.removeAttribute("open");

        // Persistir: si este era el guardado, marcar “ninguno”
        const stored = getStoredOpenId();
        const myId = getNavDropdownId(dd);
        if (stored === myId) setStoredOpenId("");
      } else {
        // Abrir y cerrar otros
        closeAllNavDropdownsInstant(dd);
        dd.setAttribute("open", "");

        // Persistir: este quedó abierto
        setStoredOpenId(getNavDropdownId(dd));
      }
    });
  });

  // =========================
  // Restaurar estado guardado (si existe)
  // - null: no hay preferencia => respeta backend
  // - "": el usuario dejó todo cerrado => cerrar todos
  // - "id": abrir ese y cerrar el resto
  // =========================
  (function restoreNavState() {
    const stored = getStoredOpenId();

    if (stored === null) {
      // Sin preferencia: no tocar (respetar open del backend)
      return;
    }

    if (stored === "") {
      closeAllNavDropdownsInstant(null);
      return;
    }

    const target = findNavDropdownById(stored);
    if (!target) {
      // Si el id ya no existe, dejar todo cerrado
      closeAllNavDropdownsInstant(null);
      return;
    }

    // Abrir el guardado y cerrar el resto (instantáneo)
    closeAllNavDropdownsInstant(target);
  })();

  // =========================
  // Cierre de “cosas flotantes” (perfil/export/topbar tenant dropdown)
  // - NO cerramos nav dropdowns del sidebar al click afuera
  // =========================
  const closeNonNavDetails = () => {
    nonNavDetails.forEach((dd) => dd.removeAttribute("open"));
  };

  const closeAllFloating = () => {
    closeUserMenu();
    closeExportMenu();
    closeNonNavDetails();
  };

  // Estado inicial flotantes
  closeUserMenu();
  closeExportMenu();

  // User toggle
  if (userButton && userMenu && userDropdown) {
    userButton.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();

      const isOpen = userMenu.classList.contains("dropdown-open");
      closeExportMenu();
      closeNonNavDetails();

      if (isOpen) closeUserMenu();
      else openUserMenu();
    });

    userDropdown.addEventListener("click", (e) => e.stopPropagation());
  }

  // Export toggle
  if (exportToggleBtn && exportWrapper && exportMenu) {
    exportToggleBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();

      const isOpen = exportWrapper.classList.contains("is-open");
      closeUserMenu();
      closeNonNavDetails();

      if (isOpen) closeExportMenu();
      else openExportMenu();
    });

    exportMenu.addEventListener("click", (e) => e.stopPropagation());
  }

  // Cierre global (click fuera)
  document.addEventListener("click", (e) => {
    const t = e.target;

    const clickInsideUser = userMenu && userMenu.contains(t);
    const clickInsideExport = exportWrapper && exportWrapper.contains(t);
    const clickInsideAnyDetail = detailDropdowns.some((dd) => dd.contains(t));

    if (!clickInsideUser && !clickInsideExport && !clickInsideAnyDetail) {
      closeAllFloating();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAllFloating();
  });
});
