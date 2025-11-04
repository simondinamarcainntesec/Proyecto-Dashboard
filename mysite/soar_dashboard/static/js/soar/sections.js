// static/js/soar/sections.js
(function () {
  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  const chips        = $$('.section-chips .chip');
  const gridSelector = '.grid-main';
  const cardSelector = '.grid-main .card';
  const norm = (v) => String(v || '').toLowerCase().trim();

  // ---------- Overlay liviano "recalculando" ----------
  function ensureRecalcOverlay() {
    const grid = $(gridSelector);
    if (!grid) return null;

    let overlay = grid.querySelector('.recalc-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'recalc-overlay';
      overlay.innerHTML = `
        <div style="display:flex; flex-direction:column; align-items:center;">
          <div class="recalc-spinner" aria-hidden="true"></div>
          <div class="recalc-text" aria-live="polite">Cargando datos…</div>
        </div>
      `;
      grid.appendChild(overlay);
    }
    return overlay;
  }

  function showRecalc(ms = 420) {
    const grid = $(gridSelector);
    const ov   = ensureRecalcOverlay();
    if (!grid || !ov) return () => {};

    grid.classList.add('recalc-busy');
    ov.classList.add('is-visible');

    let closed = false;
    const hide = () => {
      if (closed) return;
      closed = true;
      ov.classList.remove('is-visible');
      grid.classList.remove('recalc-busy');
    };

    // fallback auto-cierre
    const t = setTimeout(hide, ms);
    return () => { clearTimeout(t); hide(); };
  }

  // ---------- Helpers sección ----------
  function parseGroups(el) {
    return new Set(
      norm(el.getAttribute('data-groups') || '')
        .split(',')
        .map(s => s.trim())
        .filter(Boolean)
    );
  }

  function getActiveSec() {
    const params = new URLSearchParams(window.location.search);
    return norm(params.get('sec') || ($('.section-chips .chip.active')?.dataset.sec) || 'all');
  }

  function setActiveChip(sec) {
    const val = norm(sec || 'all');
    $$('.section-chips .chip').forEach(c =>
      c.classList.toggle('active', norm(c.dataset.sec || 'all') === val)
    );
  }

  function persistSec(sec) {
    const params = new URLSearchParams(window.location.search);
    params.set('sec', norm(sec || 'all'));
    const url = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, '', url);
  }

  // ---------- Aplicar sección (con/ sin animación) ----------
  function applySection(sec, { animate = true } = {}) {
    const val = norm(sec || 'all');
    document.body.setAttribute('data-active-sec', val);

    const cards = $$(cardSelector);
    const isAll = (val === 'all');

    if (!animate) {
      // Sin animación (p.ej. al cargar la página)
      cards.forEach(card => {
        const willShow = isAll ? true : parseGroups(card).has(val);
        if (willShow) {
          card.style.display = '';
          card.removeAttribute('hidden');
          card.removeAttribute('aria-hidden');
          card.classList.remove('is-fade-in', 'is-fade-out', 'show');
        } else {
          card.style.display = 'none';
          card.setAttribute('hidden', '');
          card.setAttribute('aria-hidden', 'true');
          card.classList.remove('is-fade-in', 'is-fade-out', 'show');
        }
      });
      // Resize silencioso
      setTimeout(() => window.dispatchEvent(new Event('resize')), 0);
      return;
    }

    // Con animación (cuando el usuario hace clic)
    // fase 1: fade-out de las que serán ocultadas
    cards.forEach(card => {
      const willShow = isAll ? true : parseGroups(card).has(val);
      card.classList.remove('is-fade-in', 'show');
      if (!willShow && card.style.display !== 'none') {
        card.classList.add('is-fade-out');
      }
    });

    // fase 2: aplicar display + fade-in a las que se muestran
    requestAnimationFrame(() => {
      cards.forEach(card => {
        const willShow = isAll ? true : parseGroups(card).has(val);

        if (willShow) {
          card.style.display = '';
          card.removeAttribute('hidden');
          card.removeAttribute('aria-hidden');

          card.classList.remove('is-fade-out');
          card.classList.add('is-fade-in');
          requestAnimationFrame(() => card.classList.add('show'));
        } else {
          card.classList.remove('is-fade-in', 'show');
          card.setAttribute('hidden', '');
          card.setAttribute('aria-hidden', 'true');
          card.style.display = 'none';
        }
      });

      setTimeout(() => window.dispatchEvent(new Event('resize')), 0);
    });
  }

  function setSection(sec, { animate = true } = {}) {
    const val = norm(sec || 'all');

    // Solo mostrar overlay/animación si animate === true (clic del usuario)
    let done = () => {};
    if (animate) done = showRecalc();

    setActiveChip(val);
    persistSec(val);
    applySection(val, { animate });

    // cerrar overlay un poco después
    if (animate) setTimeout(done, 280);
  }

  // ---------- Eventos ----------
  chips.forEach(chip => {
    chip.addEventListener('click', () => setSection(chip.dataset.sec, { animate: true }));
  });

  // Reaplicar si el grid cambia (re-render) — sin animación
  const gridMain = $(gridSelector);
  if (gridMain) {
    const observer = new MutationObserver(() => applySection(getActiveSec(), { animate: false }));
    observer.observe(gridMain, { childList: true, subtree: true });
  }

  // ---------- Init (sin animación) ----------
  (function init() {
    // Creamos overlay una vez (no lo mostramos)
    ensureRecalcOverlay();
    const initial = getActiveSec();
    setSection(initial, { animate: false }); // <-- sin overlay/animación al cargar
  })();
})();
