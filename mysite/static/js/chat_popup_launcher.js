// static/js/chat_popup_launcher.js
(function () {
  const POPUP_NAME = "portalChatPopup";
  const POPUP_URL = "/integrations/chat/"; // ajusta si usas prefix o namespace distinto

  window.openChatPopup = function openChatPopup() {
    const features = [
      "popup=yes",
      "width=420",
      "height=720",
      "top=80",
      "left=80",
      "resizable=yes",
      "scrollbars=yes"
    ].join(",");

    const w = window.open(POPUP_URL, POPUP_NAME, features);

    // Si el navegador bloquea popups, window.open devuelve null
    if (!w) {
      // Fallback: abrir en pestaña
      window.location.href = POPUP_URL;
      return;
    }

    try {
      w.focus();
      if ("BroadcastChannel" in window) {
        const bc = new BroadcastChannel("portal_chat_channel_v1");
        bc.postMessage({ type: "focus" });
        bc.close();
      }
    } catch (_) {}
  };
})();
