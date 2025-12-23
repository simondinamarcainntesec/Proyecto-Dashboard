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

  // Header modal
  const elEventTitle = Q('#assign-event-title');
  const elEventId = Q('#assign-event-id');

  // ✅ Tenant fijo desde template
  const tenantStatic = Q('#assign-tenant-static'); // div con data-tenant-id

  const selUser = Q('#assign-user');
  const selDuration = Q('#assign-duration');
  const customWrap = Q('#assign-custom-date-wrap');
  const inpCustomDate = Q('#assign-custom-date');
  const dueText = Q('#assign-due-text');

  let selectedRow = null;

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

  function openAssignModal() {
    if (!selectedRow) return;

    const id = selectedRow.dataset.id || '—';
    const tipo = selectedRow.dataset.tipo || '—';
    const dev = selectedRow.dataset.dispositivo || '—';

    if (elEventTitle) elEventTitle.textContent = `${tipo} (${dev})`;
    if (elEventId) elEventId.textContent = id;

    // defaults duración
    if (selDuration) selDuration.value = '7';
    if (customWrap) customWrap.classList.add('hidden');
    if (inpCustomDate) inpCustomDate.value = '';

    computeDueDate();

    document.body.classList.add('modal-open');
    assignModal.classList.remove('hidden');
    assignModal.setAttribute('aria-hidden', 'false');

    // ✅ cargar usuarios del tenant ACTUAL (fijo)
    const tenantId = (tenantStatic?.dataset?.tenantId || '').trim();
    loadUsersForTenant(tenantId);
  }

  function closeAssignModal() {
    assignModal.classList.add('hidden');
    assignModal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
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
    let dueISO = '';

    const dur = selDuration ? selDuration.value : '7';
    if (dur === 'custom') {
      dueISO = (inpCustomDate?.value || '').trim();
    } else {
      const n = parseInt(dur, 10);
      const due = addDays(today, isNaN(n) ? 7 : n);
      dueISO = toISODate(due);
    }

    if (dur === 'custom') customWrap && customWrap.classList.remove('hidden');
    else customWrap && customWrap.classList.add('hidden');

    dueText.textContent = dueISO
      ? `Fecha de vencimiento: ${formatLongCL(dueISO)}`
      : 'Fecha de vencimiento: —';

    validateAssignForm();
  }

  function validateAssignForm() {
    if (!assignSubmit || !selUser || !selDuration) return;

    const userOk = !!(selUser.value || '').trim();
    const dur = selDuration.value;
    const dueOk = (dur !== 'custom') || !!(inpCustomDate?.value || '').trim();

    assignSubmit.disabled = !(userOk && dueOk);
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
    openAssignModal();
  });

  assignBackdrop?.addEventListener('click', closeAssignModal);
  assignClose?.addEventListener('click', closeAssignModal);
  assignCancel?.addEventListener('click', closeAssignModal);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      hideCtxMenu();
      closeAssignModal();
    }
  });

  selDuration?.addEventListener('change', computeDueDate);
  inpCustomDate?.addEventListener('change', computeDueDate);
  selUser?.addEventListener('change', validateAssignForm);

  computeDueDate();
})();
