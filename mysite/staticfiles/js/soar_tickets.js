// static/js/soar_tickets.js
(function () {
  const Q = (s, r = document) => r.querySelector(s);

  const table = Q('#tbl-tickets');
  const modal = Q('#ticketModal');
  const closeModal = Q('#closeTicketModal');
  const successModal = Q('#ticketSuccessModal');

  if (!table || !modal || !closeModal || !successModal) return;

  // ===== Modal detalle =====
  const backdrop = Q('[data-ticket-backdrop]');
  const closeBtn = Q('[data-ticket-close]');
  const closeBtn2 = Q('[data-ticket-close-2]');
  const detailCard = modal.querySelector('.modal-card');

  const titleText = Q('#tkt-title-text');
  const elCode = Q('#tkt-code');
  const elAssigned = Q('#tkt-assigned');
  const elOpened = Q('#tkt-opened');
  const elUpdated = Q('#tkt-updated');
  const elTenant = Q('#tkt-tenant');
  const elDue = Q('#tkt-due');
  const elStatusBadge = Q('#tkt-status-badge');

  const elAlarmId = Q('#tkt-alarm-id');
  const elDevice = Q('#tkt-device');
  const elType = Q('#tkt-type');
  const elDatetime = Q('#tkt-datetime');
  const elSevPill = Q('#tkt-sev-pill');

  const elRiesgo = Q('#tkt-riesgo');
  const elAnalisis = Q('#tkt-analisis');
  const elAcciones = Q('#tkt-acciones');
  const appWrap = Q('#tkt-app-wrap');
  const elApp = Q('#tkt-app');

  const btnOpenClose = Q('#tkt-open-close-modal');

  // cerrado
  const wrapClosedBy = Q('#tkt-closed-by-wrap');
  const wrapClosedAt = Q('#tkt-closed-at-wrap');
  const elClosedBy = Q('#tkt-closed-by');
  const elClosedAt = Q('#tkt-closed-at');

  // notes (detalle)
  const wrapNotes = Q('#tkt-notes-wrap');
  const elNotes = Q('#tkt-notes');

  // ===== Modal observaciones =====
  const closeBackdrop = Q('[data-close-backdrop]');
  const closeX = Q('[data-close-x]');
  const closeCancel = Q('[data-close-cancel]');
  const closeForm = Q('#close-notes-form');
  const notesTextarea = Q('#close-notes');
  const closeConfirmBtn = Q('#close-confirm-btn');
  const closeCard = closeModal.querySelector('.modal-card');

  // ===== Modal éxito =====
  const successBackdrop = Q('[data-success-backdrop]');
  const successOk = Q('[data-success-ok]');
  const successCard = successModal.querySelector('.modal-card');

  let selectedRow = null;

  // helpers
  function esc(s){ return String(s ?? ''); }

  function stopAll(e) {
    if (!e) return;
    e.preventDefault?.();
    e.stopPropagation?.();
    if (e.stopImmediatePropagation) e.stopImmediatePropagation();
  }

  function pillClassFromSeverity(sevRaw) {
    const sev = (sevRaw || '').toLowerCase();
    if (sev === 'critical' || sev === 'crítico' || sev === 'critico') return 'sev-critical';
    if (sev === 'high' || sev === 'alto') return 'sev-high';
    if (sev === 'medium' || sev === 'medio') return 'sev-medium';
    if (sev === 'low' || sev === 'bajo') return 'sev-low';
    if (sev === 'info') return 'sev-info';
    return 'sev-na';
  }

  function formatLongCL(iso) {
    if (!iso) return '—';
    try {
      const [y, m, d] = iso.split('-').map(Number);
      const dt = new Date(y, m - 1, d);
      return dt.toLocaleDateString('es-CL', { day: 'numeric', month: 'long', year: 'numeric' });
    } catch {
      return iso;
    }
  }

  function setStatusBadge(status) {
    const st = (status || 'OPEN').toUpperCase();
    if (st === 'OPEN') {
      elStatusBadge.innerHTML = `<span class="state-badge is-open">Abierto</span>`;
      if (btnOpenClose) btnOpenClose.style.display = '';
    } else {
      elStatusBadge.innerHTML = `<span class="state-badge is-closed">Cerrado</span>`;
      if (btnOpenClose) btnOpenClose.style.display = 'none';
    }
  }

  function getCookie(name) {
    const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return m ? decodeURIComponent(m[2]) : '';
  }

  function getCsrfTokenFromForm() {
    const inp = closeForm?.querySelector('input[name="csrfmiddlewaretoken"]');
    return inp ? inp.value : '';
  }

  // ===== modal open/close =====
  function openModalDetail() {
    document.body.classList.add('modal-open');
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
  }

  // NO quitar modal-open si otra modal sigue abierta
  function closeModalDetailFully() {
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');

    const closeIsOpen = !closeModal.classList.contains('hidden');
    const successIsOpen = !successModal.classList.contains('hidden');
    if (!closeIsOpen && !successIsOpen) {
      document.body.classList.remove('modal-open');
    }
  }

  function openCloseNotesModal() {
    document.body.classList.add('modal-open');

    closeModal.classList.remove('hidden');
    closeModal.setAttribute('aria-hidden', 'false');

    // precarga notes
    const existing = (selectedRow?.dataset?.notes || '').trim();
    notesTextarea.value = existing || '';

    // action del form close/<id>/
    const ticketId = selectedRow?.dataset?.ticketId;
    if (closeForm && ticketId) closeForm.action = `close/${ticketId}/`;

    setTimeout(() => notesTextarea.focus(), 50);
  }

  function closeCloseNotesModal() {
    closeModal.classList.add('hidden');
    closeModal.setAttribute('aria-hidden', 'true');

    const detailIsOpen = !modal.classList.contains('hidden');
    const successIsOpen = !successModal.classList.contains('hidden');
    if (!detailIsOpen && !successIsOpen) {
      document.body.classList.remove('modal-open');
    }
  }

  function openSuccessModal() {
    document.body.classList.add('modal-open');
    successModal.classList.remove('hidden');
    successModal.setAttribute('aria-hidden', 'false');
  }

  function closeSuccessModalAndReload() {
    successModal.classList.add('hidden');
    successModal.setAttribute('aria-hidden', 'true');

    // removemos blur/lock
    document.body.classList.remove('modal-open');

    // refrescar para que cambie el estado/tabla
    location.reload();
  }

  // evitar clicks dentro de cards = "afuera"
  detailCard?.addEventListener('click', (e) => e.stopPropagation());
  closeCard?.addEventListener('click', (e) => e.stopPropagation());
  successCard?.addEventListener('click', (e) => e.stopPropagation());

  // ===== fill detail =====
  function fillFromRow(tr) {
    selectedRow = tr;

    const code = tr.dataset.ticketCode || '—';
    const alarmId = tr.dataset.alarmId || '—';
    const device = tr.dataset.device || '—';
    const type = tr.dataset.type || '—';
    const sev = tr.dataset.sev || 'N/A';

    const status = tr.dataset.status || 'OPEN';
    const tenant = tr.dataset.tenant || '—';
    const assigned = tr.dataset.assigned || '—';
    const created = tr.dataset.created || '—';
    const opened = tr.dataset.opened || '—';
    const updated = tr.dataset.updated || opened || '—';
    const due = tr.dataset.due || '';

    const eventDate = (tr.dataset.eventDate || '').trim();
    const eventTime = (tr.dataset.eventTime || '').trim();

    const riesgo = tr.dataset.riesgo || '—';
    const analisis = tr.dataset.analisis || '—';
    const acciones = tr.dataset.acciones || '—';
    const app = (tr.dataset.app || '').trim();

    const closedBy = (tr.dataset.closedBy || '').trim();
    const closedAt = (tr.dataset.closedAt || '').trim();

    const notes = (tr.dataset.notes || '').trim();

    titleText.textContent = `${sev || 'N/A'} — ${device || '—'}`;

    elCode.textContent = code;
    elAssigned.textContent = assigned;

    // OJO: tu template usa id="tkt-created-by"
    const createdEl = Q('#tkt-created-by');
    if (createdEl) createdEl.textContent = created;

    elOpened.textContent = opened;
    elUpdated.textContent = updated;
    elTenant.textContent = tenant;
    elDue.textContent = due ? formatLongCL(due) : '—';
    setStatusBadge(status);

    elAlarmId.textContent = alarmId;
    elDevice.textContent = device;
    elType.textContent = type;

    const dt = (eventDate || eventTime) ? `${eventDate || '—'} ${eventTime || ''}`.trim() : '—';
    elDatetime.textContent = dt;

    elSevPill.innerHTML = `<span class="pill ${pillClassFromSeverity(sev)}">${esc(sev || 'N/A')}</span>`;

    elRiesgo.textContent = riesgo || '—';
    elAnalisis.textContent = analisis || '—';
    elAcciones.textContent = acciones || '—';

    if (appWrap && elApp) {
      if (app) {
        appWrap.style.display = '';
        elApp.textContent = app;
      } else {
        appWrap.style.display = 'none';
        elApp.textContent = '';
      }
    }

    // cerrado por / fecha cierre (solo mostrar si está cerrado y viene info)
    const isClosed = (status || '').toUpperCase() === 'CLOSED';
    if (wrapClosedBy && wrapClosedAt && elClosedBy && elClosedAt) {
      if (isClosed) {
        wrapClosedBy.style.display = '';
        wrapClosedAt.style.display = '';
        elClosedBy.textContent = closedBy || '—';
        elClosedAt.textContent = closedAt || '—';
      } else {
        wrapClosedBy.style.display = 'none';
        wrapClosedAt.style.display = 'none';
        elClosedBy.textContent = '—';
        elClosedAt.textContent = '—';
      }
    }

    // Observaciones dentro del mismo grid
    if (wrapNotes && elNotes) {
      if (notes) {
        wrapNotes.style.display = '';
        elNotes.textContent = notes;
      } else {
        wrapNotes.style.display = 'none';
        elNotes.textContent = '—';
      }
    }
  }

  // ===== events =====
  table.addEventListener('click', (ev) => {
    const tr = ev.target.closest('tr.ticket-row');
    if (!tr) return;
    fillFromRow(tr);
    openModalDetail();
  });

  // cerrar detalle
  backdrop?.addEventListener('click', closeModalDetailFully);
  closeBtn?.addEventListener('click', closeModalDetailFully);
  closeBtn2?.addEventListener('click', closeModalDetailFully);

  // detalle -> observaciones
  btnOpenClose?.addEventListener('click', (ev) => {
    stopAll(ev);
    if (!selectedRow) return;

    // next tick por si hay listeners globales
    setTimeout(() => openCloseNotesModal(), 0);
  });

  // cerrar observaciones
  closeBackdrop?.addEventListener('click', closeCloseNotesModal);
  closeX?.addEventListener('click', closeCloseNotesModal);
  closeCancel?.addEventListener('click', (ev) => { stopAll(ev); closeCloseNotesModal(); });

  // ✅ éxito estilo "Exportación": NO cerrar al click en backdrop, solo OK
  // successBackdrop?.addEventListener('click', closeSuccessModalAndReload); // intencionalmente OFF
  successOk?.addEventListener('click', (ev) => { stopAll(ev); closeSuccessModalAndReload(); });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;

    // prioridad: éxito -> observaciones -> detalle
    if (!successModal.classList.contains('hidden')) {
      closeSuccessModalAndReload();
      return;
    }
    if (!closeModal.classList.contains('hidden')) {
      closeCloseNotesModal();
      return;
    }
    closeModalDetailFully();
  });

  // ✅ Submit por AJAX: cierra 2 modales y abre éxito
  closeForm?.addEventListener('submit', async (ev) => {
    stopAll(ev);
    if (!selectedRow || !closeForm.action) return;

    if (closeConfirmBtn) closeConfirmBtn.disabled = true;

    try {
      const fd = new FormData(closeForm);
      const csrfCookie = getCookie('csrftoken');
      const csrfForm = getCsrfTokenFromForm();

      const res = await fetch(closeForm.action, {
        method: 'POST',
        body: fd,
        credentials: 'same-origin',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          ...(csrfCookie ? { 'X-CSRFToken': csrfCookie } : (csrfForm ? { 'X-CSRFToken': csrfForm } : {})),
        }
      });

      const ct = (res.headers.get('content-type') || '').toLowerCase();
      const data = ct.includes('application/json') ? await res.json() : null;

      if (!res.ok || (data && data.ok === false)) {
        const msg = (data && (data.error || data.message)) ? (data.error || data.message) : 'No se pudo cerrar el ticket.';
        alert(msg);
        if (closeConfirmBtn) closeConfirmBtn.disabled = false;
        return;
      }

      // ✅ actualizar dataset local (por si vuelve a abrir sin reload)
      selectedRow.dataset.status = 'CLOSED';
      selectedRow.dataset.notes = (fd.get('notes') || '').toString();

      // cerrar ambas modales y abrir éxito
      closeCloseNotesModal();
      closeModalDetailFully();
      openSuccessModal();

    } catch (err) {
      console.error(err);
      alert('Error de red al cerrar el ticket.');
      if (closeConfirmBtn) closeConfirmBtn.disabled = false;
    }
  });

})();
