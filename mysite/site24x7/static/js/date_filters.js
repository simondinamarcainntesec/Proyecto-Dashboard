(function () {
  const Q = (s, r = document) => r.querySelector(s);
  const QA = (s, r = document) => Array.from(r.querySelectorAll(s));

  const form = Q('#date-filter');
  const inpFrom = Q('#inp-from');
  const inpTo = Q('#inp-to');
  const inpPeriod = Q('#inp-period');

  if (!form || !inpPeriod) return;

  const DEBUG = false;
  const log = (...a) => DEBUG && console.log('[DATE_FILTERS]', ...a);

  function normalizeDateStr(s) {
    const v = String(s || '').trim();
    return /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : '';
  }

  function setActiveChipByPeriod(periodValue) {
    // Compatible con:
    // 1) data-period (si lo agregas después)
    // 2) name="period" value="X" (tu caso actual)
    QA('.chip-btn').forEach(btn => {
      const p = btn.dataset?.period || btn.value || btn.getAttribute('value') || '';
      btn.classList.toggle('is-active', String(p) === String(periodValue));
    });
  }

  function clearActiveChips() {
    QA('.chip-btn').forEach(btn => btn.classList.remove('is-active'));
  }

  function navigateClean(params) {
    const url = new URL(window.location.href);

    // limpia SOLO lo de fechas (conserva otros params si existieran)
    url.searchParams.delete('period');
    url.searchParams.delete('from');
    url.searchParams.delete('to');

    if (params.period) url.searchParams.set('period', String(params.period));
    if (params.from) url.searchParams.set('from', params.from);
    if (params.to) url.searchParams.set('to', params.to);

    log('NAV ->', url.toString());
    window.location.href = url.toString();
  }

  function forceCustomIfBothDates() {
    const from = normalizeDateStr(inpFrom?.value);
    const to = normalizeDateStr(inpTo?.value);

    if (from && to) {
      // swap si vienen al revés
      if (from > to) {
        inpFrom.value = to;
        inpTo.value = from;
      }
      inpPeriod.value = '50';
      clearActiveChips();
      return true;
    }
    return false;
  }

  // Init: carga desde URL y aplica estado visual
  (function initFromUrl() {
    const params = new URLSearchParams(window.location.search);

    const urlFrom = normalizeDateStr(params.get('from'));
    const urlTo = normalizeDateStr(params.get('to'));
    let p = (params.get('period') || '3').trim() || '3';

    if (inpFrom) inpFrom.value = urlFrom || '';
    if (inpTo) inpTo.value = urlTo || '';

    // si vienen from/to en URL => custom sí o sí
    if (urlFrom && urlTo) {
      p = '50';
      inpPeriod.value = '50';
      clearActiveChips();
    } else {
      inpPeriod.value = p;
      setActiveChipByPeriod(p);
    }
  })();

  // Chips: (tu HTML actual no tiene data-period, así que tomamos btn.value)
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.chip-btn');
    if (!btn) return;

    // solo si es botón de periodo (name="period" o data-period)
    const p = btn.dataset?.period || btn.value || btn.getAttribute('value');
    if (!p) return;

    e.preventDefault();
    e.stopPropagation();

    inpPeriod.value = String(p);

    if (inpFrom) inpFrom.value = '';
    if (inpTo) inpTo.value = '';

    setActiveChipByPeriod(p);
    navigateClean({ period: p });
  }, true);

  // cambios manuales de fecha => period=50
  inpFrom?.addEventListener('change', forceCustomIfBothDates);
  inpTo?.addEventListener('change', forceCustomIfBothDates);

  // Submit manual
  form.addEventListener('submit', (e) => {
    const didCustom = forceCustomIfBothDates();
    if (didCustom) return; // deja que el form haga GET normal con period=50

    // Si no hay rango completo, evita mandar from=&to=
    e.preventDefault();
    const p = (inpPeriod.value || '3').trim() || '3';
    navigateClean({ period: p });
  });

  // Refresh
  Q('#btn-refresh')?.addEventListener('click', () => window.location.reload());
})();
