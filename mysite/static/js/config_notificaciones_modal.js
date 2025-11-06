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
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault(); // Evita el submit normal
    const loader = document.getElementById("loading-overlay");

    // 🔹 Asegura que el loader esté oculto antes de empezar
    if (loader) loader.style.display = "none";

    try {
      const res = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      });

      // 🔹 Vuelve a ocultar el loader si algún script lo activó
      if (loader) loader.style.display = "none";

      if (!res.ok) {
        console.error("Error guardando preferencias", res.status);
        return;
      }

      // ✅ Mostrar mensaje y cerrar modal
      showSaveToastAndClose();
    } catch (err) {
      console.error("Error de red al guardar preferencias", err);
      if (loader) loader.style.display = "none";
    }
  });


  // Cerrar modal clicando fuera
  const overlay = document.getElementById("configModal");
  overlay?.addEventListener("click", (ev) => {
    if (ev.target === overlay) {
      toggleConfigModal(false);
    }
  });
});
