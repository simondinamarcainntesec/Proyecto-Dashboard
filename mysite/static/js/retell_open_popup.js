// static/js/retell_open_popup.js
(function () {
  const POPUP_NAME = "retell_call_popup";

  let popupRef = null;

  function getPopupUrl() {
    const u = window.__RETELL_POPUP_URL;
    return (u && String(u).trim()) ? String(u).trim() : "/integrations/retell/call/";
  }

  window.openRetellCallWindow = function openRetellCallWindow() {
    // Si ya existe, solo focus
    if (popupRef && !popupRef.closed) {
      try { popupRef.focus(); } catch (_) {}
      return;
    }

    const features = [
      "popup=yes",
      "width=420",
      "height=720",
      "left=120",
      "top=80",
      "resizable=yes",
      "scrollbars=yes",
    ].join(",");

    // CLAVE: abrir SIN async/await para evitar bloqueo
    popupRef = window.open("about:blank", POPUP_NAME, features);

    if (!popupRef) {
      alert("El navegador bloqueó la ventana. Permite popups para este sitio y vuelve a intentar.");
      return;
    }

    try {
      popupRef.location = getPopupUrl();
      popupRef.focus();
    } catch (_) {
      // fallback
      try { popupRef.close(); } catch (_) {}
      popupRef = null;
      alert("No se pudo abrir la ventana de llamada. Revisa permisos de popups.");
    }
  };

  // (Opcional) si más adelante vuelves a agregar indicador en Home, aquí puedes escuchar postMessage.
  // Ahora no hace nada si no existen elementos.
  window.addEventListener("message", (ev) => {
    if (ev.origin !== window.location.origin) return;
    const data = ev.data || {};
    if (data.source !== "retell") return;

    // Si en Home vuelves a agregar IDs callMicWrap/callMicBtn/retellStatus, aquí los puedes actualizar.
    // Lo dejo sin romper aunque no existan.
    const wrap = document.getElementById("callMicWrap");
    const micBtn = document.getElementById("callMicBtn");
    const statusEl = document.getElementById("retellStatus");

    if (data.type === "call_started") {
      if (wrap) wrap.classList.remove("hidden");
      if (statusEl) statusEl.textContent = "Llamada activa";
    }

    if (data.type === "call_ended" || data.type === "call_error") {
      if (wrap) wrap.classList.add("hidden");
      if (statusEl) statusEl.textContent = "";
      if (micBtn) {
        micBtn.style.removeProperty("--mic-glow");
        micBtn.style.removeProperty("--mic-halo-scale");
        micBtn.style.removeProperty("--mic-scale");
        micBtn.classList.remove("is-on");
      }
    }

    if (data.type === "mic_level" && micBtn) {
      const glow = Math.max(0, Math.min(1, Number(data.level) || 0));
      micBtn.style.setProperty("--mic-glow", String(glow));
      micBtn.style.setProperty("--mic-halo-scale", String(1 + glow * 0.25));
      micBtn.style.setProperty("--mic-scale", String(1 + glow * 0.12));
      micBtn.classList.toggle("is-on", glow > 0.08);
      if (wrap) wrap.classList.remove("hidden");
    }
  });
})();
