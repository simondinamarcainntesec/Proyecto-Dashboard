// static/js/menus_dropdowns.js

document.addEventListener('DOMContentLoaded', () => {
  // ==============================
  // MENÚ USUARIO (esquina superior derecha)
  // ==============================
  const userMenu   = document.getElementById('userMenu');
  const userButton = document.getElementById('userButton');

  if (userMenu && userButton) {
    userButton.addEventListener('click', (event) => {
      event.stopPropagation(); // evita que el click burbujee al document
      userMenu.classList.toggle('is-open');
    });
  }

  // ==============================
  // DROPDOWNS <details> (sidebar + tenant)
  // ==============================
  const allDetails   = Array.from(document.querySelectorAll('details.tenant-dropdown'));
  const navDropdowns = Array.from(
    document.querySelectorAll('details.tenant-dropdown.nav-dropdown')
  );

  // ---------- ESTADO INICIAL (acordeón al cargar) ----------
  if (navDropdowns.length > 0) {
    // buscamos el dropdown cuyo summary tenga .nav-item.is-active
    const activeDropdown = navDropdowns.find((det) =>
      det.querySelector('summary.nav-item.is-active')
    );

    if (activeDropdown) {
      navDropdowns.forEach((det) => {
        det.open = (det === activeDropdown);
      });
    } else {
      // si ninguno está activo, los cerramos todos
      navDropdowns.forEach((det) => {
        det.open = false;
      });
    }
  }
  // ---------------------------------------------------------

  // Cerrar otros dropdowns de la sidebar cuando uno se abre (modo acordeón)
  navDropdowns.forEach((dropdown) => {
    dropdown.addEventListener('toggle', () => {
      if (dropdown.open) {
        navDropdowns.forEach((other) => {
          if (other !== dropdown && other.open) {
            other.open = false;
          }
        });
      }
    });
  });

  // ==============================
  // CLICK GLOBAL → CERRAR TODO
  // ==============================
  document.addEventListener('click', (event) => {
    const target = event.target;

    // 1) Cerrar menú de usuario si haces click fuera
    if (userMenu && !userMenu.contains(target)) {
      userMenu.classList.remove('is-open');
    }

    // 2) Cerrar todos los <details> si haces click fuera de cada uno
    allDetails.forEach((det) => {
      if (det.open && !det.contains(target)) {
        det.open = false;
      }
    });
  });

  // ==============================
  // ESC → CERRAR TODO
  // ==============================
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      if (userMenu) userMenu.classList.remove('is-open');
      allDetails.forEach((det) => {
        if (det.open) det.open = false;
      });
    }
  });
});
