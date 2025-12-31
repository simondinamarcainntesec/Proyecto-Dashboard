// static/js/csrf_patch.js
(function () {
  function getCookie(name) {
    const v = `; ${document.cookie}`;
    const parts = v.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  function pickCsrf() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    const metaToken = (meta?.content || "").trim();
    const cookieToken = (getCookie("csrftoken") || "").trim();

    if (metaToken && (metaToken.length === 32 || metaToken.length === 64)) return metaToken;
    if (cookieToken && (cookieToken.length === 32 || cookieToken.length === 64)) return cookieToken;
    return "";
  }

  // Evita “doble patch”
  if (window.__CSRF_FETCH_PATCHED__) return;
  window.__CSRF_FETCH_PATCHED__ = true;

  const _fetch = window.fetch;
  window.fetch = function (input, init) {
    try {
      const url = typeof input === "string" ? input : (input?.url || "");
      // Solo este endpoint
      if (url.includes("/inntesec-agent/create-web-call/")) {
        init = init || {};
        init.headers = new Headers(init.headers || {});
        const t = pickCsrf();
        if (t) init.headers.set("X-CSRFToken", t);
      }
    } catch (_) {}
    return _fetch.call(this, input, init);
  };
})();
