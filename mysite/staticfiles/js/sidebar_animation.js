/**
 * Animación del Sidebar - Portal Clientes
 * Animaciones suaves para el sidebar sin botón toggle
 * Integrado con el tema de base.css
 */

(function() {
  'use strict';

  // Constantes (usando las variables CSS del tema)
  const ANIMATION_DURATION = 300; // ms

  // Elementos del DOM
  let sidebar = null;
  let brandEl = null;
  let navItems = null;
  let navDropdowns = null;

  /**
   * Inicializa la animación del sidebar
   */
  function init() {
    sidebar = document.querySelector('.sidebar');
    if (!sidebar) {
      console.warn('Sidebar no encontrado');
      return;
    }

    cacheElements();
    addStyles();
    attachEventListeners();
    animateOnLoad();
  }

  /**
   * Cachea elementos del DOM para mejor rendimiento
   */
  function cacheElements() {
    brandEl = sidebar.querySelector('.brand');
    navItems = sidebar.querySelectorAll('.nav-item');
    navDropdowns = sidebar.querySelectorAll('.nav-dropdown');
  }

  /**
   * Agrega los estilos CSS necesarios para la animación
   */
  function addStyles() {
    const styleId = 'sidebar-animation-styles';
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      /* =========================================================
         Animación Sidebar - Integrado con base.css
         ========================================================= */

      /* Animación de entrada inicial */
      @keyframes slideInFromLeft {
        from {
          opacity: 0;
          transform: translateX(-16px);
        }
        to {
          opacity: 1;
          transform: translateX(0);
        }
      }

      .sidebar.animate-in .brand {
        animation: slideInFromLeft 450ms cubic-bezier(0.4, 0.0, 0.2, 1) forwards;
      }

      .sidebar.animate-in .nav-item {
        animation: slideInFromLeft 400ms cubic-bezier(0.4, 0.0, 0.2, 1) forwards;
        opacity: 0;
      }

      .sidebar.animate-in .nav-item:nth-child(1) { animation-delay: 50ms; }
      .sidebar.animate-in .nav-item:nth-child(2) { animation-delay: 100ms; }
      .sidebar.animate-in .nav-item:nth-child(3) { animation-delay: 150ms; }
      .sidebar.animate-in .nav-item:nth-child(4) { animation-delay: 200ms; }
      .sidebar.animate-in .nav-item:nth-child(5) { animation-delay: 250ms; }
      .sidebar.animate-in .nav-item:nth-child(6) { animation-delay: 300ms; }
      .sidebar.animate-in .nav-item:nth-child(7) { animation-delay: 350ms; }

      /* Animación de subitems en carga inicial (para dropdowns ya abiertos) */
      .sidebar.animate-in .nav-subitem {
        animation: slideInFromLeft 400ms cubic-bezier(0.4, 0.0, 0.2, 1) forwards;
        opacity: 0;
      }

      /* Los subitems continúan la cascada después de su nav-item padre */
      .sidebar.animate-in .nav-item:nth-child(1) .nav-subitem:nth-child(1) { animation-delay: 100ms; }
      .sidebar.animate-in .nav-item:nth-child(1) .nav-subitem:nth-child(2) { animation-delay: 150ms; }
      .sidebar.animate-in .nav-item:nth-child(1) .nav-subitem:nth-child(3) { animation-delay: 200ms; }
      .sidebar.animate-in .nav-item:nth-child(1) .nav-subitem:nth-child(4) { animation-delay: 250ms; }
      .sidebar.animate-in .nav-item:nth-child(1) .nav-subitem:nth-child(5) { animation-delay: 300ms; }
      .sidebar.animate-in .nav-item:nth-child(1) .nav-subitem:nth-child(6) { animation-delay: 350ms; }

      .sidebar.animate-in .nav-item:nth-child(2) .nav-subitem:nth-child(1) { animation-delay: 150ms; }
      .sidebar.animate-in .nav-item:nth-child(2) .nav-subitem:nth-child(2) { animation-delay: 200ms; }
      .sidebar.animate-in .nav-item:nth-child(2) .nav-subitem:nth-child(3) { animation-delay: 250ms; }
      .sidebar.animate-in .nav-item:nth-child(2) .nav-subitem:nth-child(4) { animation-delay: 300ms; }
      .sidebar.animate-in .nav-item:nth-child(2) .nav-subitem:nth-child(5) { animation-delay: 350ms; }
      .sidebar.animate-in .nav-item:nth-child(2) .nav-subitem:nth-child(6) { animation-delay: 400ms; }

      .sidebar.animate-in .nav-item:nth-child(3) .nav-subitem:nth-child(1) { animation-delay: 200ms; }
      .sidebar.animate-in .nav-item:nth-child(3) .nav-subitem:nth-child(2) { animation-delay: 250ms; }
      .sidebar.animate-in .nav-item:nth-child(3) .nav-subitem:nth-child(3) { animation-delay: 300ms; }
      .sidebar.animate-in .nav-item:nth-child(3) .nav-subitem:nth-child(4) { animation-delay: 350ms; }
      .sidebar.animate-in .nav-item:nth-child(3) .nav-subitem:nth-child(5) { animation-delay: 400ms; }
      .sidebar.animate-in .nav-item:nth-child(3) .nav-subitem:nth-child(6) { animation-delay: 450ms; }

      .sidebar.animate-in .nav-item:nth-child(4) .nav-subitem:nth-child(1) { animation-delay: 250ms; }
      .sidebar.animate-in .nav-item:nth-child(4) .nav-subitem:nth-child(2) { animation-delay: 300ms; }
      .sidebar.animate-in .nav-item:nth-child(4) .nav-subitem:nth-child(3) { animation-delay: 350ms; }
      .sidebar.animate-in .nav-item:nth-child(4) .nav-subitem:nth-child(4) { animation-delay: 400ms; }
      .sidebar.animate-in .nav-item:nth-child(4) .nav-subitem:nth-child(5) { animation-delay: 450ms; }
      .sidebar.animate-in .nav-item:nth-child(4) .nav-subitem:nth-child(6) { animation-delay: 500ms; }

      .sidebar.animate-in .nav-item:nth-child(5) .nav-subitem:nth-child(1) { animation-delay: 300ms; }
      .sidebar.animate-in .nav-item:nth-child(5) .nav-subitem:nth-child(2) { animation-delay: 350ms; }
      .sidebar.animate-in .nav-item:nth-child(5) .nav-subitem:nth-child(3) { animation-delay: 400ms; }
      .sidebar.animate-in .nav-item:nth-child(5) .nav-subitem:nth-child(4) { animation-delay: 450ms; }
      .sidebar.animate-in .nav-item:nth-child(5) .nav-subitem:nth-child(5) { animation-delay: 500ms; }
      .sidebar.animate-in .nav-item:nth-child(5) .nav-subitem:nth-child(6) { animation-delay: 550ms; }

      .sidebar.animate-in .nav-item:nth-child(6) .nav-subitem:nth-child(1) { animation-delay: 350ms; }
      .sidebar.animate-in .nav-item:nth-child(6) .nav-subitem:nth-child(2) { animation-delay: 400ms; }
      .sidebar.animate-in .nav-item:nth-child(6) .nav-subitem:nth-child(3) { animation-delay: 450ms; }
      .sidebar.animate-in .nav-item:nth-child(6) .nav-subitem:nth-child(4) { animation-delay: 500ms; }
      .sidebar.animate-in .nav-item:nth-child(6) .nav-subitem:nth-child(5) { animation-delay: 550ms; }
      .sidebar.animate-in .nav-item:nth-child(6) .nav-subitem:nth-child(6) { animation-delay: 600ms; }

      .sidebar.animate-in .nav-item:nth-child(7) .nav-subitem:nth-child(1) { animation-delay: 400ms; }
      .sidebar.animate-in .nav-item:nth-child(7) .nav-subitem:nth-child(2) { animation-delay: 450ms; }
      .sidebar.animate-in .nav-item:nth-child(7) .nav-subitem:nth-child(3) { animation-delay: 500ms; }
      .sidebar.animate-in .nav-item:nth-child(7) .nav-subitem:nth-child(4) { animation-delay: 550ms; }
      .sidebar.animate-in .nav-item:nth-child(7) .nav-subitem:nth-child(5) { animation-delay: 600ms; }
      .sidebar.animate-in .nav-item:nth-child(7) .nav-subitem:nth-child(6) { animation-delay: 650ms; }

      /* Animación hover suave */
      .sidebar .nav-item {
        transition: transform 180ms cubic-bezier(0.4, 0.0, 0.2, 1);
      }

      /* ===== ANIMACIÓN DE DROPDOWNS ===== */
      
      /* Transición suave del chevron */
      .sidebar .chevron {
        transition: transform 280ms cubic-bezier(0.4, 0.0, 0.2, 1);
      }

      .sidebar details.nav-dropdown[open] .chevron {
        transform: rotate(180deg);
      }

      /* Animación del contenedor de submenu */
      .sidebar details.nav-dropdown .tenant-list.nav-submenu {
        overflow: hidden;
        max-height: 0;
        opacity: 0;
        transform: translateY(-8px);
        transition: opacity 400ms cubic-bezier(0.4, 0.0, 0.2, 1),
                    transform 400ms cubic-bezier(0.4, 0.0, 0.2, 1),
                    max-height 400ms cubic-bezier(0.4, 0.0, 0.2, 1),
                    margin 400ms cubic-bezier(0.4, 0.0, 0.2, 1);
      }

      .sidebar details.nav-dropdown[open] .tenant-list.nav-submenu {
        max-height: 500px;
        opacity: 1;
        transform: translateY(0);
      }

      /* Animación de cierre */
      .sidebar details.nav-dropdown.is-closing .tenant-list.nav-submenu {
        max-height: 0;
        opacity: 0;
        transform: translateY(-8px);
      }

      /* Subitems - estado inicial oculto */
      .sidebar .nav-subitem {
        opacity: 0;
        transform: translateX(-12px);
        transition: opacity 350ms cubic-bezier(0.4, 0.0, 0.2, 1),
                    transform 350ms cubic-bezier(0.4, 0.0, 0.2, 1);
      }

      /* Estado visible cuando el dropdown está abierto (sin animación) */
      .sidebar details.nav-dropdown[open] .nav-subitem {
        opacity: 1;
        transform: translateX(0);
      }

      /* Animación individual de cada subitem al abrir */
      .sidebar details.nav-dropdown.is-opening .nav-subitem:nth-child(1) {
        transition-delay: 80ms;
      }
      .sidebar details.nav-dropdown.is-opening .nav-subitem:nth-child(2) {
        transition-delay: 140ms;
      }
      .sidebar details.nav-dropdown.is-opening .nav-subitem:nth-child(3) {
        transition-delay: 200ms;
      }
      .sidebar details.nav-dropdown.is-opening .nav-subitem:nth-child(4) {
        transition-delay: 260ms;
      }
      .sidebar details.nav-dropdown.is-opening .nav-subitem:nth-child(5) {
        transition-delay: 320ms;
      }
      .sidebar details.nav-dropdown.is-opening .nav-subitem:nth-child(6) {
        transition-delay: 380ms;
      }

      /* Animación de cierre de subitems (sobrescribe el estado [open]) */
      .sidebar details.nav-dropdown.is-closing .nav-subitem {
        opacity: 0 !important;
        transform: translateX(-12px) !important;
        transition: opacity 350ms cubic-bezier(0.4, 0.0, 0.2, 1),
                    transform 350ms cubic-bezier(0.4, 0.0, 0.2, 1);
      }

      .sidebar details.nav-dropdown.is-closing .nav-subitem:nth-child(1) {
        transition-delay: 0ms;
      }
      .sidebar details.nav-dropdown.is-closing .nav-subitem:nth-child(2) {
        transition-delay: 0ms;
      }
      .sidebar details.nav-dropdown.is-closing .nav-subitem:nth-child(3) {
        transition-delay: 0ms;
      }
      .sidebar details.nav-dropdown.is-closing .nav-subitem:nth-child(4) {
        transition-delay: 0ms;
      }
      .sidebar details.nav-dropdown.is-closing .nav-subitem:nth-child(5) {
        transition-delay: 0ms;
      }
      .sidebar details.nav-dropdown.is-closing .nav-subitem:nth-child(6) {
        transition-delay: 0ms;
      }

      /* Efecto de fondo suave al abrir */
      .sidebar details.nav-dropdown[open] > summary {
        background: rgba(59,130,246,.08);
        transition: background 280ms cubic-bezier(0.4, 0.0, 0.2, 1);
      }

      /* Accesibilidad: reducir animaciones */
      @media (prefers-reduced-motion: reduce) {
        .sidebar.animate-in .nav-item,
        .sidebar.animate-in .brand {
          animation: none !important;
          opacity: 1 !important;
        }
        
        .sidebar .nav-item,
        .sidebar .chevron,
        .sidebar details.nav-dropdown .tenant-list.nav-submenu,
        .sidebar .nav-subitem {
          transition: none !important;
        }

        .sidebar .nav-subitem {
          opacity: 1 !important;
          transform: none !important;
        }
      }
    `;
    
    document.head.appendChild(style);
  }

  /**
   * Cierra todos los dropdowns excepto el especificado
   */
  function closeOtherDropdowns(currentDropdown) {
    navDropdowns.forEach(dropdown => {
      if (dropdown !== currentDropdown && dropdown.hasAttribute('open')) {
        // Agregar clase de cierre para animación
        dropdown.classList.add('is-closing');
        dropdown.classList.remove('is-opening');
        
        // Limpiar estilos inline para permitir animación CSS
        const subitems = dropdown.querySelectorAll('.nav-subitem');
        subitems.forEach(subitem => {
          subitem.style.removeProperty('opacity');
          subitem.style.removeProperty('transform');
        });
        
        // Cerrar después de la animación
        setTimeout(() => {
          dropdown.removeAttribute('open');
          dropdown.classList.remove('is-closing');
        }, 280);
      }
    });
  }

  /**
   * Maneja la animación de apertura de dropdown
   */
  function handleDropdownOpen(dropdown) {
    // Remover clase de cierre si existe
    dropdown.classList.remove('is-closing');
    
    // Resetear subitems al estado inicial
    const subitems = dropdown.querySelectorAll('.nav-subitem');
    subitems.forEach(subitem => {
      subitem.style.opacity = '0';
      subitem.style.transform = 'translateX(-12px)';
      subitem.style.transition = 'none';
    });
    
    // Forzar reflow para que el navegador procese los cambios
    dropdown.offsetHeight;
    
    // Restaurar transiciones y limpiar estilos inline
    subitems.forEach(subitem => {
      subitem.style.transition = '';
      // Remover estilos inline para que CSS tome el control
      subitem.style.removeProperty('opacity');
      subitem.style.removeProperty('transform');
    });
    
    // Agregar clase de apertura en el siguiente frame
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        dropdown.classList.add('is-opening');
      });
    });
  }

  /**
   * Adjunta los event listeners
   */
  function attachEventListeners() {
    // Animación hover suave
    navItems.forEach(item => {
      item.addEventListener('mouseenter', function() {
        this.style.transform = 'translateX(3px)';
      });

      item.addEventListener('mouseleave', function() {
        this.style.transform = '';
      });
    });

    // Manejar apertura/cierre de dropdowns
    navDropdowns.forEach(dropdown => {
      const summary = dropdown.querySelector('summary');
      
      // Capturar el click ANTES de que el navegador maneje el toggle
      summary.addEventListener('click', function(e) {
        const isCurrentlyOpen = dropdown.hasAttribute('open');
        
        if (isCurrentlyOpen) {
          // Está abierto, se va a cerrar
          e.preventDefault(); // Prevenir cierre inmediato
          
          // Animar cierre
          dropdown.classList.remove('is-opening');
          dropdown.classList.add('is-closing');
          
          // Limpiar estilos inline
          const subitems = dropdown.querySelectorAll('.nav-subitem');
          subitems.forEach(subitem => {
            subitem.style.removeProperty('opacity');
            subitem.style.removeProperty('transform');
          });
          
          // Cerrar después de la animación
          setTimeout(() => {
            dropdown.removeAttribute('open');
            dropdown.classList.remove('is-closing');
          }, 280);
        } else {
          // Está cerrado, se va a abrir - dejar que el navegador lo abra
          // NO preventDefault, permitir que se abra naturalmente
          closeOtherDropdowns(dropdown);
          
          // Programar animación para después de que el navegador lo abra
          setTimeout(() => {
            handleDropdownOpen(dropdown);
          }, 0);
        }
      });
    });
  }

  /**
   * Animación inicial al cargar la página
   */
  function animateOnLoad() {
    sidebar.classList.add('animate-in');
    setTimeout(() => {
      sidebar.classList.remove('animate-in');
    }, 900);
  }

  // Inicializar cuando el DOM esté listo
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();