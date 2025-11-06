// list.js — SOAR Incidentes: modal + live search + Enter/botón = búsqueda global
(function () {
  const Q  = (sel) => document.querySelector(sel);
  const QA = (sel) => Array.from(document.querySelectorAll(sel));

  // ====== MODAL ======
  const modal    = Q('#incidentModal');
  const metaList = Q('#inc-meta-list');

  function openFromRow(tr) {
    if (!modal || !tr) return;

    const id   = tr.dataset.id || '—';
    const dev  = tr.dataset.dispositivo || '—';
    const tipo = tr.dataset.tipo || '—';
    const sev  = tr.dataset.sev || 'N/A';
    const date = tr.dataset.date || '—';
    const time = tr.dataset.time || '—';

    const title = Q('#inc-title');
    if (title) {
      title.innerHTML = `🚨 <strong>${sev || 'N/A'}</strong> — <span class="muted">${dev}</span>`;
    }

    if (metaList) {
      metaList.innerHTML = [
        `<li><span class="mono">ID:</span> ${id}</li>`,
        `<li><strong>Dispositivo:</strong> ${dev}</li>`,
        `<li><strong>Tipo:</strong> ${tipo}</li>`,
        `<li><strong>Fecha/Hora:</strong> ${date} ${time}</li>`
      ].join('');
    }

    const riesgo   = tr.dataset.descripcion || tr.dataset.riesgo || '—';
    const clasif   = tr.dataset.analisis || '—';
    const acciones = tr.dataset.acciones || '—';
    const resumen  = tr.dataset.resumen || '—';

    const app      = tr.dataset.app || '';
    const wrap     = Q('#inc-app-wrap');

    const setText = (sel, txt) => { const el = Q(sel); if (el) el.textContent = txt; };
    setText('#inc-riesgo', riesgo);
    setText('#inc-clasif', clasif);
    setText('#inc-acciones', acciones);
    setText('#inc-resumen', resumen);

    if (wrap) {
      if (app) {
        setText('#inc-app', app);
        wrap.style.display = '';
      } else {
        wrap.style.display = 'none';
      }
    }

    document.body.classList.add('modal-open');
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
  }

  function closeModal() {
    if (!modal) return;
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
  }

  Q('.modal-backdrop')?.addEventListener('click', closeModal);
  Q('[data-close]')?.addEventListener('click', closeModal);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
  Q('.modal-card')?.addEventListener('click', (e) => e.stopPropagation());

  const tbody = Q('#tbl-incidentes tbody');
  if (tbody) {
    tbody.addEventListener('click', (ev) => {
      const tr = ev.target.closest('tr');
      if (tr) openFromRow(tr);
    });
  }

  // ====== BUSCADOR: live (local) + global (Enter / botón) ======
  const input   = Q('#q');
  const btnLive = Q('#btn-search-live'); 

  // --- util para GLOBAL (backend): recarga con ?q= y preserva from/to ---
  function submitGlobalSearch() {
    const q   = (input?.value || '').trim();
    const from = Q('#inp-from')?.value?.trim();
    const to   = Q('#inp-to')?.value?.trim();

    const params = new URLSearchParams(window.location.search);

    // limpiar paginación
    params.delete('page');

    // setear q (o sacarlo si está vacío)
    if (q) params.set('q', q); else params.delete('q');

    // preservar fechas si existen en UI
    if (from) params.set('from', from); else params.delete('from');
    if (to)   params.set('to', to);     else params.delete('to');

    // navegar (backend filtrará TODO el dataset)
    window.location.search = params.toString();
  }

  if (input && tbody) {
    const rows = Array.from(tbody.querySelectorAll('tr'));

    function haystack(tr) {
      return [
        tr.dataset.id,
        tr.dataset.dispositivo,
        tr.dataset.tipo,
        tr.dataset.sev,
        tr.dataset.date,
        tr.dataset.time,
        tr.dataset.descripcion,
        tr.dataset.analisis,
        tr.dataset.acciones,
        tr.dataset.resumen,
        tr.dataset.riesgo,
        tr.dataset.app
      ].join(' | ').toLowerCase();
    }

    const caches = new Map(rows.map((r) => [r, haystack(r)]));

    function applyFilterLocal(q) {
      const needle = (q || '').trim().toLowerCase();
      rows.forEach((r) => {
        const match = !needle || caches.get(r).includes(needle);
        r.style.display = match ? '' : 'none';
      });
    }

    // Filtro inicial local si llegó con valor (sin recarga)
    applyFilterLocal(input.value);

    // Live search (local)
    input.addEventListener('input', () => applyFilterLocal(input.value));

    // ENTER => búsqueda GLOBAL (backend) para filtrar TODAS las alarmas
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();    // evita submit del form
        submitGlobalSearch();  // recarga con ?q= y from/to
      }
    });

    // Botón "Buscar" => también GLOBAL
    if (btnLive) {
      btnLive.addEventListener('click', (e) => {
        e.preventDefault();
        submitGlobalSearch();
      });
    }
  }
})();


