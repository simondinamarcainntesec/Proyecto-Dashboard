// static/js/theme-switcher.js

document.addEventListener('DOMContentLoaded', () => {
    const themeSwitcher = document.getElementById('theme-switcher');
    const currentTheme = localStorage.getItem('theme') || 'light';

    document.body.classList.add(currentTheme + '-mode');
    themeSwitcher.textContent = currentTheme === 'light' ? '🌙' : '☀️';

    themeSwitcher.addEventListener('click', () => {
        let newTheme = document.body.classList.contains('light-mode') ? 'dark' : 'light';
        
        document.body.classList.remove('light-mode', 'dark-mode');
        document.body.classList.add(newTheme + '-mode');
        
        localStorage.setItem('theme', newTheme);

        themeSwitcher.textContent = newTheme === 'light' ? '🌙' : '☀️';
    });
});