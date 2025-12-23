(function () {
  const Q = (s, r = document) => r.querySelector(s);
  const QA = (s, r = document) => Array.from(r.querySelectorAll(s));

  const form = Q('#date-filter');
  const inpFrom = Q('#inp-from');
  const inpTo = Q('#inp-to');

  if (!form) return;

  const DEBUG = false;
  const log = (...a) => DEBUG && console.log('[DATE_FILTERS]', ...a);

  function normalizeDateStr(s) {
    const v = String(s || '').trim();
    return /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : '';
  }

  // Cuando tocas un chip, limpia fechas ANTES del submit
  // para que no se “cuelgue” en custom por from/to antiguos.
  QA('.chip-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      // Solo chips de periodo (name=period value=...)
      if (btn.name !== 'period') return;

      if (inpFrom) inpFrom.value = '';
      if (inpTo) inpTo.value = '';

      // deja que el submit normal ocurra
      log('chip submit period=', btn.value);
    }, true);
  });

  // Si el usuario pone ambas fechas, fuerza period=50 (en URL igual vendrán from/to)
  function hasBothDates() {
    const from = normalizeDateStr(inpFrom?.value);
    const to = normalizeDateStr(inpTo?.value);
    return !!(from && to);
  }

  // Enviar “Aplicar”:
  // - si hay ambas fechas: ok, submit normal con from/to
  // - si no: evita mandar from/to sueltos (limpia)
  form.addEventListener('submit', () => {
    if (!hasBothDates()) {
      if (inpFrom && !normalizeDateStr(inpFrom.value)) inpFrom.value = '';
      if (inpTo && !normalizeDateStr(inpTo.value)) inpTo.value = '';
    }
  }, true);
})();
