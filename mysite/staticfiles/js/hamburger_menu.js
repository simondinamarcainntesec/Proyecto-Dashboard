/**
 * hamburger_menu.js
 * Script para controlar el menú hamburguesa en móviles
 * Se activa automáticamente cuando viewport < 768px
 */

(function () {
    'use strict';

    // Esperar a que el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    function init() {
        // Crear botón siempre (CSS controla visibilidad)
        createHamburgerButton();
        setupEventListeners();

        // Si estamos en desktop, asegurar sidebar cerrado
        if (window.innerWidth >= 768) {
            const sidebar = document.querySelector('.sidebar');
            if (sidebar) {
                sidebar.classList.remove('is-open');
            }
            document.body.classList.remove('sidebar-open');
        }
    }

    /**
     * Crear el botón hamburguesa y agregarlo a la topbar
     */
    function createHamburgerButton() {
        // Verificar si ya existe
        if (document.querySelector('.hamburger-btn')) {
            return;
        }

        const topbar = document.querySelector('.topbar');
        const topLeft = document.querySelector('.top-left');

        if (!topbar || !topLeft) {
            console.warn('Hamburger menu: .topbar o .top-left no encontrados');
            return;
        }

        // Crear botón
        const hamburger = document.createElement('button');
        hamburger.className = 'hamburger-btn';
        hamburger.setAttribute('aria-label', 'Abrir menú de navegación');
        hamburger.setAttribute('aria-expanded', 'false');
        hamburger.type = 'button';
        hamburger.innerHTML = '☰'; // Carácter hamburguesa

        // Insertar al principio de top-left
        topLeft.insertBefore(hamburger, topLeft.firstChild);
    }

    /**
     * Configurar event listeners
     */
    function setupEventListeners() {
        const hamburger = document.querySelector('.hamburger-btn');
        const sidebar = document.querySelector('.sidebar');

        if (!hamburger || !sidebar) {
            return;
        }

        // Click en hamburguesa
        hamburger.addEventListener('click', function (e) {
            e.stopPropagation();
            toggleSidebar();
        });

        // Click en el backdrop (body::before)
        document.body.addEventListener('click', function (e) {
            // Si el sidebar está abierto y click fuera del sidebar
            if (document.body.classList.contains('sidebar-open')) {
                if (!sidebar.contains(e.target) && !e.target.closest('.hamburger-btn')) {
                    closeSidebar();
                }
            }
        });

        // Click en enlaces del sidebar (cerrar al navegar)
        const sidebarLinks = sidebar.querySelectorAll('a.nav-item, a.nav-subitem');
        sidebarLinks.forEach(link => {
            link.addEventListener('click', function () {
                // Pequeño delay para que la navegación se complete
                setTimeout(closeSidebar, 150);
            });
        });

        // Tecla Escape para cerrar
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && document.body.classList.contains('sidebar-open')) {
                closeSidebar();
            }
        });

        // Resize: remover clases si volvemos a desktop
        window.addEventListener('resize', handleResize);
    }

    /**
     * Toggle sidebar
     */
    function toggleSidebar() {
        const isOpen = document.body.classList.contains('sidebar-open');
        if (isOpen) {
            closeSidebar();
        } else {
            openSidebar();
        }
    }

    /**
     * Abrir sidebar
     */
    function openSidebar() {
        const sidebar = document.querySelector('.sidebar');
        const hamburger = document.querySelector('.hamburger-btn');

        if (!sidebar) return;

        sidebar.classList.add('is-open');
        document.body.classList.add('sidebar-open');

        if (hamburger) {
            hamburger.setAttribute('aria-expanded', 'true');
            hamburger.innerHTML = '✕'; // Cambiar a X
        }

        // Prevenir scroll del body
        document.body.style.overflow = 'hidden';
    }

    /**
     * Cerrar sidebar
     */
    function closeSidebar() {
        const sidebar = document.querySelector('.sidebar');
        const hamburger = document.querySelector('.hamburger-btn');

        if (!sidebar) return;

        sidebar.classList.remove('is-open');
        document.body.classList.remove('sidebar-open');

        if (hamburger) {
            hamburger.setAttribute('aria-expanded', 'false');
            hamburger.innerHTML = '☰'; // Volver a hamburguesa
        }

        // Restaurar scroll del body
        document.body.style.overflow = '';
    }

    /**
     * Manejar resize
     */
    function handleResize() {
        const width = window.innerWidth;

        if (width >= 768) {
            // Desktop: remover todo
            closeSidebar();
            const hamburger = document.querySelector('.hamburger-btn');
            if (hamburger) {
                hamburger.style.display = 'none';
            }
        } else {
            // Mobile: asegurar que el hamburguesa esté visible
            let hamburger = document.querySelector('.hamburger-btn');
            if (!hamburger) {
                createHamburgerButton();
                setupEventListeners();
            } else {
                hamburger.style.display = '';
            }
        }
    }

})();
