// static/js/alarms_one/page-loader.js

function ensureOverlay() {
  let ov = document.getElementById("loading-overlay");
  if (!ov) {
    ov = document.createElement("div");
    ov.id = "loading-overlay";
    ov.setAttribute("role", "status");
    ov.setAttribute("aria-live", "polite");
    ov.hidden = true;
    ov.innerHTML = `
      <div class="loading-card">
        <div class="spinner" aria-hidden="true"></div>
        <div class="loading-text">Cargando datos…</div>
      </div>`;
    document.body.appendChild(ov);
  }
  return ov;
}

export function showOverlay(msg = "Cargando datos…") {
  const ov = ensureOverlay();
  const txt = ov.querySelector(".loading-text");
  if (txt) txt.textContent = msg;
  ov.hidden = false;
}

export function hideOverlay() {
  const ov = document.getElementById("loading-overlay");
  if (ov) ov.hidden = true;
}

function bindNavHandlers() {
  const onNavigate = (message = "Cargando datos…") => {
    // Pinta overlay lo antes posible
    requestAnimationFrame(() => showOverlay(message));
  };

  // 1) Click en botón Refresh (realtime)
  const btn = document.getElementById("btn-refresh");
  if (btn) {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      onNavigate("Actualizando datos…");
      // recarga con cache-buster para forzar nueva consulta
      const params = new URLSearchParams(window.location.search);
      params.set("_", Date.now().toString());
      window.location.search = params.toString();
    });
  }

  // 2) Click en enlaces de navegación internos (por ej. volver al histórico)
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a");
    if (!a) return;
    // Solo mismo origen; deja pasar # y enlaces externos sin overlay
    try {
      const url = new URL(a.href, window.location.href);
      const sameOrigin = url.origin === window.location.origin;
      const isHashOnly = url.href === window.location.href || url.hash.length > 0 && url.pathname === window.location.pathname;
      if (sameOrigin && !isHashOnly) {
        onNavigate();
      }
    } catch (_) { /* noop */ }
  });

  // 3) F5 / Ctrl+R / Cmd+R → mostrar overlay
  window.addEventListener("keydown", (e) => {
    const isF5 = e.key === "F5";
    const isReloadCombo = (e.key === "r" || e.key === "R") && (e.ctrlKey || e.metaKey);
    if (isF5 || isReloadCombo) {
      // No prevenimos la recarga; solo mostramos overlay
      onNavigate("Recargando…");
    }
  });

  // 4) beforeunload: último recurso (navegaciones no capturadas)
  window.addEventListener("beforeunload", () => {
    // Nota: en algunos navegadores el render del overlay puede no alcanzarse,
    // pero no hace daño mantenerlo.
    showOverlay();
  });

  // 5) pageshow con BFCache (volver atrás) → ocultar overlay si quedó visible
  window.addEventListener("pageshow", (evt) => {
    if (evt.persisted) hideOverlay();
  });

  // Oculta overlay inicial si vino visible por alguna razón
  hideOverlay();
}

// Inicia al cargar el DOM
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bindNavHandlers);
} else {
  bindNavHandlers();
}
