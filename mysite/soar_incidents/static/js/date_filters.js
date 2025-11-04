// static/js/date_filters.js
// Filtros de fecha (solo back). El buscador #q NO recarga la página.
(function () {
  const form = document.getElementById("filters-form");
  const fromInput = document.getElementById("inp-from");
  const toInput   = document.getElementById("inp-to");
  const chips = document.querySelectorAll(".chip-btn");
  const btnRefresh = document.getElementById("btn-refresh");

  if (!form) return;

  /* ===== Utils fechas ===== */
  function pad(n){ return String(n).padStart(2,'0'); }
  function toLocalIsoDate(dt){
    return dt.getFullYear()+'-'+pad(dt.getMonth()+1)+'-'+pad(dt.getDate());
  }
  function minusDays(dt, days){
    return new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()-days, dt.getHours(), dt.getMinutes(), dt.getSeconds());
  }
  function firstDayOfMonth(dt){
    return new Date(dt.getFullYear(), dt.getMonth(), 1, 0,0,0);
  }

  /* ===== Chips rápidas ===== */
  function setActiveChip(range){
    chips.forEach(c=>c.classList.toggle('is-active', c.dataset.range===range));
  }

  function submitPreservingDateOnly({page} = {}) {
    const params = new URLSearchParams(window.location.search);
    const f = (fromInput?.value || "").trim();
    const t = (toInput?.value || "").trim();

    params.delete('page');
    if (page) params.set('page', page);

    if (f) params.set('from', f); else params.delete('from');
    if (t) params.set('to', t); else params.delete('to');

    // expulsamos cualquier 'q' para no mezclar con live-search
    params.delete('q');

    window.location.search = params.toString();
  }

  function goWithRange(range){
    const now = new Date();
    let from;
    if (range==='7d')         from = minusDays(now,7);
    else if (range==='30d')   from = minusDays(now,30);
    else if (range==='month') from = firstDayOfMonth(now);
    else                      from = minusDays(now,30);

    if (fromInput) fromInput.value = toLocalIsoDate(from);
    if (toInput)   toInput.value   = toLocalIsoDate(now);
    setActiveChip(range);
    submitPreservingDateOnly({page: null});
  }

  chips.forEach(btn => btn.addEventListener("click", () => goWithRange(btn.dataset.range)));

  // Si no hay valores, setea últimos 30 días (solo UI)
  if (fromInput && toInput && (!fromInput.value || !toInput.value)) {
    const now = new Date();
    const from = minusDays(now, 30);
    fromInput.value = toLocalIsoDate(from);
    toInput.value   = toLocalIsoDate(now);
    setActiveChip('30d');
  } else if (fromInput && toInput) {
    try {
      const f = new Date(fromInput.value);
      const t = new Date(toInput.value);
      const delta = Math.round((t - f) / (24*60*60*1000));
      if (delta === 7) setActiveChip('7d');
      else if (delta === 30) setActiveChip('30d');
      else setActiveChip('');
    } catch {}
  }

  /* ====== Submit (Aplicar) — SOLO fechas ===== */
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    submitPreservingDateOnly({page: null});
  });

  /* ====== Refresh mantiene from/to y renueva 'to' ===== */
  if (btnRefresh && toInput) {
    btnRefresh.addEventListener("click", () => {
      const now = new Date();
      toInput.value = toLocalIsoDate(now);
      submitPreservingDateOnly({page: null});
    });
  }

  /* ====== Paginación: preserva SOLO from/to ===== */
  const pag = document.getElementById("paginate");
  if (pag) {
    const params = new URLSearchParams(window.location.search);
    const f = (fromInput?.value || "").trim();
    const t = (toInput?.value || "").trim();

    if (f) params.set('from', f); else params.delete('from');
    if (t) params.set('to', t); else params.delete('to');
    params.delete('q');

    pag.querySelectorAll('a[href]').forEach(a => {
      const url = new URL(a.href, window.location.origin);
      const out = new URLSearchParams(url.search);
      ['from','to'].forEach(k=>{
        if (params.has(k)) out.set(k, params.get(k)); else out.delete(k);
      });
      out.delete('q');
      a.href = url.pathname + '?' + out.toString();
    });
  }

  /* ====== Forzar apertura del date picker al clickear el área del calendario ===== */
  (function ensureCalendarIconClickable() {
    // Área "clickable" en el extremo derecho del contenedor (simula el ícono)
    const ICON_HIT = 36; // px
    document.querySelectorAll('.date-range').forEach(box => {
      const input = box.querySelector('input[type="date"]');
      if (!input) return;

      // Click en el contenedor: si se hace en el lado derecho, abrimos el picker
      box.addEventListener('click', (e) => {
        const r = box.getBoundingClientRect();
        const onIconArea = (e.clientX >= r.right - ICON_HIT);
        if (onIconArea) {
          e.preventDefault();
          if (typeof input.showPicker === 'function') input.showPicker();
          else { input.focus(); input.click?.(); }
        }
      });

      // Click directo al input → siempre intentamos abrir el picker nativo
      input.addEventListener('mousedown', (e) => {
        // Algunos navegadores ya lo abren; en otros ayudamos con showPicker
        if (typeof input.showPicker === 'function') {
          e.preventDefault();
          input.showPicker();
        }
      });

      // Asegura que al enfocar por teclado también se pueda abrir rápido con Space/Enter
      input.addEventListener('keydown', (e) => {
        if ((e.key === ' ' || e.key === 'Enter') && typeof input.showPicker === 'function') {
          e.preventDefault();
          input.showPicker();
        }
      });
    });
  })();

  // "Limpiar" ya apunta a "?" en el HTML.
})();
