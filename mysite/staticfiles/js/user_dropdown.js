// static/js/user_dropdown.js

document.addEventListener("DOMContentLoaded", () => {
  // === Menú del usuario ===
  const userMenu = document.getElementById("userMenu");
  const userButton = document.getElementById("userButton");

  // === TODOS los <details> que actúan como dropdowns (topbar y/o sidebar) ===
  const detailDropdowns = Array.from(document.querySelectorAll("details.tenant-dropdown"));

  // Utilidad: cerrar todo excepto el que indiquemos como "exceptEl"
  const closeAllExcept = (exceptEl = null) => {
    // Cierra menú de usuario si no es la excepción
    if (userMenu && exceptEl !== userMenu) {
      userMenu.classList.remove("dropdown-open");
    }
    // Cierra todos los <details> si no son la excepción
    detailDropdowns.forEach((dd) => {
      if (dd !== exceptEl) dd.removeAttribute("open");
    });
  };

  // --- Click en el botón del usuario ---
  if (userButton && userMenu) {
    userButton.addEventListener("click", (e) => {
      e.stopPropagation();
      const willOpen = !userMenu.classList.contains("dropdown-open");

      // Si se va a abrir el usuario, cierra los demás primero
      if (willOpen) {
        closeAllExcept(userMenu);
        userMenu.classList.add("dropdown-open");
      } else {
        // Si estaba abierto, lo cerramos
        userMenu.classList.remove("dropdown-open");
      }
    });
  }

  // --- Cuando se abre un <details>, cierra todos los demás ---
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
    const clickInsideAnyDetail = detailDropdowns.some((dd) => dd.contains(t));

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
