// list.js — SOAR Incidentes: modal + live search + Enter/botón = búsqueda global
(function () {
  const Q = (sel) => document.querySelector(sel);
  const DBG = () => !!window.SOAR_DEBUG;
  const log = (...a) => { if (DBG()) console.log('[SOAR_LIST]', ...a); };

  function esc(s) {
    return String(s ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  // ============================
  // Ticket map desde json_script
  // ============================
  function readTicketMap() {
    const el = Q('#soarTicketMap');
    if (!el) return {};
    try {
      return JSON.parse(el.textContent || '{}') || {};
    } catch (e) {
      console.warn('[SOAR_LIST] ticket_map JSON inválido', e);
      return {};
    }
  }
  const TICKET_MAP = readTicketMap();

  function isAssigned(tr) {
    const v = String(tr?.dataset?.assigned || '').trim().toLowerCase();
    return v === '1' || v === 'true' || v === 'yes';
  }

  // ✅ soporte a múltiples nombres de data-*
  function assignedName(tr) {
    const raw =
      tr?.dataset?.assignedName ||
      tr?.dataset?.assigned_name ||
      tr?.dataset?.ticketAssignedToName ||
      tr?.dataset?.ticket_assigned_to_name ||
      tr?.dataset?.ticketName ||
      tr?.dataset?.ticket_name ||
      '';
    return String(raw || '').trim();
  }

  // ✅ si el dataset viene vacío, buscar por ID en ticket_map (server-side)
  function assignedNameFromMap(tr) {
    const id = String(tr?.dataset?.id || '').trim();
    if (!id) return '';
    const tk = TICKET_MAP[id] || null;
    if (!tk) return '';
    return String(
      tk.assigned_to_name || tk.assigned_to || tk.assigned || tk.assignee || tk.assigned_to_name || ''
    ).trim();
  }

  function renderAssignedBadge(tr) {
    const yes = isAssigned(tr);
    if (!yes) {
      return `
        <span class="assign-pill is-no">
          <svg class="assign-ico" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"></circle>
          </svg>
          No
        </span>
      `;
    }

    const name = assignedName(tr) || assignedNameFromMap(tr);

    const userPart = name
      ? `
        <span class="assign-user-badge">
          <span class="meta-ico is-user" aria-hidden="true"></span>
          <span class="assign-user-name">${esc(name)}</span>
        </span>
      `
      : '';

    return `
      <span class="assign-pill is-yes">
        <svg class="assign-ico" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"></circle>
          <path d="M8 12l2.5 2.5L16 9" fill="none" stroke="currentColor" stroke-width="2.5"
            stroke-linecap="round" stroke-linejoin="round"></path>
        </svg>
        Sí
      </span>
      ${userPart}
    `;
  }

  // ====== MODAL ======
  const modal = Q('#incidentModal');
  const metaList = Q('#inc-meta-list');

  function openFromRow(tr) {
    if (!modal || !tr) return;

    const id = tr.dataset.id || '—';
    const dev = tr.dataset.dispositivo || '—';
    const tipo = tr.dataset.tipo || '—';
    const sev = tr.dataset.sev || 'N/A';
    const date = tr.dataset.date || '—';
    const time = tr.dataset.time || '—';

    const title = Q('#inc-title');
    if (title) {
      title.innerHTML = `
        🚨 <strong>${esc(sev || 'N/A')}</strong>
        — <span class="muted">${esc(dev)}</span>
        <span class="inc-title-right">${renderAssignedBadge(tr)}</span>
      `;
    }

    if (metaList) {
      const nm = assignedName(tr) || assignedNameFromMap(tr);
      const assignedLine = isAssigned(tr)
        ? `<li><strong>Ticket:</strong> Sí${nm ? ` — <span class="mono">${esc(nm)}</span>` : ''}</li>`
        : `<li><strong>Ticket:</strong> No</li>`;

      metaList.innerHTML = [
        `<li><span class="mono">ID:</span> ${esc(id)}</li>`,
        assignedLine,
        `<li><strong>Dispositivo:</strong> ${esc(dev)}</li>`,
        `<li><strong>Tipo:</strong> ${esc(tipo)}</li>`,
        `<li><strong>Fecha/Hora:</strong> ${esc(date)} ${esc(time)}</li>`
      ].join('');
    }

    const riesgo = tr.dataset.descripcion || tr.dataset.riesgo || '—';
    const clasif = tr.dataset.analisis || '—';
    const acciones = tr.dataset.acciones || '—';
    const resumen = tr.dataset.resumen || '—';
    const app = tr.dataset.app || '';

    const wrap = Q('#inc-app-wrap');
    const setText = (sel, txt) => {
      const el = Q(sel);
      if (el) el.textContent = txt ?? '';
    };

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
    modal.removeAttribute('inert');

    log('openFromRow', { id, assigned: isAssigned(tr), name: assignedName(tr) || assignedNameFromMap(tr) });
  }

  function closeModal() {
    if (!modal) return;
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    modal.setAttribute('inert', '');
    document.body.classList.remove('modal-open');
  }

  Q('#incidentModal .modal-backdrop')?.addEventListener('click', closeModal);
  Q('#incidentModal [data-close]')?.addEventListener('click', closeModal);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });
  Q('#incidentModal .modal-card')?.addEventListener('click', (e) => e.stopPropagation());

  const tbody = Q('#tbl-incidentes tbody');
  if (tbody) {
    tbody.addEventListener('click', (ev) => {
      const tr = ev.target.closest('tr');
      if (tr) openFromRow(tr);
    });
  }

  // ====== BUSCADOR: live (local) + global (Enter / botón) ======
  const input = Q('#q');
  const btnLive = Q('#btn-search-live');

  const selSev = Q('#f-sev');
  const selAssigned = Q('#f-assigned');

  function submitGlobalSearch() {
    const q = (input?.value || '').trim();
    const from = Q('#inp-from')?.value?.trim();
    const to = Q('#inp-to')?.value?.trim();

    const sev = (selSev?.value || '').trim();
    const assigned = (selAssigned?.value || '').trim();

    const params = new URLSearchParams(window.location.search);
    params.delete('page');

    if (q) params.set('q', q); else params.delete('q');
    if (from) params.set('from', from); else params.delete('from');
    if (to) params.set('to', to); else params.delete('to');
    if (sev) params.set('sev', sev); else params.delete('sev');
    if (assigned) params.set('assigned', assigned); else params.delete('assigned');

    window.location.search = params.toString();
  }

  if (input && tbody) {
    const rows = Array.from(tbody.querySelectorAll('tr'));

    function assignedText(tr) {
      const v = (tr.dataset.assigned || '').trim();
      const nm = assignedName(tr) || assignedNameFromMap(tr);
      return (v === '1')
        ? `si sí asignado assigned ${nm}`.toLowerCase()
        : 'no no_asignado unassigned';
    }

    function haystack(tr) {
      return [
        tr.dataset.id,
        assignedText(tr),
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
        const match = !needle || (caches.get(r) || '').includes(needle);
        r.style.display = match ? '' : 'none';
      });
    }

    applyFilterLocal(input.value);

    input.addEventListener('input', () => applyFilterLocal(input.value));

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        submitGlobalSearch();
      }
    });

    if (btnLive) {
      btnLive.addEventListener('click', (e) => {
        e.preventDefault();
        submitGlobalSearch();
      });
    }
  }
})();
