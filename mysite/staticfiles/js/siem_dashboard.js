// site24x7_dashboard.js
// Control de tema claro/oscuro para dashboards embebidos (usa data-theme en <body>)

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("theme-switcher");
  const root = document.body; // donde vive data-theme

  if (!btn || !root) return;

  const STORAGE_KEY = "innmonitor_iframe_theme";

  const setTheme = (mode) => {
    const isDark = mode === "dark";
    root.setAttribute("data-theme", isDark ? "dark" : "light");
    btn.textContent = isDark ? "☀️" : "🌙"; // icono simple
    btn.setAttribute("aria-label", isDark ? "Cambiar a modo claro" : "Cambiar a modo oscuro");
  };

  // Default: dark si no existe
  const saved = localStorage.getItem(STORAGE_KEY);
  const initial = saved === "light" ? "light" : "dark";
  setTheme(initial);

  btn.addEventListener("click", () => {
    const current = root.getAttribute("data-theme") === "dark" ? "dark" : "light";
    const next = current === "dark" ? "light" : "dark";
    localStorage.setItem(STORAGE_KEY, next);
    setTheme(next);
  });
});
