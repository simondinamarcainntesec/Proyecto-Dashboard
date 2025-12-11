// site24x7_dashboard.js
// Control de tema claro/oscuro para el iframe de Inn-Monitor

document.addEventListener("DOMContentLoaded", function () {
  const container = document.querySelector(".iframe-container");
  const btn = document.getElementById("btn-theme-toggle");

  if (!container || !btn) return;

  const STORAGE_KEY = "innmonitor_iframe_theme";

  function applyTheme(mode) {
    const isDark = mode === "dark";
    container.classList.toggle("dark", isDark);
    btn.textContent = isDark ? "Modo claro" : "Modo oscuro";
  }

  // Leer tema desde localStorage (si no hay, por defecto "dark")
  let current = localStorage.getItem(STORAGE_KEY);
  if (!current) {
    current = "dark";
  }
  applyTheme(current);

  // Toggle al hacer click
  btn.addEventListener("click", function () {
    current = current === "dark" ? "light" : "dark";
    localStorage.setItem(STORAGE_KEY, current);
    applyTheme(current);
  });
});
