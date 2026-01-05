// static/js/alarms_one/page-loader-universal.js
(function () {
  let hideTimer = null;
  let inflight = 0;

  // Detección dinámica de página embed (si es así, no mostramos overlay global)
  const isEmbed = function(){
    return !!(document.body && document.body.classList && document.body.classList.contains('is-embed'));
  };

  // Ventana de tiempo para considerar que un request fue gatillado por acción del usuario
  const USER_ACTION_WINDOW_MS = 1500;
  let lastUserActionAt = 0;

  const ensureOverlay = () => {
    if (isEmbed()) return null; // no creamos overlay global en embeds

    let ov = document.getElementById("loading-overlay");
    if (!ov) {
      ov = document.createElement("div");
      ov.id = "loading-overlay";
      ov.setAttribute("role", "status");
      ov.setAttribute("aria-live", "polite");
      ov.innerHTML = `
        <div class="loading-card">
          <div class="spinner" aria-hidden="true"></div>
          <div class="loading-text">Cargando datos…</div>
        </div>`;
      document.body.appendChild(ov);
    }
    return ov;
  };

  const isOverlayActive = () => {
    if (isEmbed()) return false;
    const ov = document.getElementById("loading-overlay");
    return !!(ov && ov.classList.contains("is-active"));
  };

  const markUserAction = () => {
    lastUserActionAt = Date.now();
  };

  const show = (msg = "Cargando datos…") => {
    if (isEmbed()) return; // evita mostrar overlay global en embeds

    const ov = ensureOverlay();
    if (!ov) return;
    const txt = ov.querySelector(".loading-text");
    if (txt) txt.textContent = msg;

    ov.classList.add("is-active");

    // Safety: si algo sale mal, se apaga solo (pero respeta inflight si hay requests)
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      // si hay requests en curso, extendemos un poco
      if (inflight > 0) return;
      const current = document.getElementById("loading-overlay");
      if (current) current.classList.remove("is-active");
    }, 12000);
  };

  const hide = () => {
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
    const ov = document.getElementById("loading-overlay");
    if (!ov) return;
    ov.classList.remove("is-active");
  };

  // ===== Auto-hide basado en requests (Fetch + XHR) solo cuando vienen de una acción reciente =====
  const shouldAttachToRequest = () => {
    return Date.now() - lastUserActionAt <= USER_ACTION_WINDOW_MS;
  };

  const onReqStart = () => {
    inflight += 1;
    // Si el usuario hizo una acción reciente y aún no se ve el loader, lo levantamos
    if (shouldAttachToRequest() && !isOverlayActive()) {
      show("Cargando datos…");
    }
  };

  const onReqEnd = () => {
    inflight = Math.max(0, inflight - 1);
    if (inflight === 0 && isOverlayActive()) {
      hide();
    }
  };

  const patchFetch = () => {
    if (!window.fetch) return;
    const originalFetch = window.fetch.bind(window);

    window.fetch = function patchedFetch() {
      // Solo contabilizamos si viene de acción reciente o si el loader ya está activo
      const track = shouldAttachToRequest() || isOverlayActive();
      if (track) onReqStart();

      const p = originalFetch.apply(this, arguments);
      return Promise.resolve(p)
        .then((res) => {
          if (track) onReqEnd();
          return res;
        })
        .catch((err) => {
          if (track) onReqEnd();
          throw err;
        });
    };
  };

  const patchXHR = () => {
    if (!window.XMLHttpRequest) return;

    const XHR = window.XMLHttpRequest;
    const originalOpen = XHR.prototype.open;
    const originalSend = XHR.prototype.send;

    XHR.prototype.open = function () {
      this.__pl_track = false;
      return originalOpen.apply(this, arguments);
    };

    XHR.prototype.send = function () {
      // Solo contabilizamos si viene de acción reciente o si el loader ya está activo
      this.__pl_track = shouldAttachToRequest() || isOverlayActive();

      if (this.__pl_track) {
        onReqStart();
        const done = () => onReqEnd();
        this.addEventListener("loadend", done, { once: true });
        this.addEventListener("error", done, { once: true });
        this.addEventListener("abort", done, { once: true });
      }

      return originalSend.apply(this, arguments);
    };
  };

  // ===== IP Modal: cuando se haga visible, apagamos el loader =====
  const watchIpModal = () => {
    const ipModal = document.getElementById("ipSearchModal");
    if (!ipModal) return;

    const checkVisible = () => {
      const isHiddenClass = ipModal.classList.contains("hidden");
      const ariaHidden = ipModal.getAttribute("aria-hidden");
      if (!isHiddenClass && ariaHidden !== "true") {
        hide();
      }
    };

    checkVisible();

    const observer = new MutationObserver(checkVisible);
    observer.observe(ipModal, {
      attributes: true,
      attributeFilter: ["class", "aria-hidden"],
    });
  };

  const bindHandlers = () => {
    // Si estamos en embed, eliminamos cualquier overlay global existente para evitar que aparezca por un race
    if (isEmbed()) {
      const existing = document.getElementById('loading-overlay');
      if (existing && existing.parentNode) existing.parentNode.removeChild(existing);
    }

    // Al cargar la página actual, overlay apagado
    hide();

    // Parchar fetch/xhr para auto-hide cuando el request venga de acción reciente
    patchFetch();
    patchXHR();

    // --- BÚSQUEDA DE IP (formularios .home-ip-form) ---
    document.addEventListener("submit", (e) => {
      const form = e.target;
      if (form && form.matches(".home-ip-form")) {
        markUserAction();
        show("Buscando IP…");
      }
    });

    // --- Botón Actualizar ---
    const refreshBtn = document.getElementById("btn-refresh");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => {
        markUserAction();
        show("Actualizando datos…");
      });
    }

    // --- Navegaciones genéricas (links) ---
    // Esto evita depender de beforeunload (que no cubre SPA/HTMX/Turbo)
    document.addEventListener("click", (e) => {
      const a = e.target && e.target.closest ? e.target.closest("a") : null;
      if (!a) return;

      // Ignorar anchors, new-tab, downloads y links sin navegación real
      const href = a.getAttribute("href") || "";
      if (!href || href.startsWith("#")) return;
      if (a.hasAttribute("download")) return;
      if (a.target && a.target.toLowerCase() === "_blank") return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

      markUserAction();
      show("Cargando datos…");
    });

    // Fallbacks para navegación tradicional
    window.addEventListener("beforeunload", () => {
      // Solo mostrar si realmente nos estamos yendo
      show("Cargando datos…");
    });

    window.addEventListener("pageshow", () => hide());
    window.addEventListener("load", () => hide());

    // Vigilar la modal de resultados de IP
    watchIpModal();
  };

  // Exponer helpers por si otro JS quiere usarlos
  window.PageLoader = { show, hide };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindHandlers);
  } else {
    bindHandlers();
  }
})();
