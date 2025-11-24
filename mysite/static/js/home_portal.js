// ========= Utils =========
function getCookie(name) {
  const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return m ? m.pop() : '';
}

function getCsrfToken() {
  return getCookie('csrftoken');
}

// ========= Modal IPs =========
function toggleIpModal(show) {
  const el = document.getElementById('ipSearchModal');
  if (!el) return;
  if (show) {
    el.classList.remove('hidden');
    el.setAttribute('aria-hidden', 'false');
  } else {
    el.classList.add('hidden');
    el.setAttribute('aria-hidden', 'true');
  }
}

// ========= Credenciales Modal =========
function toggleCredModal(show) {
  const el = document.getElementById('credModal');
  if (!el) return;
  if (show) {
    el.classList.remove('hidden');
    el.setAttribute('aria-hidden', 'false');
  } else {
    el.classList.add('hidden');
    el.setAttribute('aria-hidden', 'true');
  }
}

function copyBlockInput(btn) {
  const input = btn.closest('.cred-block')?.querySelector('input');
  if (!input) return;
  input.select();
  input.setSelectionRange(0, 99999);

  try {
    document.execCommand('copy');
  } catch (e) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(input.value);
    }
  }

  btn.textContent = 'Copiado';
  setTimeout(() => {
    btn.textContent = 'Copiar';
  }, 1200);
}

function toggleBlockInput(btn) {
  const input = btn.closest('.cred-block')?.querySelector('input');
  if (!input) return;
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = 'Ocultar';
  } else {
    input.type = 'password';
    btn.textContent = 'Ver';
  }
}

// ========= Abrir página de login/descarga en nueva pestaña =========
function openDownloadPage() {
  const base = document.getElementById('cred-url')?.value;
  if (!base) return;
  window.open(base, '_blank', 'noopener');
}

// ========= Menú usuario =========
(function () {
  const btn = document.getElementById('userButton');
  const menu = document.querySelector('.user-menu .dropdown-menu');
  if (!btn || !menu) return;

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.classList.toggle('is-open');
  });

  document.addEventListener('click', () => {
    menu.classList.remove('is-open');
  });
})();
