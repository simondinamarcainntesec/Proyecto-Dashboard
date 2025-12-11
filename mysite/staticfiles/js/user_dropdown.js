// static/js/user_dropdown.js

document.addEventListener("DOMContentLoaded", () => {
  // === Menú del usuario ===
  const userMenu = document.getElementById("userMenu");
  const userButton = document.getElementById("userButton");
  const userDropdown = userMenu
    ? userMenu.querySelector(".dropdown-menu")
    : null;

  // === TODOS los <details> que actúan como dropdowns (topbar y/o sidebar) ===
  const detailDropdowns = Array.from(
    document.querySelectorAll("details.tenant-dropdown")
  );
  // Solo los del sidebar (tienen nav-dropdown)
  const navDropdowns = detailDropdowns.filter((dd) =>
    dd.classList.contains("nav-dropdown")
  );

  // Utilidad: cerrar TODO (usuario + <details>), excepto uno opcional
  const closeAllExcept = (exceptEl = null) => {
    // Cierra menú de usuario si no es la excepción
    if (userMenu && exceptEl !== userMenu) {
      userMenu.classList.remove("dropdown-open");
      if (userDropdown) {
        userDropdown.style.display = "none";
      }
    }

    // Cierra todos los <details> si no son la excepción
    detailDropdowns.forEach((dd) => {
      if (dd !== exceptEl) {
        dd.removeAttribute("open");
      }
    });
  };

  // ---------- ESTADO INICIAL: todo CERRADO en el sidebar ----------
  navDropdowns.forEach((dd) => dd.removeAttribute("open"));
  // ---------------------------------------------------------------

  // --- Click en el botón del usuario ---
  if (userButton && userMenu && userDropdown) {
    userButton.addEventListener("click", (e) => {
      e.stopPropagation();

      const isOpen = userMenu.classList.contains("dropdown-open");
      const willOpen = !isOpen;

      if (willOpen) {
        // Se va a abrir → cerramos todo lo demás
        closeAllExcept(userMenu);
        userMenu.classList.add("dropdown-open");
        userDropdown.style.display = "block";
      } else {
        // Estaba abierto → lo cerramos
        userMenu.classList.remove("dropdown-open");
        userDropdown.style.display = "none";
      }
    });
  }

  // --- Cuando se abre un <details>, cierra los demás ---
  detailDropdowns.forEach((dd) => {
    dd.addEventListener("toggle", () => {
      if (dd.open) {
        // Si este se abrió, cierra el resto y el menú de usuario
        closeAllExcept(dd);
      }
    });
  });

  // --- Cierre global al hacer clic fuera ---
  document.addEventListener("click", (e) => {
    const t = e.target;

    const clickInsideUser = userMenu && userMenu.contains(t);
    const clickInsideAnyDetail = detailDropdowns.some((dd) =>
      dd.contains(t)
    );

    // Si el clic NO fue dentro de ninguno, cerramos todo
    if (!clickInsideUser && !clickInsideAnyDetail) {
      closeAllExcept(null);
    }
  });

  // --- Cierra también con tecla Esc ---
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAllExcept(null);
    }
  });
});
