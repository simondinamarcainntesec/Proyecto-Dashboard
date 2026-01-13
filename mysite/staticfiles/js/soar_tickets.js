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

  // initial notes
  const wrapInitialNotes = Q('#tkt-initial-notes-wrap');
  const elInitialNotes = Q('#tkt-initial-notes');

  // notes
  const wrapNotes = Q('#tkt-notes-wrap');
  const elNotes = Q('#tkt-notes');

  // ===== Editor vencimiento (IDs alineados al template) =====
  const btnDueEdit = Q('#tkt-due-edit-btn');
  const dueEditWrap = Q('#tkt-due-edit');
  const dueInput = Q('#tkt-due-input');
  const dueSaveBtn = Q('#tkt-due-save');
  const dueCancelBtn = Q('#tkt-due-cancel');
  const dueHint = Q('#tkt-due-help');

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

  // ✅ elementos internos para reutilizar texto
  const successTitleEl = Q('#ticketSuccessTitle');
  const successTextEl = successModal.querySelector('.success-info-text');

  // ✅ controla si al cerrar la modal hay que recargar o no
  let successShouldReload = true;

  let selectedRow = null;

  // helpers
  function esc(s) { return String(s ?? ''); }

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

  // OPEN / CLOSED / OVERDUE
  function setStatusBadge(status) {
    const st = (status || 'OPEN').toUpperCase();

    if (st === 'CLOSED') {
      elStatusBadge.innerHTML = `<span class="state-badge is-closed">Cerrado</span>`;
      if (btnOpenClose) btnOpenClose.style.display = 'none';
      return;
    }

    if (st === 'OVERDUE') {
      elStatusBadge.innerHTML = `<span class="state-badge is-overdue">Vencido</span>`;
      if (btnOpenClose) btnOpenClose.style.display = '';
      return;
    }

    elStatusBadge.innerHTML = `<span class="state-badge is-open">Abierto</span>`;
    if (btnOpenClose) btnOpenClose.style.display = '';
  }

  function getCookie(name) {
    const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return m ? decodeURIComponent(m[2]) : '';
  }

  function getCsrfTokenFromForm() {
    const inp = closeForm?.querySelector('input[name="csrfmiddlewaretoken"]');
    return inp ? inp.value : '';
  }

  function getDueUrl(ticketId) {
    const tpl = table.dataset.dueUrlTemplate || '';
    if (!tpl) return `due/${ticketId}/`;
    return tpl.replace('999999', String(ticketId));
  }

  function setRowStatusBadge(tr, status) {
    if (!tr) return;
    const td = tr.querySelector('td .state-badge')?.closest('td');
    if (!td) return;

    const st = (status || 'OPEN').toUpperCase();
    if (st === 'CLOSED') td.innerHTML = `<span class="state-badge is-closed">Cerrado</span>`;
    else if (st === 'OVERDUE') td.innerHTML = `<span class="state-badge is-overdue">Vencido</span>`;
    else td.innerHTML = `<span class="state-badge is-open">Abierto</span>`;
  }

  // ===== modal open/close =====
  function openModalDetail() {
    document.body.classList.add('modal-open');
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
  }

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

    const existing = (selectedRow?.dataset?.notes || '').trim();
    notesTextarea.value = existing || '';

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

  // ✅ ahora acepta texto + si recarga o no
  function openSuccessModal(opts = {}) {
    const title = opts.title ?? 'Ticket cerrado con éxito';
    const text = opts.text ?? 'El ticket fue actualizado y guardado correctamente.';
    successShouldReload = (opts.reloadOnClose ?? true);

    if (successTitleEl) successTitleEl.textContent = title;
    if (successTextEl) successTextEl.textContent = text;

    document.body.classList.add('modal-open');
    successModal.classList.remove('hidden');
    successModal.setAttribute('aria-hidden', 'false');
  }

  function closeSuccessModal() {
    successModal.classList.add('hidden');
    successModal.setAttribute('aria-hidden', 'true');

    if (successShouldReload) {
      document.body.classList.remove('modal-open');
      location.reload();
      return;
    }

    // ✅ si no hay otros modales abiertos, saca modal-open
    const detailIsOpen = !modal.classList.contains('hidden');
    const closeIsOpen = !closeModal.classList.contains('hidden');
    if (!detailIsOpen && !closeIsOpen) {
      document.body.classList.remove('modal-open');
    }
  }

  // evitar clicks dentro de cards = "afuera"
  detailCard?.addEventListener('click', (e) => e.stopPropagation());
  closeCard?.addEventListener('click', (e) => e.stopPropagation());
  successCard?.addEventListener('click', (e) => e.stopPropagation());

  // ===== Editor vencimiento UI =====
  function resetDueEditor() {
    if (dueEditWrap) dueEditWrap.style.display = 'none';
    if (btnDueEdit) btnDueEdit.style.display = 'none';
    if (dueHint) dueHint.style.display = 'none';
    if (dueInput) dueInput.value = '';
    if (dueSaveBtn) dueSaveBtn.disabled = false;
  }

  function getCurrentUserId() {
    const v = document.body?.dataset?.userId;
    return v ? String(v) : '';
  }

  function computeRowStatus(tr) {
    const isOverdue = String(tr?.dataset?.isOverdue || '0') === '1';
    if (isOverdue) return 'OVERDUE';
    return String(tr?.dataset?.status || 'OPEN').toUpperCase();
  }

  function canEditDueForRow(tr) {
    const userId = getCurrentUserId();
    const createdId = String(tr?.dataset?.createdId || '');
    const st = computeRowStatus(tr);
    return !!userId && !!createdId && userId === createdId && st !== 'CLOSED';
  }

  function showDueEditor(tr) {
    if (!tr) return;

    const canEdit = canEditDueForRow(tr);
    const currentDue = (tr.dataset.due || '').trim();

    if (btnDueEdit) btnDueEdit.style.display = canEdit ? '' : 'none';
    if (dueHint) dueHint.style.display = canEdit ? 'none' : '';

    if (dueEditWrap) dueEditWrap.style.display = 'none';
    if (dueInput) dueInput.value = currentDue || '';
    if (dueSaveBtn) dueSaveBtn.disabled = false;
  }

  async function saveDueDateForSelected() {
    if (!selectedRow) return;

    if (!canEditDueForRow(selectedRow)) {
      alert('Solo el creador puede cambiar el vencimiento.');
      return;
    }

    const ticketId = selectedRow.dataset.ticketId;
    const newDue = (dueInput?.value || '').trim();

    if (!ticketId || !newDue) {
      alert('Debes seleccionar una fecha válida.');
      return;
    }

    if (dueSaveBtn) dueSaveBtn.disabled = true;

    try {
      const url = getDueUrl(ticketId);

      const fd = new FormData();
      fd.append('due_date', newDue);

      const csrfCookie = getCookie('csrftoken');
      const csrfForm = getCsrfTokenFromForm();

      const res = await fetch(url, {
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
        const msg =
          (data && (data.error || data.message)) ? (data.error || data.message) :
          `No se pudo actualizar el vencimiento. (${res.status})`;
        alert(msg);
        if (dueSaveBtn) dueSaveBtn.disabled = false;
        return;
      }

      // ✅ actualizar local
      const dueIso = data?.due_date || newDue;
      const st = String((data?.status || selectedRow.dataset.status || 'OPEN')).toUpperCase();

      selectedRow.dataset.due = dueIso;
      selectedRow.dataset.status = st;
      selectedRow.dataset.isOverdue = (st === 'OVERDUE') ? '1' : '0';

      // UI: fecha + badge modal
      elDue.textContent = dueIso ? formatLongCL(dueIso) : '—';
      elDue.classList.toggle('is-overdue', st === 'OVERDUE');
      setStatusBadge(st);

      // UI: badge en la tabla
      setRowStatusBadge(selectedRow, st);

      // cerrar editor
      if (dueEditWrap) dueEditWrap.style.display = 'none';
      if (dueSaveBtn) dueSaveBtn.disabled = false;

      // refrescar visibilidad del botón por si cambió el estado
      showDueEditor(selectedRow);

      // ✅ REUTILIZA la misma modal de éxito (SIN recargar)
      openSuccessModal({
        title: 'Vencimiento actualizado',
        text: 'La fecha de vencimiento fue actualizada correctamente.',
        reloadOnClose: false
      });

    } catch (err) {
      console.error(err);
      alert('Error de red al actualizar vencimiento.');
      if (dueSaveBtn) dueSaveBtn.disabled = false;
    }
  }

  btnDueEdit?.addEventListener('click', (ev) => {
    stopAll(ev);
    if (!selectedRow) return;
    if (dueEditWrap) dueEditWrap.style.display = '';
    if (dueInput) dueInput.focus();
  });

  dueCancelBtn?.addEventListener('click', (ev) => {
    stopAll(ev);
    if (dueEditWrap) dueEditWrap.style.display = 'none';
    if (dueSaveBtn) dueSaveBtn.disabled = false;
  });

  dueSaveBtn?.addEventListener('click', (ev) => {
    stopAll(ev);
    saveDueDateForSelected();
  });

  // ===== fill detail =====
  function fillFromRow(tr) {
    selectedRow = tr;

    resetDueEditor();

    const code = tr.dataset.ticketCode || '—';
    const alarmId = tr.dataset.alarmId || '—';
    const device = tr.dataset.device || '—';
    const type = tr.dataset.type || '—';
    const sev = tr.dataset.sev || 'N/A';

    const status = computeRowStatus(tr);

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

    const initialNotes = (tr.dataset.initialNotes || '').trim();
    const notes = (tr.dataset.notes || '').trim();

    titleText.textContent = `${sev || 'N/A'} — ${device || '—'}`;

    elCode.textContent = code;
    elAssigned.textContent = assigned;

    const createdEl = Q('#tkt-created-by');
    if (createdEl) createdEl.textContent = created;

    elOpened.textContent = opened;
    elUpdated.textContent = updated;
    elTenant.textContent = tenant;

    elDue.textContent = due ? formatLongCL(due) : '—';

    elDue.classList.toggle('is-overdue', status === 'OVERDUE');
    setStatusBadge(status);

    showDueEditor(tr);

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

    const isClosed = status === 'CLOSED';
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

    if (wrapInitialNotes && elInitialNotes) {
      if (initialNotes) {
        wrapInitialNotes.style.display = '';
        elInitialNotes.textContent = initialNotes;
      } else {
        wrapInitialNotes.style.display = 'none';
        elInitialNotes.textContent = '—';
      }
    }

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
    setTimeout(() => openCloseNotesModal(), 0);
  });

  // cerrar observaciones
  closeBackdrop?.addEventListener('click', closeCloseNotesModal);
  closeX?.addEventListener('click', closeCloseNotesModal);
  closeCancel?.addEventListener('click', (ev) => { stopAll(ev); closeCloseNotesModal(); });

  // ✅ éxito (ahora respeta reloadOnClose)
  successBackdrop?.addEventListener('click', (ev) => { stopAll(ev); closeSuccessModal(); });
  successOk?.addEventListener('click', (ev) => { stopAll(ev); closeSuccessModal(); });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;

    if (!successModal.classList.contains('hidden')) {
      closeSuccessModal();
      return;
    }
    if (!closeModal.classList.contains('hidden')) {
      closeCloseNotesModal();
      return;
    }
    closeModalDetailFully();
  });

  // Submit por AJAX: cerrar ticket
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

      selectedRow.dataset.status = 'CLOSED';
      selectedRow.dataset.isOverdue = '0';
      selectedRow.dataset.notes = (fd.get('notes') || '').toString();
      setRowStatusBadge(selectedRow, 'CLOSED');

      closeCloseNotesModal();
      closeModalDetailFully();

      // ✅ misma modal, pero para cierre con recarga
      openSuccessModal({
        title: 'Ticket cerrado con éxito',
        text: 'El ticket fue actualizado y guardado correctamente.',
        reloadOnClose: true
      });

    } catch (err) {
      console.error(err);
      alert('Error de red al cerrar el ticket.');
      if (closeConfirmBtn) closeConfirmBtn.disabled = false;
    }
  });

})();
