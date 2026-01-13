(function() {
    document.addEventListener("DOMContentLoaded", function() {

        // 1. Limpieza preventiva de overlays globales (código original conservado)
        try {
            if (document.body.classList.contains('is-embed')) {
                var globalOv = document.getElementById('loading-overlay');
                if (globalOv && globalOv.parentNode) {
                    globalOv.parentNode.removeChild(globalOv);
                }
            }
        } catch (e) { /* ignore */ }

        // 2. Inicializar todos los contenedores de iframe encontrados
        const containers = document.querySelectorAll('.iframe-container');

        containers.forEach(function(container) {
            const iframe = container.querySelector('iframe');
            const overlay = container.querySelector('.iframe-overlay');

            if (!iframe || !overlay) return;

            // Función para finalizar la transición visual
            function revealDashboard() {
                // Prevenir ejecución múltiple
                if (iframe.classList.contains('is-loaded')) return;

                // Ocultar Overlay
                overlay.classList.add('hidden');
                overlay.setAttribute('aria-busy', 'false');

                // Mostrar Iframe
                iframe.classList.remove('is-loading');
                iframe.classList.add('is-loaded');
                iframe.removeAttribute('aria-hidden');
            }

            // A. INICIO: Mover data-src a src para comenzar la carga real
            if (iframe.dataset.src) {
                iframe.src = iframe.dataset.src;
            }

            // B. EVENTO LOAD: El navegador confirma que el iframe descargó el contenido
            iframe.addEventListener('load', function() {
                // Pequeño retardo (500ms) para permitir que el renderizado interno se estabilice
                // y evitar flashes blancos
                setTimeout(revealDashboard, 2500);
            });

            // C. FALLBACK: Timeout de seguridad (15 segundos)
            // Si el servidor del dashboard no responde, mostramos error o forzamos mostrar lo que haya
            setTimeout(function() {
                if (!overlay.classList.contains('hidden')) {
                    // Opción: Mostrar mensaje de error en el overlay sin quitarlo
                    overlay.classList.add('error');
                    
                    const txt = overlay.querySelector('.overlay-text');
                    if (txt) txt.textContent = "El servidor tarda en responder...";
                    
                    const errMsg = overlay.querySelector('.overlay-error-msg');
                    if (errMsg) errMsg.textContent = "Es posible que deba recargar la página.";
                    
                    // Si prefieres que se muestre el iframe de todas formas tras 15s, descomenta esto:
                    // revealDashboard();
                }
            }, 15000);
        });
    });
})();