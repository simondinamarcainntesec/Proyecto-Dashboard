// static/js/coach_allinone.js
(function () {
  console.log("[Coach] script cargado");

  const STORAGE_KEY = "inntesec_coach_nav_v2";

  function qs(selector) {
    return document.querySelector(selector);
  }

  function qsa(selector) {
    return Array.from(document.querySelectorAll(selector));
  }

  function findInnMonitorSummary() {
    const summaries = qsa(".nav summary.nav-item");
    const match = summaries.find((el) =>
      el.textContent.trim().includes("Inn-Monitor")
    );
    console.log("[Coach] Inn-Monitor summary encontrado:", !!match);
    return match || null;
  }

  function findSiemLink() {
    const byHref = qs('.nav a.nav-item[href*="/siem/"]');
    console.log("[Coach] SIEM link por href encontrado:", !!byHref);
    return byHref || null;
  }

  const stepsConfig = [
    {
      key: "home",
      title: "Inicio",
      description:
        "Aquí encuentras el resumen general del portal, con los indicadores principales de tu seguridad.",
      getTarget: () => qs("#homeNav"),
      dotId: "coachDotHome",
    },
    {
      key: "alarms",
      title: "Alarmas",
      description:
        "En esta sección puedes revisar el dashboard general de alarmas y el estado en tiempo real.",
      getTarget: () => qs("#alarmsSummary"),
      dotId: "coachDotAlarms",
    },
    {
      key: "soar",
      title: "SOAR",
      description:
        "El módulo SOAR permite gestionar eventos, playbooks y el flujo de tratamiento de incidentes.",
      getTarget: () => qs("#soarSummary"),
      dotId: "coachDotSoar",
    },
    {
      key: "siem",
      title: "SIEM",
      description:
        "Desde SIEM puedes revisar las alertas y realizar correlaciones avanzadas.",
      getTarget: () => findSiemLink(),
      dotId: "coachDotSiem",
    },
    {
      key: "inn-monitor",
      title: "Inn-Monitor",
      description:
        "Inn-Monitor muestra el estado de monitores y el dashboard de disponibilidad y rendimiento.",
      getTarget: () => findInnMonitorSummary(),
      dotId: "coachDotInnMonitor",
    },
    {
      key: "config",
      title: "Configuración",
      description:
        "En Configuración puedes cambiar la contraseña, gestionar credenciales y configurar notificaciones.",
      getTarget: () => qs("#settingsSummary"),
      dotId: "coachDotConfig",
    },
  ];

  let steps = [];
  let currentIndex = 0;

  let backdropEl = null;   // usamos tu #coachmarkBackdrop
  let panelEl = null;
  let titleEl = null;
  let bodyEl = null;
  let progressEl = null;
  let btnPrev = null;
  let btnNext = null;
  let btnSkip = null;

  function setBodyCoachOpen(on) {
    const b = document.body;
    if (!b) return;
    if (on) b.classList.add("coachmark-open");
    else b.classList.remove("coachmark-open");
  }

  function createCoachDom() {
    if (!backdropEl) {
      // Usamos el backdrop que ya tienes en el HTML
      backdropEl = qs("#coachmarkBackdrop");
      if (!backdropEl) {
        // Fallback por si en alguna vista no existe
        backdropEl = document.createElement("div");
        backdropEl.id = "coachmarkBackdrop";
        backdropEl.className = "coachmark-backdrop hidden";
        document.body.appendChild(backdropEl);
      }
    }

    if (panelEl) return; // ya creado

    // =========================
    // PANEL flotante del tour
    // =========================
    panelEl = document.createElement("div");
    panelEl.className = "coach-panel";
    Object.assign(panelEl.style, {
      position: "absolute",
      maxWidth: "340px",
      background: "#0f172a",
      color: "#e5e7eb",
      padding: "16px",
      borderRadius: "14px",
      boxShadow: "0 20px 40px rgba(15,23,42,0.8)",
      fontFamily:
        "Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      fontSize: "14px",
      zIndex: "9900",
    });

    const header = document.createElement("div");
    header.className = "coach-panel-header";
    Object.assign(header.style, {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: "8px",
      gap: "8px",
    });

    titleEl = document.createElement("h3");
    titleEl.className = "coach-title";
    Object.assign(titleEl.style, {
      margin: "0",
      fontSize: "16px",
      fontWeight: "600",
    });
    header.appendChild(titleEl);

    btnSkip = document.createElement("button");
    btnSkip.type = "button";
    btnSkip.className = "coach-skip";
    btnSkip.textContent = "Saltar tour";
    Object.assign(btnSkip.style, {
      border: "none",
      background: "transparent",
      color: "#9ca3af",
      fontSize: "12px",
      cursor: "pointer",
    });
    header.appendChild(btnSkip);

    panelEl.appendChild(header);

    bodyEl = document.createElement("p");
    bodyEl.className = "coach-body";
    Object.assign(bodyEl.style, {
      margin: "0 0 12px 0",
      lineHeight: "1.4",
    });
    panelEl.appendChild(bodyEl);

    const footer = document.createElement("div");
    footer.className = "coach-footer";
    Object.assign(footer.style, {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: "12px",
      marginTop: "4px",
    });

    progressEl = document.createElement("span");
    progressEl.className = "coach-progress";
    Object.assign(progressEl.style, {
      fontSize: "12px",
      color: "#9ca3af",
    });
    footer.appendChild(progressEl);

    const btnGroup = document.createElement("div");
    btnGroup.className = "coach-buttons";
    Object.assign(btnGroup.style, {
      display: "flex",
      gap: "8px",
    });

    btnPrev = document.createElement("button");
    btnPrev.type = "button";
    btnPrev.className = "coach-btn coach-btn-secondary";
    btnPrev.textContent = "Anterior";
    Object.assign(btnPrev.style, {
      padding: "6px 10px",
      borderRadius: "999px",
      border: "1px solid #4b5563",
      background: "transparent",
      color: "#e5e7eb",
      fontSize: "13px",
      cursor: "pointer",
    });
    btnGroup.appendChild(btnPrev);

    btnNext = document.createElement("button");
    btnNext.type = "button";
    btnNext.className = "coach-btn coach-btn-primary";
    btnNext.textContent = "Siguiente";
    Object.assign(btnNext.style, {
      padding: "6px 12px",
      borderRadius: "999px",
      border: "none",
      background: "#3b82f6",
      color: "#f9fafb",
      fontSize: "13px",
      fontWeight: "500",
      cursor: "pointer",
    });
    btnGroup.appendChild(btnNext);

    footer.appendChild(btnGroup);
    panelEl.appendChild(footer);

    document.body.appendChild(panelEl);

    btnSkip.addEventListener("click", endCoach);
    btnPrev.addEventListener("click", () => goToStep(currentIndex - 1));
    btnNext.addEventListener("click", () => {
      if (currentIndex >= steps.length - 1) {
        endCoach();
      } else {
        goToStep(currentIndex + 1);
      }
    });

    window.addEventListener("resize", positionStep);
    window.addEventListener("scroll", positionStep, true);
  }

  function setDotActive(step, active) {
    if (!step.dotId) return;
    const dot = qs("#" + step.dotId);
    if (!dot) return;
    if (active) {
      dot.classList.remove("hidden");
      dot.classList.add("is-on"); // coincide con coachmark.css
    } else {
      dot.classList.remove("is-on");
      dot.classList.add("hidden");
    }
  }

  function clearAllDots() {
    steps.forEach((s) => setDotActive(s, false));
  }

  function clearNavEffects() {
    const nodes = qsa(".nav .nav-item, .nav summary.nav-item");
    nodes.forEach((el) => {
      el.classList.remove("coachmark-dim", "coachmark-highlight");
    });
  }

  function applyNavHighlight(step) {
    const target = step.getTarget();
    const nodes = qsa(".nav .nav-item, .nav summary.nav-item");

    // Atenuar todo
    nodes.forEach((el) => el.classList.add("coachmark-dim"));

    // Resaltar solo el actual
    if (target) {
      target.classList.remove("coachmark-dim");
      target.classList.add("coachmark-highlight");
    }
  }

  function positionStep() {
    if (!panelEl || currentIndex < 0 || currentIndex >= steps.length) return;

    const step = steps[currentIndex];
    const target = step.getTarget();
    if (!target) {
      console.warn("[Coach] Target no encontrado en positionStep para:", step.key);
      return;
    }

    const rect = target.getBoundingClientRect();
    const scrollY = window.scrollY || document.documentElement.scrollTop;
    const scrollX = window.scrollX || document.documentElement.scrollLeft;

    const panelWidth = panelEl.offsetWidth || 320;
    const margin = 16;

    let top = rect.top + scrollY;
    let left = rect.right + scrollX + margin;

    // Si no cabe a la derecha, lo ponemos debajo
    if (left + panelWidth > scrollX + window.innerWidth) {
      left = rect.left + scrollX;
      top = rect.bottom + scrollY + margin;
    }

    panelEl.style.top = top + "px";
    panelEl.style.left = left + "px";
  }

  function goToStep(index) {
    if (index < 0 || index >= steps.length) return;
    currentIndex = index;

    const step = steps[currentIndex];
    console.log("[Coach] Mostrando paso:", step.key);

    clearAllDots();
    clearNavEffects();
    applyNavHighlight(step);
    setDotActive(step, true);

    titleEl.textContent = step.title;
    bodyEl.textContent = step.description;
    progressEl.textContent = `Paso ${currentIndex + 1} de ${steps.length}`;

    btnPrev.disabled = currentIndex === 0;
    btnPrev.style.opacity = currentIndex === 0 ? "0.5" : "1";
    btnPrev.style.cursor = currentIndex === 0 ? "default" : "pointer";

    btnNext.textContent =
      currentIndex === steps.length - 1 ? "Finalizar" : "Siguiente";

    // Mostrar backdrop SOLO sobre la zona de contenido (tu div existente)
    if (backdropEl) {
      backdropEl.classList.remove("hidden");
    }
    setBodyCoachOpen(true);

    positionStep();
  }

  function startCoach(force = false) {
    console.log("[Coach] startCoach(force=", force, ")");

    // Auto (primera vez) respeta localStorage; botón Guía rápida lo ignora.
    if (!force && localStorage.getItem(STORAGE_KEY) === "done") {
      console.log("[Coach] Ya completado, no se muestra de nuevo (modo auto).");
      return;
    }

    steps = stepsConfig
      .map((s) => {
        const exists = !!s.getTarget();
        console.log("[Coach] Paso", s.key, "existe:", exists);
        return { ...s, exists };
      })
      .filter((s) => s.exists);

    console.log("[Coach] Pasos encontrados:", steps.length);

    if (!steps.length) {
      console.warn("[Coach] No hay pasos válidos, no se inicia el tour.");
      return;
    }

    createCoachDom();
    goToStep(0);
  }

  function endCoach() {
    console.log("[Coach] endCoach");
    clearAllDots();
    clearNavEffects();
    setBodyCoachOpen(false);

    if (backdropEl) {
      backdropEl.classList.add("hidden");
    }

    if (panelEl) {
      panelEl.style.top = "-9999px";
      panelEl.style.left = "-9999px";
    }

    localStorage.setItem(STORAGE_KEY, "done");
  }

  // ==== INICIALIZACIÓN ====
  document.addEventListener("DOMContentLoaded", function () {
    console.log("[Coach] DOMContentLoaded");

    const quickBtn = document.getElementById("showCoachBtn");
    if (quickBtn) {
      quickBtn.addEventListener("click", function () {
        console.log("[Coach] Click en Guía rápida");
        window.startInntesecCoach();
      });
    }

    // Auto: solo la primera vez en este navegador
    startCoach(false);
  });

  // Exponer función global para el botón Guía rápida
  window.startInntesecCoach = function () {
    console.log("[Coach] startInntesecCoach manual");
    startCoach(true);
  };
})();
