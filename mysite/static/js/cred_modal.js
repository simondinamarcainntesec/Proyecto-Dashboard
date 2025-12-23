// static/js/cred_modal.js
(() => {
  "use strict";

  const modal = document.getElementById("credModal");

  // Helpers
  function isModalOpen() {
    return !!modal && !modal.classList.contains("hidden");
  }

  function lockScroll(lock) {
    // Si ya usas esta clase en otras modals, mantenla.
    // Si no existe CSS asociado, no rompe nada.
    document.documentElement.classList.toggle("modal-open", lock);
    document.body.classList.toggle("modal-open", lock);
  }

  function setAria(open) {
    if (!modal) return;
    modal.setAttribute("aria-hidden", open ? "false" : "true");
  }

  // Exponer igual para no romper onclick aunque no exista el DOM (otras páginas)
  window.toggleCredModal = function (show) {
    if (!modal) return;

    if (show) {
      modal.classList.remove("hidden");
      setAria(true);
      lockScroll(true);

      // Enfocar el primer botón útil (opcional)
      const focusable = modal.querySelector(
        ".cred-close, button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])"
      );
      if (focusable) focusable.focus();
    } else {
      modal.classList.add("hidden");
      setAria(false);
      lockScroll(false);
    }
  };

  window.toggleBlockInput = function (btn) {
    try {
      const block = btn && btn.closest ? btn.closest(".cred-block") : null;
      const input = block ? block.querySelector(".cred-input") : null;
      if (!input) return;

      const wasHidden = input.type === "password";
      input.type = wasHidden ? "text" : "password";
      btn.textContent = wasHidden ? "Ocultar" : "Ver";

      // Evitar que quede seleccionado raro
      input.blur();
    } catch (_) {}
  };

  window.copyBlockInput = async function (btn) {
    try {
      const block = btn && btn.closest ? btn.closest(".cred-block") : null;
      const input = block ? block.querySelector(".cred-input") : null;
      if (!input) return;

      const value = (input.value || "").trim();
      if (!value) return;

      const prevType = input.type;

      // Clipboard API (preferido)
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
      } else {
        // Fallback clásico
        input.type = "text";
        input.focus();
        input.select();
        document.execCommand("copy");
        input.type = prevType;
        input.blur();
      }

      // Feedback simple
      const old = btn.textContent;
      btn.textContent = "Copiado";
      btn.disabled = true;

      window.setTimeout(() => {
        btn.textContent = old;
        btn.disabled = false;
      }, 900);
    } catch (e) {
      console.warn("[cred_modal] No se pudo copiar:", e);
    }
  };

  window.openDownloadPage = function () {
    const urlInput = document.getElementById("cred-url");
    const url = urlInput && urlInput.value ? urlInput.value.trim() : "";
    if (!url) return;

    window.open(url, "_blank", "noopener,noreferrer");
  };

  // Cerrar al click en el fondo + evitar cierre al click dentro
  if (modal) {
    // Click en overlay => cerrar
    modal.addEventListener("mousedown", (e) => {
      if (e.target === modal) window.toggleCredModal(false);
    });

    // Click dentro de la tarjeta => no cerrar
    const card = modal.querySelector(".cred-card");
    if (card) {
      card.addEventListener("mousedown", (e) => e.stopPropagation());
    }

    // Escape para cerrar
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && isModalOpen()) {
        window.toggleCredModal(false);
      }
    });

    // Botones de cerrar (por si quieres eliminar onclick del HTML en el futuro)
    const closeBtns = modal.querySelectorAll(".cred-close, [data-cred-close]");
    closeBtns.forEach((b) => {
      b.addEventListener("click", (e) => {
        // Si el botón ya tiene onclick, esto no estorba
        e.preventDefault();
        window.toggleCredModal(false);
      });
    });
  }
})();
