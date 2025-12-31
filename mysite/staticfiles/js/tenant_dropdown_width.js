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

    const csList = getComputedStyle(list);
    const padL = px(csList.paddingLeft);
    const padR = px(csList.paddingRight);
    const borderL = px(csList.borderLeftWidth);
    const borderR = px(csList.borderRightWidth);

    const isOverlay = csList.position === "absolute" || csList.position === "fixed";

    // Items: overlay usa tenant-option; sidebar usa nav-subitem (pero soportamos ambos)
    const items = Array.from(detailsEl.querySelectorAll(".tenant-option, .nav-subitem"));
    if (!items.length) return;

    // Measurer fiel a estilos del contenedor
    const meas = document.createElement("div");
    meas.className = list.className;
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

    // Medimos cada item (no solo el más largo)
    const measuredWidths = [];
    let maxItemWidth = 0;

    for (const el of items) {
      const clone = document.createElement(el.tagName.toLowerCase());
      clone.className = el.className;

      // Texto igual al real (sin espacios extra)
      clone.textContent = (el.textContent || "").trim();

      // Evitar navegación accidental en <a>
      if (clone.tagName.toLowerCase() === "a") clone.setAttribute("href", "javascript:void(0)");

      // Medición en 1 línea y tamaño por contenido
      Object.assign(clone.style, {
        whiteSpace: "nowrap",
        width: "max-content",
        maxWidth: "none",
        display: "inline-flex",
      });

      meas.appendChild(clone);

      const w = clone.getBoundingClientRect().width;
      measuredWidths.push(w);
      if (w > maxItemWidth) maxItemWidth = w;
    }

    document.body.removeChild(meas);

    // ===== 2) Ancho del contenedor =====
    if (isOverlay) {
      // Topbar: menú al ancho del item más largo
      const desiredListWidth = Math.ceil(maxItemWidth + padL + padR + borderL + borderR);
      const maxAllowed = window.innerWidth - 24;
      const finalListWidth = clamp(desiredListWidth, 0, maxAllowed);
      list.style.width = finalListWidth + "px";
    } else {
      // Sidebar: asegurar que el submenu NO se “agrande” por contenido
      list.style.width = "100%";
      list.style.maxWidth = "100%";
    }

    // ===== 3) Cálculo del ancho interno renderizado del contenedor =====
    const listRect = list.getBoundingClientRect();
    const listWidthRendered = Math.ceil(listRect.width);

    const innerWidth = Math.max(0, listWidthRendered - padL - padR - borderL - borderR);

    // Evitar scroll horizontal por cualquier motivo
    list.style.overflowX = "hidden";
    // no pisar overflowY si tu CSS ya define algo
    if (!list.style.overflowY) list.style.overflowY = "auto";

    // ===== 4) Aplicar widths =====
    items.forEach((el, idx) => {
      el.style.boxSizing = "border-box";
      el.style.outline = "none";

      if (isOverlay) {
        // Overlay: items a ancho interno fijo
        el.style.display = "block";
        el.style.width = innerWidth + "px";
      } else {
        // Sidebar: “pill” al ancho del texto (clamp al contenedor)
        const desired = Math.ceil(measuredWidths[idx] || 0);
        const finalW = clamp(desired, 0, innerWidth);

        el.style.display = "inline-flex";
        el.style.width = finalW + "px";
        el.style.maxWidth = innerWidth + "px";
        el.style.flex = "0 0 auto";
        el.style.alignSelf = "flex-start";

        // Seguridad para texto largo
        el.style.whiteSpace = "nowrap";
        el.style.overflow = "hidden";
        el.style.textOverflow = "ellipsis";
      }

      // Mantener tu “active” sin romper el ancho
      if (el.classList.contains("is-active")) {
        el.style.boxShadow = "inset 0 0 0 1px #3b82f6";
      }
    });
  }

  function wire(detailsEl) {
    const run = () => requestAnimationFrame(() => measureAndApply(detailsEl));

    run();

    detailsEl.addEventListener("toggle", run);
    window.addEventListener("resize", run, { passive: true });

    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(run).catch(() => {});
    }

    const mo = new MutationObserver(run);
    mo.observe(detailsEl, { childList: true, subtree: true });
  }

  function boot() {
    // ✅ SOLO topbar: no tocar acordeones del sidebar
    document.querySelectorAll("details.tenant-dropdown").forEach((detailsEl) => {
      if (detailsEl.closest(".sidebar")) return; // ignora sidebar
      wire(detailsEl);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
