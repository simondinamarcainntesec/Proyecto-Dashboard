// static/js/date_filters.js
(function () {
  const Q = (s, r = document) => r.querySelector(s);

  function showOverlayIfExists() {
    const overlay = Q("#loading-overlay");
    if (!overlay) return;
    overlay.classList.add("is-active");
  }

  function navigateToPeriod(v) {
    const url = new URL(window.location.href);
    url.searchParams.set("period", String(v));
    url.searchParams.delete("from");
    url.searchParams.delete("to");
    showOverlayIfExists();
    window.location.href = url.toString();
  }

  // CAPTURE + stopImmediatePropagation para ganarle a cualquier JS global que bloquee submits
  document.addEventListener(
    "click",
    (e) => {
      const btn = e.target?.closest?.('.chip-btn[name="period"]');
      if (!btn) return;

      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();

      navigateToPeriod(btn.value);
    },
    true
  );

  // Backup: si por alguna razón se dispara submit del form
  document.addEventListener(
    "submit",
    (e) => {
      const form = e.target;
      if (!form || form.id !== "date-filter") return;

      const active = form.querySelector('.chip-btn[name="period"].is-active');
      const fallback = form.querySelector('.chip-btn[name="period"]');

      const v = (active?.value || fallback?.value || "3");

      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();

      navigateToPeriod(v);
    },
    true
  );

  console.log("[date_filters] hard override loaded");
})();
