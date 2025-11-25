// static/js/coach_allinone.js
// Versión todo-en-uno: define initSidebarOnboarding + bootstrapping robusto + fallback
(function () {
  'use strict';
  var LOG = function () { try { console.debug.apply(console, arguments); } catch(e){} };
  var WARN = function () { try { console.warn.apply(console, arguments); } catch(e){} };
  var ERR = function () { try { console.error.apply(console, arguments); } catch(e){} };

  LOG('[coach-all] cargado');

  /**
   * initSidebarOnboarding: versión robusta (soporta details/summary, storage bloqueado ...)
   * Parámetros: { prefix, maxRuns }
   */
  function initSidebarOnboarding(opts) {
    opts = opts || {};
    try {
      LOG('[coach-all] initSidebarOnboarding llamado', opts);
      var PREFIX = opts.prefix || 'inntesec:coachmark:v40';
      var MAX_RUNS = typeof opts.maxRuns === 'number' ? opts.maxRuns : 1;

      var body = document.body;
      var username = (body && body.getAttribute('data-username')) || 'anon';
      username = String(username).toLowerCase();
      var KEY_RUNS = PREFIX + ':' + username + ':runs';

      // Safe read of runs (handle storage blocked)
      var runs = 0;
      try { runs = parseInt(localStorage.getItem(KEY_RUNS) || '0', 10); if (isNaN(runs)) runs = 0; }
      catch (e) { WARN('[coach-all] localStorage inaccesible, asumiendo runs=0'); runs = 0; }

      LOG('[coach-all] runs=', runs);
      if (runs >= MAX_RUNS) { LOG('[coach-all] ya completado, no se mostrará'); return; }

      // DOM elements required
      var sidebar = document.querySelector('.sidebar');
      var backdrop = document.getElementById('coachmarkBackdrop');
      var coach = document.getElementById('coachmarkGeneric');
      var coachTxt = coach ? (coach.querySelector('.coachmark-text') || coach.querySelector('p')) : null;
      var btnOK = coach ? (coach.querySelector('[data-coachmark-close], .btn-ok')) : null;

      LOG('[coach-all] elementos base:', {
        sidebar: !!sidebar, backdrop: !!backdrop, coach: !!coach, coachTxt: !!coachTxt, btnOK: !!btnOK
      });

      if (!sidebar || !backdrop || !coach || !coachTxt || !btnOK) {
        WARN('[coach-all] faltan elementos base — abortando (asegúrate de tener #coachmarkGeneric y #coachmarkBackdrop en DOM)');
        return;
      }

      // Steps (usa los IDs que tienes en la plantilla)
      var stepsRaw = [
        { id:'home', el: document.getElementById('homeNav'), dot: document.getElementById('coachDotHome'), msg: 'Desde Home puedes ver un resumen general de tu portal.' },
        { id:'alarms', el: document.getElementById('alarmsSummary'), dot: document.getElementById('coachDotAlarms'), msg: 'En Alarmas existen dos vistas: Dashboard histórico y Tiempo Real.' },
        { id:'soar', el: document.getElementById('soarSummary'), dot: document.getElementById('coachDotSoar'), msg: 'SOAR muestra análisis y correlación de eventos.' },
        { id:'config', el: document.getElementById('settingsSummary'), dot: document.getElementById('coachDotConfig'), msg: 'Desde Configuración puedes cambiar credenciales y notificaciones.' }
      ];

      var steps = stepsRaw.filter(function(s){ return s && s.el; });
      if (!steps.length) { WARN('[coach-all] ningún paso disponible en DOM'); return; }
      LOG('[coach-all] pasos activos:', steps.map(function(s){ return s.id; }));

      // nav items to dim (include summary and subitems)
      var navItems = Array.prototype.slice.call(document.querySelectorAll('.nav .nav-item, .nav summary, .nav .nav-subitem'));
      var dimAll = function(){ navItems.forEach(function(n){ n && n.classList && n.classList.add('coachmark-dim'); }); };
      var undimAll = function(){ navItems.forEach(function(n){ n && n.classList && n.classList.remove('coachmark-dim'); }); };

      var showDotOnlyFor = function(step){
        stepsRaw.forEach(function(s){ if (s && s.dot) { try { s.dot.classList.add('hidden'); s.dot.classList.remove('is-on'); } catch(e){} }});
        if (step && step.dot) {
          try { step.dot.classList.remove('hidden'); void step.dot.offsetWidth; step.dot.classList.add('is-on'); LOG('[coach-all] dot shown for', step.id); } catch(e){}
        }
      };

      // details helpers: open temporarily to measure, restore later
      var ensureDetailsOpen = function(summaryEl){
        if (!summaryEl || !summaryEl.closest) return null;
        var details = summaryEl.closest('details');
        if (!details) return null;
        var wasOpen = !!details.open;
        if (!wasOpen) {
          try { details.open = true; LOG('[coach-all] opened details for', summaryEl.id || summaryEl); }
          catch(e){ WARN('[coach-all] no se pudo abrir details:', e); }
        }
        return { details: details, wasOpen: wasOpen };
      };
      var restoreDetailsState = function(saved){
        if (!saved) return;
        try { if (!saved.wasOpen && saved.details) { saved.details.open = false; LOG('[coach-all] restored details closed'); } } catch(e){ WARN('[coach-all] restore failed', e); }
      };

      // compute and set coach position relative to target
      var placeCoachNear = function(target){
        if (!target) return;
        var detailsState = null;
        if (target.tagName && target.tagName.toLowerCase() === 'summary') detailsState = ensureDetailsOpen(target);
        var r;
        try { r = target.getBoundingClientRect(); } catch(e){ r = { top: 12, bottom: 12, left: 12, right: 200 }; }
        var sRect = sidebar.getBoundingClientRect();
        var preferRight = (window.innerWidth - (sRect.right + 12)) > 360;
        if (preferRight) {
          coach.style.left = (sRect.right + 12 + window.scrollX) + 'px';
          coach.style.top  = (window.scrollY + r.top) + 'px';
        } else {
          coach.style.left = Math.max(12, window.scrollX + r.left - 8) + 'px';
          coach.style.top  = (window.scrollY + r.bottom + 8) + 'px';
        }
        coach.style.zIndex = 9950;
        try { target._coach_details_state = detailsState; } catch(e){}
      };

      var positionBackdrop = function(){
        var s = sidebar.getBoundingClientRect();
        backdrop.style.position = 'fixed';
        backdrop.style.top = '0';
        backdrop.style.bottom = '0';
        backdrop.style.right = '0';
        backdrop.style.left = (s.right + window.scrollX) + 'px';
        backdrop.style.zIndex = 9800;
      };

      var highlight = function(target){
        body.classList.add('coachmark-open');
        dimAll();
        if (target) {
          // undim upward chain
          var node = target;
          while (node && node !== document.body) { try { node.classList && node.classList.remove('coachmark-dim'); } catch(e){} node = node.parentElement; }
          try { target.classList.remove('coachmark-dim'); target.classList.add('coachmark-highlight'); target.style.zIndex = 9850; } catch(e){}
        }
      };

      var unhighlight = function(target){
        if (!target) return;
        try { target.classList.remove('coachmark-highlight'); target.style.zIndex = ''; } catch(e){}
        undimAll();
        body.classList.remove('coachmark-open');
        try {
          if (target._coach_details_state) { restoreDetailsState(target._coach_details_state); delete target._coach_details_state; }
          else {
            var summary = target.closest && target.closest('summary');
            if (summary && summary._coach_details_state) { restoreDetailsState(summary._coach_details_state); delete summary._coach_details_state; }
          }
        } catch(e){ WARN('[coach-all] restoring details failed', e); }
      };

      var openCoach = function(step){
        if (!step || !step.el) return;
        coachTxt.textContent = step.msg;
        positionBackdrop();
        placeCoachNear(step.el);
        showDotOnlyFor(step);
        highlight(step.el);
        coach.classList.remove('hidden');
        backdrop.classList.remove('hidden');
      };

      var closeCoach = function(step){
        if (!step) return;
        coach.classList.add('hidden');
        backdrop.classList.add('hidden');
        unhighlight(step.el);
        if (step.dot) { try { step.dot.classList.remove('is-on'); step.dot.classList.add('hidden'); } catch(e){} }
      };

      var idx = 0;
      var nextStep = function(){
        var current = steps[idx];
        closeCoach(current);
        idx += 1;
        if (idx >= steps.length) {
          LOG('[coach-all] completado, guardando runs');
          try { localStorage.setItem(KEY_RUNS, String(runs+1)); } catch(e){ WARN('[coach-all] no se pudo guardar runs', e); }
          steps.forEach(function(s){ if (s.dot) { try { s.dot.classList.add('hidden'); s.dot.classList.remove('is-on'); } catch(e){} }});
          body.classList.remove('coachmark-open');
          detach();
          return;
        }
        openCoach(steps[idx]);
      };

      var showCurrent = function(){ if (idx < 0 || idx >= steps.length) return; openCoach(steps[idx]); };

      var onDocClick = function(e){ var step = steps[idx]; if (!step) return; if (!coach.contains(e.target) && !step.el.contains(e.target)) nextStep(); };
      var onReflow = function(){ positionBackdrop(); var step = steps[idx]; if (step) placeCoachNear(step.el); };

      var detach = function(){
        try { window.removeEventListener('resize', onReflow); window.removeEventListener('scroll', onReflow, { passive: true }); document.removeEventListener('keydown', onKey); document.removeEventListener('click', onDocClick, true); btnOK.removeEventListener('click', nextStep); backdrop.removeEventListener('click', nextStep); } catch(e){}
      };

      var onKey = function(e){ if (e.key === 'Escape') nextStep(); };

      try { btnOK.addEventListener('click', nextStep); backdrop.addEventListener('click', nextStep); } catch(e){}
      window.addEventListener('resize', onReflow);
      window.addEventListener('scroll', onReflow, { passive: true });
      document.addEventListener('keydown', onKey);
      document.addEventListener('click', onDocClick, true);

      idx = 0;
      LOG('[coach-all] iniciando tour en paso:', steps[0].id);
      showCurrent();

      return { stop: detach };
    } catch (err) {
      ERR('[coach-all] error initSidebarOnboarding:', err);
    }
  }

  // expose to window
  try { window.initSidebarOnboarding = initSidebarOnboarding; LOG('[coach-all] initSidebarOnboarding expuesto'); } catch(e){}

  // bootstrap: attach button handler y autostart si se desea
  function bootstrapAll() {
    try {
      // Button handler (always instalado)
      var btn = document.getElementById('showCoachBtn');
      if (btn) {
        try { btn.removeEventListener('click', btn._coach_handler); } catch(e){}
        var handler = function(){
          try {
            var uname = (document.body && document.body.getAttribute('data-username')) || 'anon';
            uname = String(uname).toLowerCase();
            var key = 'inntesec:coachmark:v40:' + uname + ':runs';
            try { localStorage.removeItem(key); } catch(e){ WARN('[coach-all] no se pudo borrar key', e); }
            if (typeof window.initSidebarOnboarding === 'function') {
              window.initSidebarOnboarding({ maxRuns: 1 });
            } else {
              // fallback simple: show coach minimal
              WARN('[coach-all] initSidebarOnboarding no definido al click — ejecutando fallback mínimo');
              fallbackMinimal();
            }
          } catch (err) { ERR('[coach-all] error en showCoachBtn handler', err); }
        };
        btn._coach_handler = handler;
        btn.addEventListener('click', handler);
        LOG('[coach-all] handler showCoachBtn instalado');
      } else {
        WARN('[coach-all] botón showCoachBtn no encontrado (seguir con autostart si está habilitado)');
      }

      // autostart if global flag set
      try {
        if (window.__SIDEBAR_ONBOARDING_AUTO) {
          LOG('[coach-all] autostart flag detectada -> intentando start');
          if (typeof window.initSidebarOnboarding === 'function') window.initSidebarOnboarding({ maxRuns: 1 });
          else LOG('[coach-all] init no está disponible, esperando DOMContentLoaded y reintentando');
        }
      } catch(e){}

      // If init already defined, call it now (safe)
      if (typeof window.initSidebarOnboarding === 'function') {
        try { window.initSidebarOnboarding({ maxRuns: 1 }); } catch(e){ ERR('[coach-all] init fallo al arrancar', e); }
      } else {
        // Poll for it for short time (in case script ordering different)
        var start = Date.now();
        var pollId = setInterval(function(){
          if (typeof window.initSidebarOnboarding === 'function') {
            clearInterval(pollId);
            try { window.initSidebarOnboarding({ maxRuns: 1 }); } catch(e){ ERR('[coach-all] init fallo al arrancar tras poll', e); }
            return;
          }
          if (Date.now() - start > 3000) {
            clearInterval(pollId);
            LOG('[coach-all] init no apareció; manteniendo handler del botón como fallback');
            // leave fallback UI to button only
          }
        }, 150);
      }
    } catch (err) {
      ERR('[coach-all] bootstrap error:', err);
    }
  }

  // Fallback minimal UI (one-step) used only if init not available
  function fallbackMinimal() {
    try {
      var sidebar = document.querySelector('.sidebar');
      var backdrop = document.getElementById('coachmarkBackdrop');
      var coach = document.getElementById('coachmarkGeneric');
      var coachTxt = coach ? (coach.querySelector('.coachmark-text') || coach.querySelector('p')) : null;
      var ok = coach ? (coach.querySelector('[data-coachmark-close], .btn-ok')) : null;
      var target = document.getElementById('homeNav') || sidebar;
      if (!coach || !backdrop || !coachTxt) { WARN('[coach-all] fallback: elementos no encontrados'); return; }
      coachTxt.textContent = 'Bienvenido — desde Home verás un resumen general del portal.';
      try {
        var r = target.getBoundingClientRect();
        var s = sidebar.getBoundingClientRect();
        var preferRight = (window.innerWidth - (s.right + 12)) > 360;
        if (preferRight) { coach.style.left = (s.right + 12 + window.scrollX) + 'px'; coach.style.top = (window.scrollY + r.top) + 'px'; }
        else { coach.style.left = Math.max(12, window.scrollX + r.left - 8) + 'px'; coach.style.top = (window.scrollY + r.bottom + 8) + 'px'; }
        coach.style.zIndex = 9950;
        backdrop.style.left = (s.right + window.scrollX) + 'px';
        backdrop.style.position = 'fixed'; backdrop.style.top = '0'; backdrop.style.bottom = '0'; backdrop.style.right = '0'; backdrop.style.zIndex = 9800;
      } catch(e){}
      coach.classList.remove('hidden'); backdrop.classList.remove('hidden');
      try { target.classList.add('coachmark-highlight'); target.style.zIndex = 9850; } catch(e){}
      function close(){ try { coach.classList.add('hidden'); backdrop.classList.add('hidden'); target && target.classList.remove('coachmark-highlight'); target && (target.style.zIndex = ''); } catch(e){} }
      ok && ok.addEventListener && ok.addEventListener('click', close, { once: true });
      backdrop.addEventListener && backdrop.addEventListener('click', close, { once: true });
      document.addEventListener('keydown', function onKey(e){ if (e.key === 'Escape') { close(); document.removeEventListener('keydown', onKey); }});
    } catch(e){ ERR('[coach-all] fallback minimal error', e); }
  }

  // start once DOM ready
  if (document.readyState === 'complete' || document.readyState === 'interactive') { setTimeout(bootstrapAll, 0); }
  else { document.addEventListener('DOMContentLoaded', bootstrapAll); }

})();
