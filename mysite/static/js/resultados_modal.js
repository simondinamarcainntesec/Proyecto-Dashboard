function toggleIpModal(show) {
  const modal = document.getElementById("ipSearchModal");
  if (!modal) return;

  if (show) {
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
  } else {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");

    // Al cerrar manualmente, limpiamos la query
    if (
      window.location.search &&
      (window.location.search.includes("blacklist_q") ||
       window.location.search.includes("whitelist_q"))
    ) {
      console.log("[IP-MODAL] Limpiando query string al cerrar modal:", window.location.search);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }
}