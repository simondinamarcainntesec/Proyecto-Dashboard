// static/js/tenant_dropdown_width.js
(() => {
  const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
  const px = (v) => {
    const n = parseFloat(v);
    return Number.isFinite(n) ? n : 0;
  };

  function measureAndApply(detailsEl) {
    const list = detailsEl.querySelector(".tenant-list");
    if (!list) return;

    const items = Array.from(detailsEl.querySelectorAll(".tenant-option"));
    if (!items.length) return;

    const csList = getComputedStyle(list);
    const padL = px(csList.paddingLeft);
    const padR = px(csList.paddingRight);
    const borderL = px(csList.borderLeftWidth);
    const borderR = px(csList.borderRightWidth);

    // Detecta si es dropdown overlay (topbar) o submenu en flujo (sidebar)
    const isOverlay = (csList.position === "absolute" || csList.position === "fixed");

    // ===== 1) Medición fiel a estilos reales =====
    // Usamos un "measurer" con EXACTAMENTE las mismas clases del list real,
    // para que tipografía/padding/line-height etc coincidan.
    const meas = document.createElement("div");
    meas.className = list.className; // incluye nav-submenu si existe
    Object.assign(meas.style, {
      position: "absolute",
      left: "-99999px",
      top: "0",
      visibility: "hidden",
      pointerEvents: "none",
      maxWidth: "none",
      width: "max-content",
      whiteSpace: "nowrap",
      overflow: "visible",
    });
    document.body.appendChild(meas);

    let maxItemWidth = 0;

    for (const el of items) {
      // Clonar usando el MISMO tag (<a> o <button>) para medir igual
      const clone = document.createElement(el.tagName.toLowerCase());
      clone.className = el.className;
      clone.textContent = (el.textContent || "").trim();

      // Para anchors, evita navegaciones accidentales
      if (clone.tagName.toLowerCase() === "a") clone.setAttribute("href", "javascript:void(0)");

      // Fuerza 1 línea para medir el ancho real del texto
      clone.style.whiteSpace = "nowrap";
      meas.appendChild(clone);

      const w = clone.getBoundingClientRect().width;
      if (w > maxItemWidth) maxItemWidth = w;
    }

    document.body.removeChild(meas);

    // ===== 2) Ancho del contenedor =====
    if (isOverlay) {
      // En topbar: el menú debe quedar fijo al item más largo
      const desiredListWidth = Math.ceil(maxItemWidth + padL + padR + borderL + borderR);

      // Seguridad viewport
      const maxAllowed = window.innerWidth - 24;
      const finalListWidth = clamp(desiredListWidth, 0, maxAllowed);

      list.style.width = finalListWidth + "px";
    } else {
      // En sidebar: NO forzamos width por contenido (se rige por el sidebar)
      // Solo garantizamos recorte y consistencia visual.
      list.style.width = "";
    }

    // ===== 3) Hover/Active EXACTAMENTE del ancho interno =====
    // Para overlay: usamos el width calculado
    // Para sidebar: usamos el ancho actual renderizado del list
    const listRect = list.getBoundingClientRect();
    const listWidthRendered = Math.ceil(listRect.width);

    const innerWidth = Math.max(
      0,
      listWidthRendered - padL - padR - borderL - borderR
    );

    // Recorte del contenedor para que nada "pinte" afuera
    list.style.overflow = "hidden";

    // Aplicar ancho interno fijo a cada item
    for (const el of items) {
      el.style.boxSizing = "border-box";
      el.style.display = "block";
      el.style.border = "0";
      el.style.outline = "none";
      el.style.width = innerWidth + "px";

      // Seleccionado: borde interno (no crece)
      if (el.classList.contains("is-active")) {
        el.style.boxShadow = "inset 0 0 0 1px #3b82f6";
      } else {
        // No toques otros box-shadows si tu CSS los necesita;
        // pero sí evitamos que un shadow heredado rompa el ancho.
        // Si quieres ser más estricto: descomenta:
        // el.style.boxShadow = "none";
      }
    }
  }

  function wire(detailsEl) {
    const run = () => requestAnimationFrame(() => measureAndApply(detailsEl));

    run();

    detailsEl.addEventListener("toggle", () => {
      // Recalcular al abrir (y también al cerrar no hace daño)
      run();
    });

    window.addEventListener("resize", run, { passive: true });

    // Fuentes listas -> cambia métricas
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(run).catch(() => {});
    }

    // Si se inyectan items o cambia el DOM
    const mo = new MutationObserver(run);
    mo.observe(detailsEl, { childList: true, subtree: true });
  }

  function boot() {
    document.querySelectorAll("details.tenant-dropdown").forEach(wire);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
