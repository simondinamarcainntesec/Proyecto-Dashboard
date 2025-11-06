// static/js/user_dropdown.js

document.addEventListener("DOMContentLoaded", () => {
  // === Dropdown del usuario ===
  const userMenu = document.getElementById("userMenu");
  const userButton = document.getElementById("userButton");
  const userDropdown = userMenu?.querySelector(".dropdown-menu");

  // === Dropdown del tenant (usa <details>) ===
  const tenantDropdown = document.querySelector(".tenant-dropdown");

  // --- Apertura / cierre del menú de usuario ---
  if (userButton && userMenu) {
    userButton.addEventListener("click", (e) => {
      e.stopPropagation();
      userMenu.classList.toggle("dropdown-open");
    });
  }

  // --- Cierre global al hacer clic fuera ---
  document.addEventListener("click", (e) => {
    const clickInsideUser = userMenu && userMenu.contains(e.target);
    const clickInsideTenant = tenantDropdown && tenantDropdown.contains(e.target);

    // Si el clic no fue dentro de ninguno de los menús, los cerramos
    if (!clickInsideUser && !clickInsideTenant) {
      userMenu?.classList.remove("dropdown-open");
      if (tenantDropdown && tenantDropdown.hasAttribute("open")) {
        tenantDropdown.removeAttribute("open");
      }
    }
  });

  // --- Cierra también con tecla Esc ---
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      userMenu?.classList.remove("dropdown-open");
      tenantDropdown?.removeAttribute("open");
    }
  });
});
