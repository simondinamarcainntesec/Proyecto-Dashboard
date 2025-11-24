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
  window.location.href = base;
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

// === Envío AJAX para formularios de creación de tickets (blacklist / whitelist) ===
document.addEventListener("DOMContentLoaded", function () {
  const forms = document.querySelectorAll(".ip-footer-form");

  if (!forms.length) return;

  forms.forEach(function (form) {
    form.addEventListener("submit", async function (e) {
      e.preventDefault(); // evita el submit clásico (recarga de página)

      const submitBtn = form.querySelector('button[type="submit"]');
      const originalHtml = submitBtn ? submitBtn.innerHTML : null;

      if (submitBtn) {
        submitBtn.disabled = true;
        form.classList.add("is-loading");
      }

      const formData = new FormData(form);

      try {
        const resp = await fetch(form.action, {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
          },
          body: formData,
        });

        let data;
        try {
          data = await resp.json();
        } catch (parseErr) {
          console.error("Error parseando JSON de respuesta:", parseErr);
          data = {
            ok: false,
            message: "No se pudo procesar la respuesta del servidor.",
          };
        }

        const msg =
          (data && data.message) ||
          (data && data.ok
            ? "Solicitud enviada correctamente."
            : "No se pudo enviar la solicitud. Intenta nuevamente más tarde.");

        // Mensaje simple al usuario (puedes cambiar alert por un toast más adelante)
        alert(msg);

        if (data && data.ok === true) {
          // Si quieres, cerramos la modal al éxito
          if (typeof toggleIpModal === "function") {
            toggleIpModal(false);
          }
        }
      } catch (err) {
        console.error("Error enviando solicitud de ticket:", err);
        alert("No se pudo enviar la solicitud. Intenta nuevamente más tarde.");
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          form.classList.remove("is-loading");
          if (originalHtml !== null) {
            submitBtn.innerHTML = originalHtml;
          }
        }
      }
    });
  });
});
