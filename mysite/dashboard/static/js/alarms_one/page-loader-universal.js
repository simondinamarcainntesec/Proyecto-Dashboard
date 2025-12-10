// static/js/alarms_one/page-loader-universal.js
(function () {
  let hideTimer = null;

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

    // Safety: si algo sale mal, se apaga solo
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      const current = document.getElementById('loading-overlay');
      if (current) current.classList.remove('is-active');
    }, 8000);
  };

  const hide = () => {
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
    const ov = document.getElementById('loading-overlay');
    if (!ov) return;
    ov.classList.remove('is-active');
  };

  // Observa la modal de IP: cuando se haga visible, apagamos el loader
  const watchIpModal = () => {
    const ipModal = document.getElementById('ipSearchModal');
    if (!ipModal) return;

    const checkVisible = () => {
      const isHiddenClass = ipModal.classList.contains('hidden');
      const ariaHidden = ipModal.getAttribute('aria-hidden');
      // Visible cuando NO tiene "hidden" y aria-hidden es "false" o null
      if (!isHiddenClass && ariaHidden !== 'true') {
        hide();
      }
    };

    // Check inicial (por si ya se renderiza visible desde el backend)
    checkVisible();

    // Observamos cambios de clase / aria-hidden
    const observer = new MutationObserver(checkVisible);
    observer.observe(ipModal, {
      attributes: true,
      attributeFilter: ['class', 'aria-hidden'],
    });
  };

  const bindHandlers = () => {
    // Al cargar la página actual, empezamos con el overlay apagado
    hide();

    // --- BÚSQUEDA DE IP (formularios .home-ip-form) ---
    document.addEventListener('submit', (e) => {
      const form = e.target;
      if (form && form.matches('.home-ip-form')) {
        // Da igual si es AJAX o navegación normal, mostramos loader
        show('Buscando IP…');
      }
    });

    // --- Botón Actualizar ---
    const refreshBtn = document.getElementById('btn-refresh');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', (e) => {
        // Si otro script cancela el click, igual mostramos loader
        show('Actualizando datos…');
      });
    }

    // --- Navegaciones genéricas ---
    window.addEventListener('beforeunload', () => {
      show();
    });

    window.addEventListener('pageshow', () => hide());
    window.addEventListener('load', () => hide());

    // Vigilar la modal de resultados de IP
    watchIpModal();
  };

  // Exponer helpers por si otro JS quiere usarlos
  window.PageLoader = { show, hide };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindHandlers);
  } else {
    bindHandlers();
  }
})();
