// Controla el overlay "Cargando datos…" en navegación y submits
(function () {
  const overlay = document.getElementById('loading-overlay');
  if (!overlay) return;

  const show = () => overlay.classList.add('is-active');
  const hide = () => overlay.classList.remove('is-active');

  // Ocultar apenas la página está lista
  window.addEventListener('DOMContentLoaded', hide);
  window.addEventListener('load', hide);
  window.addEventListener('pageshow', hide);

  // Mostrar al navegar vía <a> (misma pestaña)
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a');
    if (!a) return;

    // Evitar si abre en nueva pestaña o con modificadores
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (a.target && a.target !== '' && a.target !== '_self') return;

    const href = a.getAttribute('href') || '';
    if (href.startsWith('#') || href.startsWith('javascript:')) return;

    show();
  });

  // Mostrar al enviar formularios
  document.addEventListener('submit', () => { show(); }, true);

  // Botones que fuerzan navegación JS (usa data-loading="instant")
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-loading="instant"]');
    if (btn) show();
  });

  // Fallback extra por si el navegador tarda en descargar
  window.addEventListener('beforeunload', () => { show(); });
})();
