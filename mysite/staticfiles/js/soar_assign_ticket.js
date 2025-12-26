// static/js/soar_assign_ticket.js
(function () {
  const Q = (s, r = document) => r.querySelector(s);

  const table = Q('#tbl-incidentes');
  const ctxMenu = Q('#soarCtxMenu');
  const ctxAssignBtn = Q('#ctxAssignTicketBtn');
  const assignModal = Q('#assignTicketModal');

  if (!table || !ctxMenu || !ctxAssignBtn || !assignModal) return;

  const assignBackdrop = Q('[data-assign-backdrop]');
  const assignClose = Q('[data-assign-close]');
  const assignCancel = Q('#assign-cancel');
  const assignSubmit = Q('#assign-submit');

  const elEventTitle = Q('#assign-event-title');
  const elEventId = Q('#assign-event-id');

  const tenantStatic = Q('#assign-tenant-static');

  const selUser = Q('#assign-user');
  const selDuration = Q('#assign-duration');
  const customWrap = Q('#assign-custom-date-wrap');
  const inpCustomDate = Q('#assign-custom-date');
  const dueText = Q('#assign-due-text');

  let selectedRow = null;
  let currentDueISO = "";

  const INFO_MODAL_ID = 'ticketCreatedModal';

  function ensureInfoModal() {
    let m = Q(`#${INFO_MODAL_ID}`);
    if (m) return m;

    const wrap = document.createElement('div');
    wrap.id = INFO_MODAL_ID;
    wrap.className = 'modal hidden';
    wrap.setAttribute('aria-hidden', 'true');

    wrap.innerHTML = `
      <div class="modal-backdrop" data-info-backdrop></div>
      <div class="modal-card created-info-card" role="dialog" aria-modal="true" aria-labelledby="ticketCreatedTitle">
        <div class="modal-header">
          <h3 id="ticketCreatedTitle">Ticket creado</h3>
          <button class="modal-close" type="button" aria-label="Cerrar" data-info-x>&times;</button>
        </div>
        <div class="modal-body">
          <p class="created-info-text">
            Ticket creado con exito, puedes revisar el detalle en el modulo de tickets.
          </p>
          <div class="created-info-actions">
            <button type="button" class="btn primary" data-info-ok>OK</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(wrap);

    const backdrop = Q('[data-info-backdrop]', wrap);
    const ok = Q('[data-info-ok]', wrap);
    const x = Q('[data-info-x]', wrap);
    const card = wrap.querySelector('.created-info-card');

    function closeInfoModal() {
      wrap.classList.add('hidden');
      wrap.setAttribute('aria-hidden', 'true');

      const anyOpen = Array.from(document.querySelectorAll('.modal'))
        .some(mm => !mm.classList.contains('hidden'));
      if (!anyOpen) document.body.classList.remove('modal-open');
    }

    ok?.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeInfoModal();
    });

    backdrop?.addEventListener('click', closeInfoModal);
    x?.addEventListener('click', closeInfoModal);
    card?.addEventListener('click', (e) => e.stopPropagation());

    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      if (!wrap.classList.contains('hidden')) closeInfoModal();
    });

    wrap._close = closeInfoModal;
    return wrap;
  }

  function openInfoModal(title, message) {
    const m = ensureInfoModal();

    const h = Q('#ticketCreatedTitle', m);
    const p = m.querySelector('.created-info-text');

    if (h) h.textContent = title || 'Información';
    if (p) p.textContent = message || '';

    document.body.classList.add('modal-open');
    m.classList.remove('hidden');
    m.setAttribute('aria-hidden', 'false');

    const ok = Q('[data-info-ok]', m);
    setTimeout(() => ok?.focus?.(), 30);
  }

  // ✅ detectar si el evento ya tiene ticket
  function isRowAssigned(tr) {
    if (!tr) return false;
    const v = String(tr.dataset.assigned || '').trim().toLowerCase();
    return v === '1' || v === 'true' || v === 'yes';
  }

  // ✅ Render del indicador "Sí/No"
  function renderAssignedCell(isYes) {
    if (isYes) {
      return `
        <span class="assign-pill is-yes">
          <svg class="assign-ico" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"></circle>
            <path d="M8 12l2.5 2.5L16 9" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"></path>
          </svg>
          Sí
        </span>
      `;
    }
    return `
      <span class="assign-pill is-no">
        <svg class="assign-ico" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"></circle>
        </svg>
        No
      </span>
    `;
  }

  function markRowAssigned(tr) {
    if (!tr) return;
    tr.dataset.assigned = '1';
    const cell = tr.querySelector('[data-assigned-cell]');
    if (cell) cell.innerHTML = renderAssignedCell(true);
  }

  // Context menu helpers
  function clampMenuToViewport(x, y) {
    ctxMenu.style.left = '0px';
    ctxMenu.style.top = '0px';
    ctxMenu.classList.remove('hidden');

    const rect = ctxMenu.getBoundingClientRect();
    const pad = 8;

    const maxX = window.innerWidth - rect.width - pad;
    const maxY = window.innerHeight - rect.height - pad;

    return {
      x: Math.max(pad, Math.min(x, maxX)),
      y: Math.max(pad, Math.min(y, maxY)),
    };
  }

  function hideCtxMenu() {
    ctxMenu.classList.add('hidden');
    ctxMenu.setAttribute('aria-hidden', 'true');
  }

  function showCtxMenu(x, y) {
    const pos = clampMenuToViewport(x, y);
    ctxMenu.style.left = `${pos.x}px`;
    ctxMenu.style.top = `${pos.y}px`;
    ctxMenu.classList.remove('hidden');
    ctxMenu.setAttribute('aria-hidden', 'false');
  }

  // Modal asignación
  function openAssignModal() {
    if (!selectedRow) return;

    // ✅ si ya está asignado -> mensaje y no abrir modal
    if (isRowAssigned(selectedRow)) {
      openInfoModal('Ticket ya asignado', 'Este evento ya cuenta con un ticket asignado.');
      return;
    }

    const id = selectedRow.dataset.id || '—';
    const tipo = selectedRow.dataset.tipo || '—';
    const dev = selectedRow.dataset.dispositivo || '—';

    if (elEventTitle) elEventTitle.textContent = `${tipo} (${dev})`;
    if (elEventId) elEventId.textContent = id;

    if (selDuration) selDuration.value = '7';
    if (customWrap) customWrap.classList.add('hidden');
    if (inpCustomDate) inpCustomDate.value = '';

    computeDueDate();

    document.body.classList.add('modal-open');
    assignModal.classList.remove('hidden');
    assignModal.setAttribute('aria-hidden', 'false');

    const tenantId = (tenantStatic?.dataset?.tenantId || '').trim();
    loadUsersForTenant(tenantId);
  }

  function closeAssignModal(keepLock = false) {
    assignModal.classList.add('hidden');
    assignModal.setAttribute('aria-hidden', 'true');

    if (!keepLock) {
      const anyOpen = Array.from(document.querySelectorAll('.modal')).some(m => !m.classList.contains('hidden'));
      if (!anyOpen) document.body.classList.remove('modal-open');
    }
  }

  function addDays(dateObj, days) {
    const d = new Date(dateObj);
    d.setDate(d.getDate() + days);
    return d;
  }

  function toISODate(d) {
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }

  function formatLongCL(iso) {
    try {
      const [y, m, d] = iso.split('-').map(Number);
      const dt = new Date(y, m - 1, d);
      return dt.toLocaleDateString('es-CL', { day: 'numeric', month: 'long', year: 'numeric' });
    } catch {
      return iso;
    }
  }

  function computeDueDate() {
    if (!dueText) return;

    const today = new Date();
    const dur = selDuration ? selDuration.value : '7';

    if (dur === 'custom') {
      currentDueISO = (inpCustomDate?.value || '').trim();
      customWrap && customWrap.classList.remove('hidden');
    } else {
      const n = parseInt(dur, 10);
      const due = addDays(today, isNaN(n) ? 7 : n);
      currentDueISO = toISODate(due);
      customWrap && customWrap.classList.add('hidden');
    }

    dueText.textContent = currentDueISO
      ? `Fecha de vencimiento: ${formatLongCL(currentDueISO)}`
      : 'Fecha de vencimiento: —';

    validateAssignForm();
  }

  function validateAssignForm() {
    if (!assignSubmit || !selUser || !selDuration) return;

    const userOk = !!(selUser.value || '').trim();
    const dur = selDuration.value;
    const dueOk = (dur !== 'custom') || !!(inpCustomDate?.value || '').trim();

    assignSubmit.disabled = !(userOk && dueOk && !!currentDueISO);
  }

  function getCSRFToken() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  async function loadUsersForTenant(tenantId) {
    if (!selUser) return;

    selUser.disabled = true;
    selUser.innerHTML = `<option value="">Cargando usuarios…</option>`;
    if (assignSubmit) assignSubmit.disabled = true;

    const endpoint = (document.body?.dataset?.soarTenantUsersUrl || '').trim();
    if (!endpoint) {
      selUser.innerHTML = `<option value="">(Falta data-soar-tenant-users-url)</option>`;
      selUser.disabled = false;
      validateAssignForm();
      return;
    }

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCSRFToken(),
        },
        credentials: 'same-origin',
        body: JSON.stringify({ tenant_id: tenantId || null }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      const items = Array.isArray(data) ? data : (data.users || []);
      selUser.innerHTML = `<option value="">Selecciona un usuario…</option>`;

      if (!items.length) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = 'No hay usuarios activos en este tenant';
        selUser.appendChild(opt);
      } else {
        items.forEach(u => {
          const opt = document.createElement('option');
          opt.value = String(u.id);
          const label = u.full_name || u.username || `User ${u.id}`;
          const email = u.email ? ` — ${u.email}` : '';
          opt.textContent = `${label}${email}`;
          selUser.appendChild(opt);
        });
      }

      selUser.disabled = false;
      validateAssignForm();
    } catch (e) {
      selUser.innerHTML = `<option value="">Error cargando usuarios</option>`;
      selUser.disabled = false;
      validateAssignForm();
    }
  }

  async function submitCreateTicket() {
    if (!selectedRow) return;

    // ✅ si ya está asignado, no abrir flow
    if (isRowAssigned(selectedRow)) {
      closeAssignModal(true);
      openInfoModal('Ticket ya asignado', 'Este evento ya cuenta con un ticket asignado.');
      return;
    }

    const endpoint = (document.body?.dataset?.soarTicketCreateUrl || '').trim();
    if (!endpoint) {
      alert("Falta data-soar-ticket-create-url en <body>.");
      return;
    }

    const assignedTo = (selUser?.value || '').trim();
    if (!assignedTo || !currentDueISO) return;

    const payload = {
      alarm_id: (selectedRow.dataset.id || '').trim(),

      dispositivo: selectedRow.dataset.dispositivo || '',
      tipo_de_amenaza: selectedRow.dataset.tipo || '',
      nivel_de_severidad: selectedRow.dataset.sev || '',

      event_date: (selectedRow.dataset.date || '').trim() || null,
      event_time: (selectedRow.dataset.time || '').trim() || null,

      descripcion_incidente: selectedRow.dataset.descripcion || '',
      analisis_criticidad: selectedRow.dataset.analisis || '',
      medidas_correctivas: selectedRow.dataset.acciones || '',
      resumen_humano: selectedRow.dataset.resumen || '',
      riesgo_detectado: selectedRow.dataset.riesgo || '',
      application: selectedRow.dataset.app || '',

      assigned_to: assignedTo,
      due_date: currentDueISO,
    };

    try {
      assignSubmit.disabled = true;

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCSRFToken(),
        },
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      });

      const out = await res.json().catch(() => ({}));

      if (res.status === 409 || out.code === 'ALREADY_EXISTS') {
        markRowAssigned(selectedRow);
        closeAssignModal(true);
        openInfoModal('Ticket ya asignado', 'Este evento ya cuenta con un ticket asignado.');
        return;
      }

      if (!res.ok || !out.ok) {
        throw new Error(out.error || `HTTP ${res.status}`);
      }

      markRowAssigned(selectedRow);
      closeAssignModal(true);
      openInfoModal('Ticket creado', 'Ticket creado con exito, puedes revisar el detalle en el modulo de tickets.');
    } catch (e) {
      assignSubmit.disabled = false;
      alert(`No se pudo crear el ticket: ${e.message || e}`);
    }
  }

  // ===== Eventos =====
  table.addEventListener('contextmenu', (ev) => {
    const tr = ev.target.closest('tr.soar-row');
    if (!tr) return;

    ev.preventDefault();
    selectedRow = tr;
    showCtxMenu(ev.clientX, ev.clientY);
  });

  document.addEventListener('click', (ev) => {
    if (!ctxMenu.classList.contains('hidden') && !ev.target.closest('#soarCtxMenu')) {
      hideCtxMenu();
    }
  });

  window.addEventListener('scroll', hideCtxMenu, { passive: true });
  window.addEventListener('resize', hideCtxMenu);

  ctxAssignBtn.addEventListener('click', () => {
    hideCtxMenu();

    // ✅ AQUÍ: si está asignado, mostrar mensaje directo
    if (isRowAssigned(selectedRow)) {
      openInfoModal('Ticket ya asignado', 'Este evento ya cuenta con un ticket asignado.');
      return;
    }

    openAssignModal();
  });

  assignBackdrop?.addEventListener('click', () => closeAssignModal(false));
  assignClose?.addEventListener('click', () => closeAssignModal(false));
  assignCancel?.addEventListener('click', () => closeAssignModal(false));

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      hideCtxMenu();
      if (!assignModal.classList.contains('hidden')) closeAssignModal(false);
    }
  });

  selDuration?.addEventListener('change', computeDueDate);
  inpCustomDate?.addEventListener('change', computeDueDate);
  selUser?.addEventListener('change', validateAssignForm);

  assignSubmit?.addEventListener('click', submitCreateTicket);

  computeDueDate();
})();
