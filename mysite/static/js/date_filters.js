// static/js/date_filters.js
// Filtros de fecha (solo back). El buscador #q NO recarga la página.
// Ahora preserva también sev y assigned al aplicar / chips / refresh / paginación.
(function () {
  const form = document.getElementById("filters-form");
  const fromInput = document.getElementById("inp-from");
  const toInput   = document.getElementById("inp-to");
  const chips = document.querySelectorAll(".chip-btn");
  const btnRefresh = document.getElementById("btn-refresh");

  // nuevos selects (si existen)
  const sevSelect = document.getElementById("f-sev");
  const assignedSelect = document.getElementById("f-assigned");

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

  // Antes: solo fechas. Ahora: fechas + sev + assigned.
  function submitPreservingFilters({page} = {}) {
    const params = new URLSearchParams(window.location.search);

    const f = (fromInput?.value || "").trim();
    const t = (toInput?.value || "").trim();

    const sev = (sevSelect?.value || "").trim();
    const assigned = (assignedSelect?.value || "").trim();

    params.delete('page');
    if (page) params.set('page', page);

    if (f) params.set('from', f); else params.delete('from');
    if (t) params.set('to', t); else params.delete('to');

    // preserva filtros nuevos
    if (sev) params.set('sev', sev); else params.delete('sev');
    if (assigned) params.set('assigned', assigned); else params.delete('assigned');

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
    submitPreservingFilters({page: null});
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

  /* ====== Submit (Aplicar) — fechas + sev + assigned ===== */
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    submitPreservingFilters({page: null});
  });

  /* ====== Refresh mantiene from/to y renueva 'to' ===== */
  if (btnRefresh && toInput) {
    btnRefresh.addEventListener("click", () => {
      const now = new Date();
      toInput.value = toLocalIsoDate(now);
      submitPreservingFilters({page: null});
    });
  }

  /* ====== Paginación: preserva from/to + sev + assigned ===== */
  const pag = document.getElementById("paginate");
  if (pag) {
    const params = new URLSearchParams(window.location.search);

    const f = (fromInput?.value || "").trim();
    const t = (toInput?.value || "").trim();

    const sev = (sevSelect?.value || params.get('sev') || "").trim();
    const assigned = (assignedSelect?.value || params.get('assigned') || "").trim();

    if (f) params.set('from', f); else params.delete('from');
    if (t) params.set('to', t); else params.delete('to');

    if (sev) params.set('sev', sev); else params.delete('sev');
    if (assigned) params.set('assigned', assigned); else params.delete('assigned');

    params.delete('q');

    pag.querySelectorAll('a[href]').forEach(a => {
      const url = new URL(a.href, window.location.origin);
      const out = new URLSearchParams(url.search);

      ['from','to','sev','assigned'].forEach(k=>{
        if (params.has(k)) out.set(k, params.get(k)); else out.delete(k);
      });

      out.delete('q');
      a.href = url.pathname + '?' + out.toString();
    });
  }

  /* ====== Forzar apertura del date picker al clickear el área del calendario ===== */
  (function ensureCalendarIconClickable() {
    const ICON_HIT = 36; // px
    document.querySelectorAll('.date-range').forEach(box => {
      const input = box.querySelector('input[type="date"]');
      if (!input) return;

      box.addEventListener('click', (e) => {
        const r = box.getBoundingClientRect();
        const onIconArea = (e.clientX >= r.right - ICON_HIT);
        if (onIconArea) {
          e.preventDefault();
          if (typeof input.showPicker === 'function') input.showPicker();
          else { input.focus(); input.click?.(); }
        }
      });

      input.addEventListener('mousedown', (e) => {
        if (typeof input.showPicker === 'function') {
          e.preventDefault();
          input.showPicker();
        }
      });

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
