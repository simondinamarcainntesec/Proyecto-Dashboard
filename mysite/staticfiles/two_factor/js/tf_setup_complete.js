// static/two_factor/js/tf_setup_complete.js
(function () {
  const params = new URLSearchParams(window.location.search);
  const nextUrl = params.get("next") || "";
  const fallback = "/admin/";

  if (nextUrl.startsWith("/admin")) {
    setTimeout(() => { window.location.href = nextUrl; }, 900);
  } else {
    setTimeout(() => { window.location.href = fallback; }, 900);
  }
})();
