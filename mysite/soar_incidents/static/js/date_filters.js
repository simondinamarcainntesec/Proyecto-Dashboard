// Filtros de fecha + buscador en tiempo real + preservación en paginación
(function () {
  const form = document.getElementById("filters-form");
  const qInput = document.getElementById("q");
  const fromInput = document.getElementById("inp-from");
  const toInput   = document.getElementById("inp-to");
  const chips = document.querySelectorAll(".chip-btn");

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

  function submitPreserving({page} = {}) {
    const params = new URLSearchParams(window.location.search);
    const q = (qInput?.value || "").trim();
    const f = (fromInput?.value || "").trim();
    const t = (toInput?.value || "").trim();

    params.delete('page');
    if (page) params.set('page', page);

    if (q) params.set('q', q); else params.delete('q');
    if (f) params.set('from', f); else params.delete('from');
    if (t) params.set('to', t); else params.delete('to');

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
    submitPreserving({page: null});
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

  /* ====== Submit (Aplicar) ===== */
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    submitPreserving({page: null});
  });

  /* ====== Buscar en tiempo real (debounce) ===== */
  let timer = null;
  if (qInput){
    qInput.addEventListener("input", () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => submitPreserving({page: null}), 350);
    });
  }

  /* >>>> NO auto-aplicar al cambiar fecha manualmente (se espera 'Aplicar') <<<< */
  // (Eliminados los listeners change de from/to)

  /* ====== Refresh mantiene filtros + actualiza 'to' a hoy ===== */
  const btnRefresh = document.getElementById("btn-refresh");
  if (btnRefresh && toInput) {
    btnRefresh.addEventListener("click", () => {
      const now = new Date();
      toInput.value = toLocalIsoDate(now);
      submitPreserving({page: null});
    });
  }

  /* ====== Paginación: preserva q/from/to en los enlaces ===== */
  const pag = document.getElementById("paginate");
  if (pag) {
    const params = new URLSearchParams(window.location.search);
    const q = (qInput?.value || "").trim();
    const f = (fromInput?.value || "").trim();
    const t = (toInput?.value || "").trim();

    if (q) params.set('q', q); else params.delete('q');
    if (f) params.set('from', f); else params.delete('from');
    if (t) params.set('to', t); else params.delete('to');

    pag.querySelectorAll('a[href]').forEach(a => {
      const url = new URL(a.href, window.location.origin);
      const out = new URLSearchParams(url.search);
      ['q','from','to'].forEach(k=>{
        if (params.has(k)) out.set(k, params.get(k)); else out.delete(k);
      });
      a.href = url.pathname + '?' + out.toString();
    });
  }

  /* ====== Click en el área del ícono del calendario ====== */
  (function ensureCalendarIconClickable() {
    const ICON_HIT = 36; // px desde el borde derecho del contenedor
    document.querySelectorAll('.date-range').forEach(box => {
      const input = box.querySelector('input[type="date"]');
      if (!input) return;
      box.addEventListener('click', (e) => {
        const r = box.getBoundingClientRect();
        const onIconArea = (e.clientX >= r.right - ICON_HIT);
        if (onIconArea) {
          if (typeof input.showPicker === 'function') input.showPicker();
          else { input.focus(); input.click?.(); }
        }
      });
    });
  })();

  // "Limpiar" ya apunta a "?" en el HTML.
})();
