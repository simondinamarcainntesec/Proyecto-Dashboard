// static/js/coach_allinone.js
(function () {
  const STORAGE_KEY = "inntesec_coach_nav_v2";

  const qs = (sel) => document.querySelector(sel);
  const qsa = (sel) => Array.from(document.querySelectorAll(sel));

  function findInnMonitorSummary() {
    const summaries = qsa(".nav summary.nav-item");
    return summaries.find((el) => el.textContent.trim().includes("Inn-Monitor")) || null;
  }

  function findSiemLink() {
    return qs('.nav a.nav-item[href*="/siem/"]') || null;
  }

  // ORDEN FIJO: Home -> Alarmas -> SOAR -> SIEM -> Inn-Monitor -> Configuración
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

  let steps = stepsConfig.slice(); // NO filtramos: el salto lo hacemos en navegación
  let currentIndex = 0;

  let backdropEl = null;
  let panelEl = null;
  let titleEl = null;
  let bodyEl = null;
  let progressEl = null;
  let btnPrev = null;
  let btnNext = null;
  let btnSkip = null;

  function setBodyCoachOpen(on) {
    document.body.classList.toggle("coachmark-open", !!on);
  }

  function setDotActive(step, active) {
    if (!step.dotId) return;
    const dot = qs("#" + step.dotId);
    if (!dot) return;
    if (active) {
      dot.classList.remove("hidden");
      dot.classList.add("is-on");
    } else {
      dot.classList.remove("is-on");
      dot.classList.add("hidden");
    }
  }

  function clearAllDots() {
    steps.forEach((s) => setDotActive(s, false));
  }

  function clearNavEffects() {
    qsa(".nav .nav-item, .nav summary.nav-item").forEach((el) => {
      el.classList.remove("coachmark-dim", "coachmark-highlight");
    });
  }

  function applyNavHighlight(step) {
    const target = step.getTarget();
    const nodes = qsa(".nav .nav-item, .nav summary.nav-item");

    nodes.forEach((el) => el.classList.add("coachmark-dim"));

    if (target) {
      target.classList.remove("coachmark-dim");
      target.classList.add("coachmark-highlight");
    }
  }

  // Encuentra el siguiente índice "válido" en la dirección indicada
  // dir = +1 (siguiente) o -1 (anterior)
  function findNextExistingIndex(fromIndex, dir) {
    let i = fromIndex;
    while (i >= 0 && i < steps.length) {
      const t = steps[i].getTarget();
      if (t) return i;
      i += dir;
    }
    return -1;
  }

  function ensureTargetVisible(target) {
    if (!target) return;
    try {
      target.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
    } catch (e) {}
  }

  function positionStep() {
    if (!panelEl || panelEl.classList.contains("hidden")) return;

    const step = steps[currentIndex];
    const target = step.getTarget();
    if (!target) return;

    const rect = target.getBoundingClientRect();
    const margin = 14;

    const panelW = panelEl.offsetWidth || 340;
    const panelH = panelEl.offsetHeight || 180;

    let left = rect.right + margin;
    let top = rect.top;

    if (left + panelW > window.innerWidth - 12) {
      left = rect.left - panelW - margin;
    }
    if (left < 12) {
      left = Math.min(rect.left, window.innerWidth - panelW - 12);
      top = rect.bottom + margin;
    }

    if (top + panelH > window.innerHeight - 12) {
      top = Math.max(12, window.innerHeight - panelH - 12);
    }
    top = Math.max(12, top);

    panelEl.style.left = left + "px";
    panelEl.style.top = top + "px";
  }

  function createCoachDom() {
    backdropEl = qs("#coachmarkBackdrop");
    if (!backdropEl) {
      backdropEl = document.createElement("div");
      backdropEl.id = "coachmarkBackdrop";
      backdropEl.className = "coachmark-backdrop hidden";
      document.body.appendChild(backdropEl);
    }

    if (panelEl) return;

    panelEl = document.createElement("div");
    panelEl.className = "coach-panel hidden";
    Object.assign(panelEl.style, {
      position: "fixed",
      zIndex: "1011",
      width: "min(360px, calc(100vw - 32px))",
      maxWidth: "360px",
      background: "#0f1d35",
      color: "#e5e7eb",
      border: "1px solid rgba(30,41,59,.70)",
      borderRadius: "14px",
      boxShadow: "0 16px 44px rgba(2,6,23,.55)",
      padding: "14px 16px",
      fontFamily: "Inter, system-ui, Segoe UI, Roboto, Arial, sans-serif",
      fontSize: "14px",
    });

    const header = document.createElement("div");
    Object.assign(header.style, {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: "10px",
      marginBottom: "8px",
    });

    titleEl = document.createElement("h3");
    Object.assign(titleEl.style, { margin: 0, fontSize: "16px", fontWeight: "800" });

    btnSkip = document.createElement("button");
    btnSkip.type = "button";
    btnSkip.textContent = "Saltar tour";
    Object.assign(btnSkip.style, {
      border: 0,
      background: "transparent",
      color: "#94a3b8",
      fontSize: "12px",
      cursor: "pointer",
      padding: "4px 6px",
      borderRadius: "10px",
    });

    header.appendChild(titleEl);
    header.appendChild(btnSkip);
    panelEl.appendChild(header);

    bodyEl = document.createElement("p");
    Object.assign(bodyEl.style, {
      margin: "0 0 12px 0",
      lineHeight: "1.45",
      color: "rgba(203,213,225,.92)",
    });
    panelEl.appendChild(bodyEl);

    const footer = document.createElement("div");
    Object.assign(footer.style, {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: "12px",
    });

    progressEl = document.createElement("span");
    Object.assign(progressEl.style, { fontSize: "12px", color: "#94a3b8" });

    const btnGroup = document.createElement("div");
    Object.assign(btnGroup.style, { display: "flex", gap: "8px" });

    btnPrev = document.createElement("button");
    btnPrev.type = "button";
    btnPrev.textContent = "Anterior";
    Object.assign(btnPrev.style, {
      padding: "6px 10px",
      borderRadius: "999px",
      border: "1px solid rgba(148,163,184,.30)",
      background: "transparent",
      color: "#e5e7eb",
      fontSize: "13px",
      cursor: "pointer",
    });

    btnNext = document.createElement("button");
    btnNext.type = "button";
    btnNext.textContent = "Siguiente";
    Object.assign(btnNext.style, {
      padding: "6px 12px",
      borderRadius: "999px",
      border: 0,
      background: "#3b82f6",
      color: "#fff",
      fontSize: "13px",
      fontWeight: "700",
      cursor: "pointer",
    });

    btnGroup.appendChild(btnPrev);
    btnGroup.appendChild(btnNext);

    footer.appendChild(progressEl);
    footer.appendChild(btnGroup);
    panelEl.appendChild(footer);

    document.body.appendChild(panelEl);

    btnSkip.addEventListener("click", endCoach);
    btnPrev.addEventListener("click", () => goToStep(currentIndex - 1));
    btnNext.addEventListener("click", () => {
      if (currentIndex >= steps.length - 1) endCoach();
      else goToStep(currentIndex + 1);
    });

    backdropEl.addEventListener("click", endCoach);

    window.addEventListener("resize", positionStep, { passive: true });
    window.addEventListener("scroll", positionStep, true);
  }

  function goToStep(index, directionHint = +1) {
    // Si el índice está fuera, cerramos.
    if (index < 0 || index >= steps.length) {
      endCoach();
      return;
    }

    // Si el target no existe, saltar al siguiente válido según dirección
    const desired = index;
    const existsAtDesired = !!steps[desired].getTarget();

    if (!existsAtDesired) {
      const next = findNextExistingIndex(desired, directionHint);
      if (next === -1) {
        // Si no hay más hacia esa dirección, intenta al revés antes de cerrar
        const alt = findNextExistingIndex(desired, -directionHint);
        if (alt === -1) endCoach();
        else goToStep(alt, -directionHint);
        return;
      }
      goToStep(next, directionHint);
      return;
    }

    currentIndex = desired;
    const step = steps[currentIndex];
    const target = step.getTarget();

    clearAllDots();
    clearNavEffects();

    applyNavHighlight(step);
    setDotActive(step, true);

    titleEl.textContent = step.title;
    bodyEl.textContent = step.description;
    progressEl.textContent = `Paso ${currentIndex + 1} de ${steps.length}`;

    // Prev/Next
    const prevExisting = findNextExistingIndex(currentIndex - 1, -1);
    btnPrev.disabled = prevExisting === -1;
    btnPrev.style.opacity = btnPrev.disabled ? "0.55" : "1";
    btnPrev.style.cursor = btnPrev.disabled ? "default" : "pointer";

    const nextExisting = findNextExistingIndex(currentIndex + 1, +1);
    btnNext.textContent = nextExisting === -1 ? "Finalizar" : "Siguiente";

    // Abrir overlay
    backdropEl.classList.remove("hidden");
    panelEl.classList.remove("hidden");
    setBodyCoachOpen(true);

    if (target) ensureTargetVisible(target);

    requestAnimationFrame(() => positionStep());
  }

  function startCoach(force = false) {
    if (!force && localStorage.getItem(STORAGE_KEY) === "done") return;

    createCoachDom();

    // Siempre parte desde Home si existe; si no, usa el primer paso disponible.
    const startIndex = steps[0].getTarget()
      ? 0
      : findNextExistingIndex(0, +1);

    if (startIndex === -1) return;
    goToStep(startIndex, +1);
  }

  function endCoach() {
    clearAllDots();
    clearNavEffects();
    setBodyCoachOpen(false);

    if (backdropEl) backdropEl.classList.add("hidden");
    if (panelEl) panelEl.classList.add("hidden");

    localStorage.setItem(STORAGE_KEY, "done");
  }

  document.addEventListener("DOMContentLoaded", function () {
    const quickBtn = document.getElementById("showCoachBtn");
    if (quickBtn) {
      quickBtn.addEventListener("click", function () {
        window.startInntesecCoach();
      });
    }

    // Auto: solo la primera vez
    startCoach(false);
  });

  window.startInntesecCoach = function () {
    startCoach(true);
  };
})();
