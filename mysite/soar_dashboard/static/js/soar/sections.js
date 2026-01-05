// static/js/soar/sections.js
(function () {
  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  const gridSelector = '.grid-main';
  const cardSelector = '.grid-main .card';
  const norm = (v) => String(v || '').toLowerCase().trim();

  // ✅ Chips: ahora son .soar-chip (fallback a .chip por compatibilidad)
  const chipSelector = '.section-chips .soar-chip, .section-chips .chip';
  const chips = $$(chipSelector);

  // Si no hay chips, no hacemos nada (evita errores en otras páginas)
  if (!chips.length) return;

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
    // ✅ Lee ?sec=... o el chip activo actual (soar-chip/chip)
    const activeChip = $(`${chipSelector}.active`);
    return norm(params.get('sec') || (activeChip?.dataset.sec) || 'all');
  }

  function setActiveChip(sec) {
    const val = norm(sec || 'all');
    $$(chipSelector).forEach(c => {
      c.classList.toggle('active', norm(c.dataset.sec || 'all') === val);
    });
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

      setTimeout(() => window.dispatchEvent(new Event('resize')), 0);
      return;
    }

    // fase 1: fade-out
    cards.forEach(card => {
      const willShow = isAll ? true : parseGroups(card).has(val);
      card.classList.remove('is-fade-in', 'show');
      if (!willShow && card.style.display !== 'none') {
        card.classList.add('is-fade-out');
      }
    });

    // fase 2: display + fade-in
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

    let done = () => {};
    if (animate) done = showRecalc();

    setActiveChip(val);
    persistSec(val);
    applySection(val, { animate });

    if (animate) setTimeout(done, 280);
  }

  // ---------- Eventos ----------
  chips.forEach(chip => {
    chip.addEventListener('click', () => setSection(chip.dataset.sec, { animate: true }));
  });

  // Reaplicar si cambia el grid (sin animación)
  const gridMain = $(gridSelector);
  if (gridMain) {
    const observer = new MutationObserver(() => applySection(getActiveSec(), { animate: false }));
    observer.observe(gridMain, { childList: true, subtree: true });
  }

  // ---------- Init (sin animación) ----------
  (function init() {
    ensureRecalcOverlay();
    const initial = getActiveSec();
    setSection(initial, { animate: false });
  })();
})();
