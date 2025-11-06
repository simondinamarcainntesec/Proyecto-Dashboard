(function () {
  const ensureOverlay = () => {
    let ov = document.getElementById('loading-overlay');
    if (!ov) {
      ov = document.createElement('div');
      ov.id = 'loading-overlay';
      ov.setAttribute('role', 'status');
      ov.setAttribute('aria-live', 'polite');
      ov.innerHTML = `
        <div class="loading-card">
          <div class="spinner" aria-hidden="true"></div>
          <div class="loading-text">Cargando datos…</div>
        </div>`;
      document.body.appendChild(ov);
    }
    return ov;
  };

  const show = (msg = 'Cargando datos…') => {
    const ov = ensureOverlay();
    const txt = ov.querySelector('.loading-text');
    if (txt) txt.textContent = msg;
    ov.classList.add('is-active'); 
  };

  const hide = () => {
    const ov = document.getElementById('loading-overlay');
    if (!ov) return;
    ov.classList.remove('is-active');
  };

  const bindHandlers = () => {
    hide();

 
    document.addEventListener('click', (e) => {
      const a = e.target.closest('a');
      if (!a) return;

      // evitar modificadores o externos
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      if (a.target && a.target !== '' && a.target !== '_self') return;
      const href = a.getAttribute('href') || '';
      if (href.startsWith('#') || href.startsWith('javascript:')) return;

     
      show();
      const start = performance.now();
      while (performance.now() - start < 35) {} 
    });

    // --- formularios ---
    document.addEventListener('submit', () => show(), true);

    // --- botones con data-loading ---
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-loading="instant"]');
      if (btn) show('Actualizando datos…');
    });

    // --- F5 / Ctrl+R ---
    window.addEventListener('keydown', (e) => {
      const isF5 = e.key === 'F5';
      const isReloadCombo = (e.key === 'r' || e.key === 'R') && (e.ctrlKey || e.metaKey);
      if (isF5 || isReloadCombo) show('Recargando…');
    });

    // --- beforeunload / pageshow ---
    window.addEventListener('beforeunload', () => show());
    window.addEventListener('pageshow', hide);
    window.addEventListener('load', hide);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindHandlers);
  } else {
    bindHandlers();
  }
})();
