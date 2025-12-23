// static/two_factor/js/tf_theme_toggle.js
(function () {
  function getTheme() {
    const t =
      document.documentElement.getAttribute("data-theme") ||
      document.documentElement.dataset.theme ||
      "";
    return (t === "light" || t === "dark") ? t : "dark";
  }

  function setTheme(v) {
    const value = (v === "light" || v === "dark") ? v : "dark";
    document.documentElement.setAttribute("data-theme", value);
    document.documentElement.dataset.theme = value;

    try {
      localStorage.setItem("django.admin.theme", value);
      localStorage.setItem("theme", value);
    } catch (e) {}
  }

  function updateIcon(btn) {
    if (!btn) return;
    const isLight = getTheme() === "light";
    const ico = btn.querySelector(".tf-theme-ico");
    if (ico) ico.textContent = isLight ? "🌙" : "☀️";
    btn.setAttribute("aria-label", isLight ? "Cambiar a modo oscuro" : "Cambiar a modo claro");
    btn.title = isLight ? "Cambiar a modo oscuro" : "Cambiar a modo claro";
  }

  function ensureButton() {
    const header = document.getElementById("header");
    if (!header) return;

    // Si ya creamos el nuestro, listo
    let btn = header.querySelector(".tf-theme-toggle");
    if (!btn) {
      btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tf-theme-toggle";
      btn.innerHTML = '<span class="tf-theme-ico" aria-hidden="true">🌓</span>';

      // Lo ponemos al final del header (como te queda ahora)
      header.appendChild(btn);

      btn.addEventListener("click", function () {
        const next = getTheme() === "dark" ? "light" : "dark";
        setTheme(next);
        updateIcon(btn);
      });
    }

    updateIcon(btn);
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Aplicar tema guardado si existe
    try {
      const saved = localStorage.getItem("django.admin.theme") || localStorage.getItem("theme");
      if (saved) setTheme(saved);
    } catch (e) {}

    ensureButton();
  });
})();
