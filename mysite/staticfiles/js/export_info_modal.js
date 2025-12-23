// static/js/site24x7/export_info_modal.js
(function () {
  const Q = (s, r = document) => r.querySelector(s);
  const QA = (s, r = document) => Array.from(r.querySelectorAll(s));

  // Si no existe el export en esta página, salimos.
  const exportWrapper = Q('#exportWrapper');
  const btnToggle = Q('#btn-export-toggle');
  const menu = Q('#export-menu');
  const modal = Q('#exportInfoModal');
  const okBtn = Q('#btn-export-info-ok');

  if (!exportWrapper || !btnToggle || !menu || !modal || !okBtn) return;

  function openMenu() {
    menu.style.display = 'block';
    exportWrapper.setAttribute('data-open', '1');
  }
  function closeMenu() {
    menu.style.display = 'none';
    exportWrapper.removeAttribute('data-open');
  }
  function toggleMenu() {
    const isOpen = exportWrapper.getAttribute('data-open') === '1';
    if (isOpen) closeMenu();
    else openMenu();
  }

  function openModal() {
    document.body.classList.add('modal-open');
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
  }

  function closeModal() {
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');

    // Solo removemos modal-open si no quedan modales abiertos
    const anyOpen = QA('.modal').some(m => !m.classList.contains('hidden'));
    if (!anyOpen) document.body.classList.remove('modal-open');
  }

  // Toggle dropdown export
  btnToggle.addEventListener('click', function (e) {
    e.preventDefault();
    e.stopPropagation();
    toggleMenu();
  });

  // Click fuera => cerrar dropdown
  document.addEventListener('click', function () {
    closeMenu();
  });

  // Click en PDF/CSV => NO exporta, abre modal
  menu.addEventListener('click', function (e) {
    const btn = e.target && e.target.closest && e.target.closest('[data-export-format]');
    if (!btn) return;

    e.preventDefault();
    e.stopPropagation();
    closeMenu();
    openModal();
  });

  // OK cierra modal
  okBtn.addEventListener('click', closeModal);

  // Cerrar modal por backdrop / X
  modal.addEventListener('click', function (e) {
    if (e.target && e.target.matches('[data-close-export-info]')) closeModal();
  });

  // ESC cierra modal
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) closeModal();
  });
})();
