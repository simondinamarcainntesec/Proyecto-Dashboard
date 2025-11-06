// static/js/alarms_one/date_filters.js
(function () {
  /* utilidades */
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

  const p = new URLSearchParams(location.search);
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

    const params = new URLSearchParams(window.location.search);
    params.set('from', toLocalIsoDateTime(from));
    params.set('to',   toLocalIsoDateTime(now));
    window.location.search = params.toString();
  }
  chips.forEach(btn=>{
    btn.addEventListener('click', ()=> goWithRange(btn.dataset.range));
  });

  const inpFrom = document.getElementById('inp-from');
  const inpTo   = document.getElementById('inp-to');
  if (inpFrom && inpTo) {
    if (!inpFrom.value || !inpTo.value) {
      const now = new Date();
      const from = minusDays(now, 30);
      inpFrom.value = toLocalIsoDate(from);
      inpTo.value   = toLocalIsoDate(now);
    }
  }

  if (p.has('from') && p.has('to')) {
    const toQ  = new Date(p.get('to').replace(' ', 'T'));
    const fromQ= new Date(p.get('from').replace(' ', 'T'));
    const diffMs = toQ - fromQ;
    const dayMs = 24*60*60*1000;
    if (Math.abs(diffMs - 7*dayMs) < dayMs) setActiveChip('7d');
    else if (Math.abs(diffMs - 30*dayMs) < dayMs) setActiveChip('30d');
    else {
      const firstMonth = firstDayOfMonth(toQ);
      if (fromQ.getFullYear()===firstMonth.getFullYear() &&
          fromQ.getMonth()===firstMonth.getMonth() &&
          fromQ.getDate()===firstMonth.getDate()) setActiveChip('month');
    }
  }

  const r = document.getElementById('btn-refresh');
  if (r) r.addEventListener('click', ()=>{
    const now = new Date();
    const params = new URLSearchParams(window.location.search);
    params.set('to', toLocalIsoDateTime(now));
    window.location.search = params.toString();
  });
})();
