// Añade un overlay "Cargando datos…" sobre cada .iframe-container
// y muestra el iframe solo cuando dispare el evento 'load'.
(function(){
  function initIframes(){
    // Si la página es un embed, eliminamos cualquier overlay global por seguridad
    try{
      if(document.body && document.body.classList && document.body.classList.contains('is-embed')){
        var globalOv = document.getElementById('loading-overlay');
        if(globalOv && globalOv.parentNode){
          globalOv.parentNode.removeChild(globalOv);
        }
      }
    }catch(e){ /* ignore */ }

    document.querySelectorAll('.iframe-container').forEach(function(container){
      var iframe = container.querySelector('iframe');
      if(!iframe) return;

      // Añadir overlay si no existe
      var overlay = container.querySelector('.iframe-overlay');
      if(!overlay){
        overlay = document.createElement('div');
        overlay.className = 'iframe-overlay';
        overlay.setAttribute('role','status');
        overlay.setAttribute('aria-live','polite');
        overlay.innerHTML = '<div class="overlay-card"><div class="spinner" aria-hidden="true"></div><div class="overlay-text">Cargando datos…</div></div>';
        container.appendChild(overlay);
      }

      var MIN_DISPLAY_MS = 7000; // 6 segundos (estándar)
      var startAt = Date.now();

      function showOverlay(){
        startAt = Date.now();
        overlay.dataset.startAt = startAt;
        overlay.classList.remove('hidden');
        overlay.style.opacity = '';
        overlay.style.visibility = '';
        iframe.classList.add('is-loading');
        iframe.classList.remove('is-loaded');
        iframe.setAttribute('aria-hidden','true');
        iframe.style.visibility = 'hidden';
      }
      // Estado inicial
      showOverlay();

      // Helper para ocultar overlay respetando el tiempo mínimo
      function hideOverlayRespectingMinAndFinalize(visibleIframe){
        var started = parseInt(overlay.dataset.startAt || '0', 10) || startAt;
        var elapsed = Date.now() - started;
        var remaining = Math.max(0, MIN_DISPLAY_MS - elapsed);
        var finalize = function(ifr){
          overlay.classList.add('hidden');
          if(ifr){
            ifr.classList.remove('is-loading');
            ifr.classList.add('is-loaded');
            ifr.removeAttribute('aria-hidden');
            ifr.style.visibility = 'visible';
          }
        };
        if(remaining > 0){
          setTimeout(function(){ finalize(visibleIframe); }, remaining);
        } else {
          finalize(visibleIframe);
        }
      }

      // Intentaremos pre-cargar fuera de pantalla en un iframe oculto
      var dataSrc = iframe.dataset && iframe.dataset.src ? iframe.dataset.src : null;
      var preloaded = false;
      var preloader = null;

      function watchIframeLoadAndFinalize(targetIframe){
        var done = false;
        var STABILIZATION_MS = 5000; // No extra stabilization — respetamos el tiempo mínimo (MIN_DISPLAY_MS) solamente
        var onload = function(){
          if(done) return; done = true;
          // Calculamos cuánto queda del mínimo y esperamos al menos STABILIZATION_MS
          var started = parseInt(overlay.dataset.startAt || '0', 10) || startAt;
          var elapsed = Date.now() - started;
          var remainingMin = Math.max(0, MIN_DISPLAY_MS - elapsed);
          var wait = Math.max(remainingMin, STABILIZATION_MS);
          setTimeout(function(){ hideOverlayRespectingMinAndFinalize(targetIframe); }, wait);
        };
        try{
          targetIframe.addEventListener('load', onload, {once:true});
        }catch(e){ /* ignore */ }
        // try to detect readyState for same-origin quickly and trigger the same stabilized hide
        setTimeout(function(){
          if(done) return;
          try{
            var rd = targetIframe.contentWindow && targetIframe.contentWindow.document && targetIframe.contentWindow.document.readyState;
            if(rd === 'complete' || rd === 'interactive') onload();
          }catch(e){ /* cross-origin: no accesible */ }
        }, 500);
        return function(){ done = true; };
      }

      var LOAD_TIMEOUT_MS = 15000;
      function startLoad(){
        if(!dataSrc) return;
        showOverlay();
        // show spinner
        var sp = container.querySelector('.spinner');
        if(sp) sp.style.display = '';

        // set src immediately so the iframe starts loading while the overlay is visible
        try{
          if(!iframe.getAttribute('src') || iframe.getAttribute('src') === 'about:blank'){
            iframe.src = dataSrc;
          }
        }catch(e){ /* ignore */ }

        var cancelWatcher = watchIframeLoadAndFinalize(iframe);
        var timedOut = false;
        var to = setTimeout(function(){
          if(timedOut) return;
          timedOut = true;
          // No se cargó en tiempo, mostramos mensaje (sin botones)
          overlay.classList.add('error');
          var txt = overlay.querySelector('.overlay-text');
          if(txt) txt.textContent = 'No se pudo cargar el dashboard. Comprueba la conexión e inténtalo más tarde.';
          var sp = overlay.querySelector('.spinner');
          if(sp) sp.style.display = 'none';

        }, LOAD_TIMEOUT_MS);

        // If the iframe loads successfully, clear the timeout
        iframe.addEventListener('load', function(){
          clearTimeout(to);
        }, {once:true});
      }

      // auto start load
      startLoad();

      // For older iframes without data-src, keep the previous fallback
      if(!dataSrc){
        iframe.addEventListener('load', function(){ hideOverlayRespectingMinAndFinalize(iframe); }, {once:true});

        setTimeout(function(){
          var done = false;
          try{
            var rd = iframe.contentWindow && iframe.contentWindow.document && iframe.contentWindow.document.readyState;
            if(rd === 'complete' || rd === 'interactive') done = true;
          }catch(e){ /* cross-origin: no accesible */ }
          if(done){
            hideOverlayRespectingMinAndFinalize(iframe);
          }
        }, 500);

        setTimeout(function(){ hideOverlayRespectingMinAndFinalize(iframe); }, 15000);
      }

      // Opcional: si el iframe no carga por timeout, el overlay puede permanecer; podrías añadir un timeout para ocultarlo y mostrar mensaje de error.
    });
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', initIframes);
  } else {
    initIframes();
  }
})();
