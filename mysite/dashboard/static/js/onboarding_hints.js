// static/js/onboarding_hints.js
(function () {
  document.addEventListener('DOMContentLoaded', () => {
    // Cambia v4 -> v5 para resetear a todos
    const PREFIX = 'inntesec:coachmark:v4';
    const MAX_RUNS = 3;

    const body = document.body;
    const username = (body.getAttribute('data-username') || 'anon').toLowerCase();
    const KEY_RUNS = `${PREFIX}:${username}:runs`;

    const backdrop  = document.getElementById('coachmarkBackdrop');
    const coach     = document.getElementById('coachmarkGeneric');
    const coachText = coach?.querySelector('p');
    const coachBtn  = coach?.querySelector('[data-coachmark-close]');
    if (!backdrop || !coach || !coachText || !coachBtn) return;

    // Pasos en esta pantalla (sólo los que existan)
    const steps = [
      {
        id: 'alarms',
        el: document.getElementById('alarmsLink'),
        dot: document.getElementById('hintDotAlarms'),
        msg: 'En esta sección encontrarás un panel histórico de tus alarmas.'
      },
      {
        id: 'realtime',
        el: document.getElementById('realtimeLink'),
        dot: document.getElementById('hintDotRealtime'),
        msg: 'En esta sección encontrarás las alarmas durante el día y su detalle.'
      },
      {
        id: 'soar',
        el: document.getElementById('soarSummary'),
        dot: document.getElementById('hintDotSoar'),
        msg: 'En esta sección encontrarás detalles de tus alarmas analizadas por Inntesec Agent.'
      },
      {
        id: 'config',
        el: document.getElementById('settingsSummary'),
        dot: document.getElementById('hintDotConfig'),
        msg: 'En esta sección encontrarás las diferentes configuraciones del servicio.'
      }
    ].filter(s => !!s.el);

    if (!steps.length) return;

    let runs = parseInt(localStorage.getItem(KEY_RUNS) || '0', 10);
    if (isNaN(runs)) runs = 0;

    // Si ya superó el máximo, asegurar dots ocultos y salir (sin flicker)
    if (runs >= MAX_RUNS) {
      steps.forEach(s => s.dot && s.dot.classList.add('hidden'));
      return;
    }

    // ===== helpers de UI =====
    const allNavItems = Array.from(document.querySelectorAll('.nav .nav-item, .nav summary.nav-item'));

    const dimAllNav = () => {
      allNavItems.forEach(it => it.classList.add('coachmark-dim'));
    };
    const undimAllNav = () => {
      allNavItems.forEach(it => it.classList.remove('coachmark-dim'));
    };

    const showDotOnlyFor = (step) => {
      steps.forEach(s => s.dot && s.dot.classList.add('hidden'));      // apaga todos
      if (step.dot) step.dot.classList.remove('hidden');               // enciende sólo el del paso activo
      if (step.dot) step.dot.classList.add('is-on');                   // asegura animación
    };

    const placeCoachNear = (target) => {
      const rect = target.getBoundingClientRect();
      const top  = window.scrollY + rect.top + rect.height + 8;
      const left = window.scrollX + rect.left + 8;
      coach.style.top = `${top}px`;
      coach.style.left = `${left}px`;
    };

    const highlight = (target) => {
      body.classList.add('coachmark-open');   // blurea sólo .content
      dimAllNav();                            // atenúa todas
      target.classList.remove('coachmark-dim');
      target.classList.add('coachmark-highlight'); // resalta item activo
    };

    const unhighlight = (target) => {
      target.classList.remove('coachmark-highlight');
      undimAllNav();
      body.classList.remove('coachmark-open');
    };

    const openCoach = (step) => {
      coachText.textContent = step.msg;
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
      // apaga el dot del paso actual
      if (step.dot) step.dot.classList.add('hidden');
    };

    // ===== flujo secuencial =====
    let idx = 0;

    const proceed = () => {
      const step = steps[idx];
      closeCoach(step);

      idx += 1;
      if (idx >= steps.length) {
        // visita terminada
        try { localStorage.setItem(KEY_RUNS, String(runs + 1)); } catch (_) {}
        // Si alcanzó el límite, oculta todos los dots definitivamente
        if (runs + 1 >= MAX_RUNS) steps.forEach(s => s.dot && s.dot.classList.add('hidden'));

        window.removeEventListener('resize', onReflow);
        window.removeEventListener('scroll', onReflow, passiveOpt);
        document.removeEventListener('keydown', onKey);
        document.removeEventListener('click', onDocClick, true);
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
      const step = steps[idx];
      if (step) placeCoachNear(step.el);
    };
    const onKey = (e) => { if (e.key === 'Escape') proceed(); };
    const onDocClick = (e) => {
      const step = steps[idx];
      if (!step) return;
      if (!coach.contains(e.target) && !step.el.contains(e.target)) proceed();
    };
    const passiveOpt = { passive: true };

    coachBtn.addEventListener('click', proceed);
    backdrop.addEventListener('click', proceed);

    showCurrent();
    window.addEventListener('resize', onReflow);
    window.addEventListener('scroll', onReflow, passiveOpt);
    document.addEventListener('keydown', onKey);
    document.addEventListener('click', onDocClick, true);
  });
})();
