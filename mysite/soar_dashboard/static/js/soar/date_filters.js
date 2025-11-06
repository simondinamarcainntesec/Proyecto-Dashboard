// static/js/soar/date_filters.js
(function () {
  /* ===== utilidades ===== */
  function pad(n){ return String(n).padStart(2,'0'); }
  function toLocalIsoDate(dt){
    return dt.getFullYear()+'-'+pad(dt.getMonth()+1)+'-'+pad(dt.getDate());
  }
  function toLocalIsoDateTime(dt){
    return dt.getFullYear()+'-'+pad(dt.getMonth()+1)+'-'+pad(dt.getDate())
           +'T'+pad(dt.getHours())+':'+pad(dt.getMinutes())+':'+pad(dt.getSeconds());
  }
  function minusDays(dt, days){
    return new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()-days, dt.getHours(), dt.getMinutes(), dt.getSeconds());
  }
  function firstDayOfMonth(dt){
    return new Date(dt.getFullYear(), dt.getMonth(), 1, 0,0,0);
  }

  const params = new URLSearchParams(location.search);

  /* ===== chips de rango ===== */
  const chips = document.querySelectorAll('.chip-btn');
  function setActiveChip(range){
    chips.forEach(c=>c.classList.toggle('is-active', c.dataset.range===range));
  }
  function goWithRange(range){
    const now = new Date();
    let from;
    if(range==='7d'){ from = minusDays(now,7); }
    else if(range==='30d'){ from = minusDays(now,30); }
    else if(range==='month'){ from = firstDayOfMonth(now); }
    else { from = minusDays(now,30); }

    const qs = new URLSearchParams(window.location.search);
    qs.set('from', toLocalIsoDateTime(from));
    qs.set('to',   toLocalIsoDateTime(now));
    window.location.search = qs.toString();
  }
  chips.forEach(btn=>{
    btn.addEventListener('click', ()=> goWithRange(btn.dataset.range));
  });

  /* ===== inputs de fecha ===== */
  const inpFrom = document.getElementById('inp-from');
  const inpTo   = document.getElementById('inp-to');

  // Si no vienen valores, poner por defecto últimos 30 días (solo fecha)
  if (inpFrom && inpTo) {
    if (!inpFrom.value || !inpTo.value) {
      const now = new Date();
      const from = minusDays(now, 30);
      inpFrom.value = toLocalIsoDate(from);
      inpTo.value   = toLocalIsoDate(now);
    }
  }

  // Activar chip según querystring actual
  if (params.has('from') && params.has('to')) {
    const toQ   = new Date(params.get('to').replace(' ', 'T'));
    const fromQ = new Date(params.get('from').replace(' ', 'T'));
    const diffMs = toQ - fromQ;
    const dayMs  = 24*60*60*1000;
    if (Math.abs(diffMs - 7*dayMs) < dayMs) setActiveChip('7d');
    else if (Math.abs(diffMs - 30*dayMs) < dayMs) setActiveChip('30d');
    else {
      const firstMonth = firstDayOfMonth(toQ);
      if (fromQ.getFullYear()===firstMonth.getFullYear() &&
          fromQ.getMonth()===firstMonth.getMonth() &&
          fromQ.getDate()===firstMonth.getDate()) setActiveChip('month');
    }
  }

  // Botón refresh: mantener "from" y actualizar "to" a ahora
  const r = document.getElementById('btn-refresh');
  if (r) r.addEventListener('click', ()=>{
    const now = new Date();
    const qs = new URLSearchParams(window.location.search);
    qs.set('to', toLocalIsoDateTime(now));
    window.location.search = qs.toString();
  });

  /* ===== Abrir picker al hacer click en el label/icono ===== */
  // El CSS coloca el ícono con ::after en .date-range.
  // Aquí interceptamos click en el label (si el target no es el input) para abrir el picker.
  document.querySelectorAll('label.date-range').forEach(lbl=>{
    const input = lbl.querySelector('input[type="date"]');
    if (!input) return;

    lbl.addEventListener('click', (ev)=>{
      // si clic fue directamente en el input, dejar comportamiento nativo
      if (ev.target === input) return;

      // enfocar y abrir el picker si el browser lo soporta
      try {
        input.focus({ preventScroll: true });
        if (typeof input.showPicker === 'function') {
          input.showPicker(); // Chrome / Edge
        } else {
          // fallback: abrir teclado/fecha en móviles al "clickear" el input
          input.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true, view:window}));
        }
      } catch (e) {
        // no pasa nada si no es soportado
      }
    });
  });
})();
