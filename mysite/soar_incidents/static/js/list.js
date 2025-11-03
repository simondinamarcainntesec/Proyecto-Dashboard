// list.js — SOAR Incidentes: modal + live search + modal-open en <body>
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

    // título
    const title = Q('#inc-title');
    if (title) {
      title.innerHTML = `🚨 <strong>${sev || 'N/A'}</strong> — <span class="muted">${dev}</span>`;
    }

    // encabezado (lista vertical)
    if (metaList) {
      metaList.innerHTML = [
        `<li><span class="mono">ID:</span> ${id}</li>`,
        `<li><strong>Dispositivo:</strong> ${dev}</li>`,
        `<li><strong>Tipo:</strong> ${tipo}</li>`,
        `<li><strong>Fecha/Hora:</strong> ${date} ${time}</li>`
      ].join('');
    }

    // bloques
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

    document.body.classList.add('modal-open');  // <-- clave para overlay correcto
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
  }

  function closeModal() {
    if (!modal) return;
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open'); // <-- quita bloqueo de scroll
  }

  // Cerrar por backdrop, botón ✕ y tecla ESC
  Q('.modal-backdrop')?.addEventListener('click', closeModal);
  Q('[data-close]')?.addEventListener('click', closeModal);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

  // Evita que clicks dentro de la tarjeta cierren la modal por accidente
  Q('.modal-card')?.addEventListener('click', (e) => e.stopPropagation());

  // Click en filas -> abrir modal
  const tbody = Q('#tbl-incidentes tbody');
  if (tbody) {
    tbody.addEventListener('click', (ev) => {
      const tr = ev.target.closest('tr');
      if (tr) openFromRow(tr);
    });
  }

  // ====== BUSCADOR EN TIEMPO REAL ======
  const input = Q('#q');
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
      ]
        .join(' | ')
        .toLowerCase();
    }

    const caches = new Map(rows.map((r) => [r, haystack(r)]));

    function applyFilter(q) {
      const needle = (q || '').trim().toLowerCase();
      rows.forEach((r) => {
        const match = !needle || caches.get(r).includes(needle);
        r.style.display = match ? '' : 'none';
      });
    }

    // Aplica filtro inicial si viene q pre-cargado
    applyFilter(input.value);

    // Live search
    input.addEventListener('input', () => applyFilter(input.value));
  }
})();
