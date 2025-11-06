// ============================================
//   TEMA CLARO / OSCURO (PERSISTENTE GLOBAL)
// ============================================

// Cargar tema guardado o usar 'light' por defecto
const savedTheme = localStorage.getItem('theme') || 'light';
document.documentElement.setAttribute('data-theme', savedTheme);

// Actualiza el icono del botón si existe
function updateThemeIcon() {
  const btn = document.getElementById('theme-switcher');
  if (!btn) return;
  const currentTheme = document.documentElement.getAttribute('data-theme');
  btn.textContent = currentTheme === 'dark' ? '☀️' : '🌙';
}

// Al cargar el DOM
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('theme-switcher');

  // Establece el icono actual
  updateThemeIcon();

  // Si no hay botón, no hace nada (home o dashboard)
  if (!btn) return;

  // Cambia el tema al hacer clic
  btn.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon();
  });
});
