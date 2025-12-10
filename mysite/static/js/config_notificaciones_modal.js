function toggleConfigModal(show = true) {
  const modal = document.getElementById("configModal");
  if (!modal) return;

  if (show) {
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
  } else {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
  }
}

function showSaveToastAndClose() {
  const toast = document.getElementById("saveToast");
  if (!toast) return;

  // Mostrar toast
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("show"), 20);

  // Ocultar toast y cerrar modal después
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => {
      toast.classList.add("hidden");
      toggleConfigModal(false);
    }, 400);
  }, 2500);
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("configForm");
  const overlay = document.getElementById("configModal");
  const toggleTelefono = document.getElementById("toggleTelefono");
  const franja = document.getElementById("franjaHoraria");
  const toggleTelegram = document.getElementById("toggleTelegram");
  const qrContainer = document.getElementById("qrTelegram");

  // ============================
  // Rellenar selects de horario
  // ============================
  function initTimeSelect(id) {
    const select = document.getElementById(id);
    if (!select) return;

    // Limpiar por si acaso
    select.innerHTML = "";

    const times = [];

    // Intervalos cada 30 minutos desde 00:00 a 23:30
    for (let h = 0; h < 24; h++) {
      const hh = String(h).padStart(2, "0");
      times.push(`${hh}:00`);
      times.push(`${hh}:30`);
    }

    // Aseguramos 23:59 como último valor posible
    if (!times.includes("23:59")) {
      times.push("23:59");
    }

    times.forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t;
      opt.textContent = t;
      select.appendChild(opt);
    });

    // Valor actual desde el backend (data-current-value)
    const current = select.dataset.currentValue;
    if (current && times.includes(current)) {
      select.value = current;
    } else {
      // Defaults si no hay valor
      if (id === "hora_inicio") {
        select.value = "00:00";
      }
      if (id === "hora_fin") {
        select.value = "23:59";
      }
    }
  }

  // Inicializar ambos selects
  initTimeSelect("hora_inicio");
  initTimeSelect("hora_fin");

  // ============================
  // Submit AJAX del formulario
  // ============================
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault(); // Evita el submit normal
      const loader = document.getElementById("loading-overlay");

      // Asegura que el loader esté oculto antes de empezar
      if (loader) loader.style.display = "none";

      try {
        const res = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          headers: {
            "X-Requested-With": "XMLHttpRequest",
          },
        });

        // Vuelve a ocultar el loader si algún script lo activó
        if (loader) loader.style.display = "none";

        if (!res.ok) {
          console.error("Error guardando preferencias", res.status);
          return;
        }

        // Mostrar mensaje y cerrar modal
        showSaveToastAndClose();
      } catch (err) {
        console.error("Error de red al guardar preferencias", err);
        if (loader) loader.style.display = "none";
      }
    });
  }

  // ============================
  // Cerrar modal clicando fuera
  // ============================
  if (overlay) {
    overlay.addEventListener("click", (ev) => {
      if (ev.target === overlay) {
        toggleConfigModal(false);
      }
    });
  }

  // ============================
  // Mostrar/ocultar franja horaria según Teléfono
  // ============================
  if (toggleTelefono && franja) {
    function updateFranja() {
      franja.classList.toggle("hidden", !toggleTelefono.checked);
    }

    toggleTelefono.addEventListener("change", updateFranja);
    updateFranja(); // Inicializa al cargar
  }

  // ============================
  // Mostrar/ocultar QR según Telegram
  // ============================
  if (toggleTelegram && qrContainer) {
    function updateQR() {
      qrContainer.classList.toggle("hidden", !toggleTelegram.checked);
    }

    toggleTelegram.addEventListener("change", updateQR);
    updateQR(); // Inicializa al cargar
  }
});
