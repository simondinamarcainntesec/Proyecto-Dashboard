// static/js/site24x7_empty_ok.js
// Sólo maneja el botón "OK" de los estados vacíos / error de Site24x7.

(function () {
  function initEmptyOkButton() {
    var btn = document.getElementById('btn-empty-ok');
    if (!btn) return;  // no hay botón en esta vista

    var homeUrl = btn.getAttribute('data-home-url') || '/';

    btn.addEventListener('click', function (event) {
      event.preventDefault();
      window.location.href = homeUrl;
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEmptyOkButton);
  } else {
    initEmptyOkButton();
  }
})();
