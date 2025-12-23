// static/js/home_ip_tickets.js
// Búsqueda de IP por AJAX + creación de tickets (blacklist/whitelist) + loader local

(function () {
  /* ===========================
   * Loader local "Creando ticket…"
   * =========================== */
  function showTicketLoading(msg) {
    const ov = document.getElementById('ticketLoadingOverlay');
    if (!ov) return;

    const txt = ov.querySelector('.ticket-loading-text');
    if (txt) {
      txt.textContent = msg || 'Creando ticket…';
    }

    ov.classList.remove('hidden');
    ov.setAttribute('aria-hidden', 'false');
  }

  function hideTicketLoading() {
    const ov = document.getElementById('ticketLoadingOverlay');
    if (!ov) return;
    ov.classList.add('hidden');
    ov.setAttribute('aria-hidden', 'true');
  }

  /* ===========================
   * Modal de confirmación
   * =========================== */
  function showTicketDialog(message, type) {
    const overlay = document.getElementById('ticketDialog');
    const textEl = document.getElementById('ticketDialogText');
    const titleEl = document.getElementById('ticketDialogTitle');
    const iconWrap = document.getElementById('ticketDialogIcon');
    const iconChar = document.getElementById('ticketDialogIconChar');

    if (!overlay || !textEl || !titleEl || !iconWrap || !iconChar) {
      // Fallback por si algo falta
      alert(message || 'Operación realizada.');
      return;
    }

    const isSuccess = type === 'success';

    titleEl.textContent = isSuccess ? 'Solicitud enviada' : 'Ocurrió un problema';
    textEl.textContent =
      message ||
      (isSuccess
        ? 'La solicitud se procesó correctamente.'
        : 'No se pudo completar la operación. Intenta nuevamente más tarde.');

    iconWrap.classList.remove('is-success', 'is-error');
    if (isSuccess) {
      iconWrap.classList.add('is-success');
      iconChar.textContent = '✔';
    } else {
      iconWrap.classList.add('is-error');
      iconChar.textContent = '✖';
    }

    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
  }

  /* ===========================
   * Envío de ticket por AJAX
   * =========================== */
  async function sendIpTicketAjax(event, form) {
    event.preventDefault();

    const submitBtn = form.querySelector('button[type="submit"]');
    const originalHtml = submitBtn ? submitBtn.innerHTML : null;

    if (submitBtn) {
      submitBtn.disabled = true;
      form.classList.add('is-loading');
    }

    const formData = new FormData(form);

    // Loader local
    showTicketLoading('Creando ticket…');

    try {
      const resp = await fetch(form.action, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData,
      });

      let data = null;
      try {
        data = await resp.json();
      } catch (parseErr) {
        console.error('No se pudo parsear JSON de respuesta:', parseErr);
      }

      let msg = 'No se pudo enviar la solicitud. Intenta nuevamente más tarde.';
      let type = 'error';

      if (data && typeof data.message === 'string') {
        msg = data.message;
      }
      if (data && data.ok) {
        type = 'success';
      }

      // Mostrar modal de confirmación
      showTicketDialog(msg, type);
    } catch (err) {
      console.error('Error en solicitud AJAX de ticket:', err);
      showTicketDialog(
        'No se pudo enviar la solicitud. Intenta nuevamente más tarde.',
        'error'
      );
    } finally {
      // Quitar loader siempre
      hideTicketLoading();

      if (submitBtn) {
        submitBtn.disabled = false;
        form.classList.remove('is-loading');
        if (originalHtml !== null) {
          submitBtn.innerHTML = originalHtml;
        }
      }
    }

    return false;
  }

  /* ===========================
   * Búsqueda de IP por AJAX
   * =========================== */
  async function submitIpSearchAjax(event, form) {
    event.preventDefault();

    const params = new URLSearchParams(new FormData(form));
    const url = form.action + '?' + params.toString();

    try {
      const resp = await fetch(url, {
        method: 'GET',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
      });

      const html = await resp.text();
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');

      const newModal = doc.getElementById('ipSearchModal');
      const modal = document.getElementById('ipSearchModal');
      if (!newModal || !modal) {
        console.error('No se encontró el modal en la respuesta.');
        showTicketDialog(
          'No se pudo obtener el resultado de la búsqueda.',
          'error'
        );
        return false;
      }

      const newBody = newModal.querySelector('.modal-body');
      const newFoot = newModal.querySelector('.modal-foot');

      const curBody = modal.querySelector('.modal-body');
      const curFoot = modal.querySelector('.modal-foot');

      if (newBody && curBody) {
        curBody.innerHTML = newBody.innerHTML;
      }
      if (newFoot && curFoot) {
        curFoot.innerHTML = newFoot.innerHTML;
      }

      // Mostrar siempre la modal de IP después de la búsqueda
      modal.classList.remove('hidden');
      modal.setAttribute('aria-hidden', 'false');
    } catch (err) {
      console.error('Error en búsqueda AJAX de IP:', err);
      showTicketDialog(
        'No se pudo completar la búsqueda. Intenta nuevamente.',
        'error'
      );
    }

    return false;
  }

  // Exponer por si lo necesitas en consola
  window.showTicketDialog = showTicketDialog;
  window.sendIpTicketAjax = sendIpTicketAjax;
  window.submitIpSearchAjax = submitIpSearchAjax;

  /* ===========================
   * Delegación de eventos
   * =========================== */
  document.addEventListener('DOMContentLoaded', function () {
    // Asegurar loader oculto al cargar
    hideTicketLoading();

    // Botón OK del modal de confirmación
    const okBtn = document.getElementById('ticketDialogOkBtn');
    if (okBtn) {
      okBtn.addEventListener('click', function () {
        const overlay = document.getElementById('ticketDialog');
        if (overlay) {
          overlay.classList.add('hidden');
          overlay.setAttribute('aria-hidden', 'true');
        }

        // Cerrar modal de IP
        if (typeof window.toggleIpModal === 'function') {
          window.toggleIpModal(false);
        } else {
          const ipModal = document.getElementById('ipSearchModal');
          if (ipModal) {
            ipModal.classList.add('hidden');
            ipModal.setAttribute('aria-hidden', 'true');
          }
        }
      });
    }

    // Delegación de submit: buscadores + footer tickets
    document.addEventListener('submit', function (e) {
      const form = e.target;
      if (!(form instanceof HTMLFormElement)) return;

      if (form.classList.contains('home-ip-form')) {
        submitIpSearchAjax(e, form);
      } else if (form.classList.contains('ip-footer-form')) {
        sendIpTicketAjax(e, form);
      }
    });
  });
})();
