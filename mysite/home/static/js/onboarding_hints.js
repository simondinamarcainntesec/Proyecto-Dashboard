// static/js/onboarding_hints.js

(function () {
  console.log('[coach] archivo onboarding_hints.js cargado (IIFE)');

  // Exponemos una función global en window
  window.initSidebarOnboarding = function () {
    console.log('[coach] initSidebarOnboarding llamado');

    try {
      const body = document.body;
      const sidebar  = document.querySelector('.sidebar');
      const content  = document.querySelector('.content');
      const backdrop = document.getElementById('coachmarkBackdrop');
      const coach    = document.getElementById('coachmarkGeneric');
      const coachTxt = coach ? coach.querySelector('.coachmark-text') : null;
      const btnOK    = coach ? coach.querySelector('[data-coachmark-close]') : null;

      if (!body || !sidebar || !content || !backdrop || !coach || !coachTxt || !btnOK) {
        console.log('[coach] faltan elementos base', {
          body: !!body,
          sidebar: !!sidebar,
          content: !!content,
          backdrop: !!backdrop,
          coach: !!coach,
          coachTxt: !!coachTxt,
          btnOK: !!btnOK,
        });
        return;
      }

      const PREFIX = 'inntesec:coach:v10002';   // bump versión
      const MAX_RUNS = 1;

      const username = (body.getAttribute('data-username') || 'anon').toLowerCase();
      const KEY_RUNS = `${PREFIX}:${username}:runs`;

      let runs = parseInt(localStorage.getItem(KEY_RUNS) || '0', 10);
      if (Number.isNaN(runs)) runs = 0;
      console.log('[coach] runs actuales =', runs);

      const steps = [
        {
          id: 'home',
          el: document.getElementById('homeNav'),
          dot: document.getElementById('coachDotHome'),
          msg: 'Desde Home puedes ver un resumen general de tu portal.',
        },
        {
          id: 'alarms',
          el: document.getElementById('alarmsSummary'),
          dot: document.getElementById('coachDotAlarms'),
          msg: 'En la sección Alarmas existen dos vistas: Dashboard histórico y Tiempo Real.',
        },
        {
          id: 'soar',
          el: document.getElementById('soarSummary'),
          dot: document.getElementById('coachDotSoar'),
          msg: 'SOAR muestra el análisis y correlación de eventos mediante Inntesec Agent IA.',
        },
        {
          id: 'config',
          el: document.getElementById('settingsSummary'),
          dot: document.getElementById('coachDotConfig'),
          msg: 'Desde Configuración puedes cambiar tu contraseña, credenciales y notificaciones.',
        },
      ].filter(s => !!s.el);

      if (!steps.length) {
        console.log('[coach] no hay pasos válidos');
        return;
      }

      if (runs >= MAX_RUNS) {
        console.log('[coach] tour ya completado, oculto dots');
        steps.forEach(s => s.dot && s.dot.classList.add('hidden'));
        return;
      }

      const navItems = Array.from(
        document.querySelectorAll('.nav .nav-item, .nav summary.nav-item')
      );

      const dimAllNav = () => navItems.forEach(n => n.classList.add('coachmark-dim'));
      const undimAllNav = () => navItems.forEach(n => n.classList.remove('coachmark-dim'));

      const showDotOnlyFor = (step) => {
        steps.forEach(s => {
          if (s.dot) {
            s.dot.classList.add('hidden');
            s.dot.classList.remove('is-on');
          }
        });
        if (step.dot) {
          step.dot.classList.remove('hidden');
          step.dot.classList.add('is-on');
        }
      };

      const positionBackdrop = () => {
        const s = sidebar.getBoundingClientRect();
        backdrop.style.left   = `${s.right + window.scrollX}px`;
        backdrop.style.top    = '0px';
        backdrop.style.right  = '0px';
        backdrop.style.bottom = '0px';
      };

      const placeCoachNear = (step) => {
        const r = step.el.getBoundingClientRect();
        coach.style.top  = `${window.scrollY + r.bottom + 10}px`;
        coach.style.left = `${window.scrollX + r.left + 12}px`;
      };

      const highlight = (step) => {
        document.body.classList.add('coachmark-open');
        dimAllNav();
        step.el.classList.remove('coachmark-dim');
        step.el.classList.add('coachmark-highlight');
      };

      const unhighlight = (step) => {
        step.el.classList.remove('coachmark-highlight');
        undimAllNav();
        document.body.classList.remove('coachmark-open');
      };

      const openCoach = (step) => {
        console.log('[coach] abrir paso', step.id);
        coachTxt.textContent = step.msg;
        positionBackdrop();
        placeCoachNear(step);
        showDotOnlyFor(step);
        highlight(step);
        coach.classList.remove('hidden');
        backdrop.classList.remove('hidden');
      };

      const closeCoach = (step) => {
        console.log('[coach] cerrar paso', step.id);
        coach.classList.add('hidden');
        backdrop.classList.add('hidden');
        unhighlight(step);
        if (step.dot) {
          step.dot.classList.add('hidden');
          step.dot.classList.remove('is-on');
        }
      };

      let idx = 0;

      const showCurrent = () => {
        const step = steps[idx];
        if (!step) return;
        openCoach(step);
      };

      const proceed = () => {
        const step = steps[idx];
        if (step) closeCoach(step);
        idx += 1;
        if (idx >= steps.length) {
          try { localStorage.setItem(KEY_RUNS, String(runs + 1)); } catch (e) {}
          steps.forEach(s => s.dot && s.dot.classList.add('hidden'));
          detach();
          return;
        }
        showCurrent();
      };

      const onReflow = () => {
        const step = steps[idx];
        if (!step) return;
        positionBackdrop();
        placeCoachNear(step);
      };

      const onKey = (e) => {
        if (e.key === 'Escape') proceed();
      };

      const onDocClick = (e) => {
        const step = steps[idx];
        if (!step) return;
        if (!coach.contains(e.target) && !step.el.contains(e.target)) {
          proceed();
        }
      };

      const detach = () => {
        window.removeEventListener('resize', onReflow);
        window.removeEventListener('scroll', onReflow, { passive: true });
        document.removeEventListener('keydown', onKey);
        document.removeEventListener('click', onDocClick, true);
      };

      btnOK.addEventListener('click', proceed);
      backdrop.addEventListener('click', proceed);

      // Arrancar tour
      showCurrent();
      window.addEventListener('resize', onReflow);
      window.addEventListener('scroll', onReflow, { passive: true });
      document.addEventListener('keydown', onKey);
      document.addEventListener('click', onDocClick, true);

      console.log('[coach] tour inicializado');
    } catch (err) {
      console.error('[coach] error en initSidebarOnboarding', err);
    }
  };
})();
