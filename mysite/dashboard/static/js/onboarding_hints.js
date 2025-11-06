// static/js/onboarding_hints.js
(function () {
  document.addEventListener('DOMContentLoaded', () => {
    // bump la versión para resetear a todos si lo necesitas (v4 -> v5)
    const PREFIX = 'inntesec:coachmark:v13';
    const MAX_RUNS = 3;

    const body = document.body;
    const username = (body.getAttribute('data-username') || 'anon').toLowerCase();
    const KEY_RUNS = `${PREFIX}:${username}:runs`;

    const sidebar  = document.querySelector('.sidebar');
    const backdrop = document.getElementById('coachmarkBackdrop');
    const coach    = document.getElementById('coachmarkGeneric');
    const coachTxt = coach?.querySelector('p');
    const btnOK    = coach?.querySelector('[data-coachmark-close]');
    if (!sidebar || !backdrop || !coach || !coachTxt || !btnOK) return;

    // Pasos disponibles en esta vista (sólo los que existan)
    const steps = [
      { id: 'alarms',   el: document.getElementById('alarmsLink'),    dot: document.getElementById('hintDotAlarms'),
        msg: 'En esta sección encontrarás un panel histórico de tus alarmas.' },
      { id: 'realtime', el: document.getElementById('realtimeLink'),  dot: document.getElementById('hintDotRealtime'),
        msg: 'En esta sección encontrarás las alarmas durante el día y su detalle.' },
      { id: 'soar',     el: document.getElementById('soarSummary'),   dot: document.getElementById('hintDotSoar'),
        msg: 'En esta sección encontrarás detalles de tus alarmas analizadas por Inntesec Agent.' },
      { id: 'config',   el: document.getElementById('settingsSummary'), dot: document.getElementById('hintDotConfig'),
        msg: 'En esta sección encontrarás las diferentes configuraciones del servicio.' },
    ].filter(s => !!s.el);

    if (!steps.length) return;

    let runs = parseInt(localStorage.getItem(KEY_RUNS) || '0', 10);
    if (isNaN(runs)) runs = 0;

    // Si ya se cumplió el máximo: ocultar dots sin flicker y salir
    if (runs >= MAX_RUNS) {
      steps.forEach(s => s.dot && s.dot.classList.add('hidden'));
      return;
    }

    // ========== utilidades de UI ==========
    const navItems = Array.from(document.querySelectorAll('.nav .nav-item, .nav summary.nav-item'));

    const dimAllNav = () => navItems.forEach(n => n.classList.add('coachmark-dim'));
    const undimAllNav = () => navItems.forEach(n => n.classList.remove('coachmark-dim'));

    const showDotOnlyFor = (step) => {
      steps.forEach(s => s.dot && s.dot.classList.add('hidden'));
      if (step.dot) {
        step.dot.classList.remove('hidden');
        step.dot.classList.add('is-on'); // activa animación
      }
    };

    const placeCoachNear = (target) => {
      const r = target.getBoundingClientRect();
      coach.style.top  = `${window.scrollY + r.top + r.height + 8}px`;
      coach.style.left = `${window.scrollX + r.left + 8}px`;
    };

    // Backdrop solo sobre el área de contenido (no tapa la sidebar)
    const positionBackdrop = () => {
      const s = sidebar.getBoundingClientRect();
      backdrop.style.left = `${s.right + window.scrollX}px`; // deja libre la barra lateral
      backdrop.style.top = `0px`;
      backdrop.style.right = `0px`;
      backdrop.style.bottom = `0px`;
      backdrop.style.position = `fixed`;
    };

    const highlight = (target) => {
      body.classList.add('coachmark-open'); // blurea .content
      dimAllNav();
      target.classList.remove('coachmark-dim');
      target.classList.add('coachmark-highlight');
    };

    const unhighlight = (target) => {
      target.classList.remove('coachmark-highlight');
      undimAllNav();
      body.classList.remove('coachmark-open');
    };

    const openCoach = (step) => {
      coachTxt.textContent = step.msg;
      positionBackdrop();
      placeCoachNear(step.el);
      showDotOnlyFor(step);
      highlight(step.el);
      coach.classList.remove('hidden');
      backdrop.classList.remove('hidden');
    };

    const closeCoach = (step) => {
      coach.classList.add('hidden');
      backdrop.classList.add('hidden');
      unhighlight(step.el);
      if (step.dot) step.dot.classList.add('hidden');
    };

    // ========== flujo secuencial ==========
    let idx = 0;

    const proceed = () => {
      const step = steps[idx];
      closeCoach(step);

      idx += 1;
      if (idx >= steps.length) {
        try { localStorage.setItem(KEY_RUNS, String(runs + 1)); } catch {}
        if (runs + 1 >= MAX_RUNS) steps.forEach(s => s.dot && s.dot.classList.add('hidden'));
        detach();
        return;
      }
      showCurrent();
    };

    const showCurrent = () => {
      const step = steps[idx];
      if (!step) return;
      openCoach(step);
    };

    const onReflow = () => {
      positionBackdrop();
      const step = steps[idx];
      if (step) placeCoachNear(step.el);
    };
    const onKey = (e) => { if (e.key === 'Escape') proceed(); };
    const onDocClick = (e) => {
      const step = steps[idx];
      if (!step) return;
      if (!coach.contains(e.target) && !step.el.contains(e.target)) proceed();
    };
    const detach = () => {
      window.removeEventListener('resize', onReflow);
      window.removeEventListener('scroll', onReflow, { passive: true });
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('click', onDocClick, true);
    };

    btnOK.addEventListener('click', proceed);
    backdrop.addEventListener('click', proceed);

    showCurrent();
    window.addEventListener('resize', onReflow);
    window.addEventListener('scroll', onReflow, { passive: true });
    document.addEventListener('keydown', onKey);
    document.addEventListener('click', onDocClick, true);
  });
})();
