// static/two_factor/js/tf_login_focus.js
(function () {
  const first = document.querySelector('#login-form input:not([type="hidden"]):not([disabled])');
  if (first) first.focus();
})();
