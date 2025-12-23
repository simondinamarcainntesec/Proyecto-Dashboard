// static/two_factor/js/tf_setup.js
(function () {
  const form = document.getElementById('tf-setup-form');
  if (!form) return;

  const step = (form.getAttribute('data-step') || '').toLowerCase();

  // Solo nos interesa interceptar en el paso generator
  if (step !== 'generator') return;

  // token sin spinners + solo números
  const token = form.querySelector('input[name="token"]');
  if (token) {
    token.setAttribute('type', 'text');
    token.setAttribute('inputmode', 'numeric');
    token.setAttribute('autocomplete', 'one-time-code');
    token.setAttribute('pattern', '[0-9]*');
    token.setAttribute('maxlength', '6');
  }

  const backdrop = document.getElementById('tfOkBackdrop');
  const okBtn = document.getElementById('tfOkBtn');

  function openOkModal(nextUrl) {
    window.__tfNextUrl = nextUrl || '/admin/';
    backdrop.classList.add('is-open');
    backdrop.setAttribute('aria-hidden', 'false');
    if (okBtn) okBtn.focus();
  }

  if (okBtn) {
    okBtn.addEventListener('click', function () {
      window.location.href = window.__tfNextUrl || '/admin/';
    });
  }

  form.addEventListener('submit', async function (e) {
    e.preventDefault();

    const fd = new FormData(form);

    try {
      const resp = await fetch(window.location.href, {
        method: 'POST',
        body: fd,
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });

      // fetch sigue redirects -> resp.url es el destino final
      const finalUrl = resp.url || '';

      // Éxito: si terminó en admin o en setup/complete, mostramos modal
      if (finalUrl.includes('/admin') || finalUrl.includes('/two_factor/setup/complete')) {
        openOkModal('/admin/');
        return;
      }

      // Si no fue éxito, reinyectamos HTML (por ejemplo error de token)
      const html = await resp.text();
      document.open();
      document.write(html);
      document.close();

    } catch (err) {
      // fallback normal (redirige)
      form.submit();
    }
  });
})();
