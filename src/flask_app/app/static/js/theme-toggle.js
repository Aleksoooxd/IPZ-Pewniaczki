document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('theme-toggle');
    const body = document.body;

    // Check for saved theme preference or default to 'dark'
    // This part now runs after DOMContentLoaded, ensuring body is ready.
    const currentTheme = localStorage.getItem('theme') || 'dark';
    if (currentTheme === 'dark') {
        body.classList.add('dark-mode');
    } else {
        body.classList.remove('dark-mode');
    }

    // After the theme is applied, make the body visible
    body.classList.add('theme-loaded'); // ADDED THIS LINE HERE to make the body visible

    // Update button icon based on current theme
    updateThemeToggleIcon();

    themeToggle.addEventListener('click', () => {
        body.classList.toggle('dark-mode');
        let theme = 'light';
        if (body.classList.contains('dark-mode')) {
            theme = 'dark';
        }
        localStorage.setItem('theme', theme);
        updateThemeToggleIcon();
    });

    function updateThemeToggleIcon() {
        const lightIcon = themeToggle.querySelector('.light-icon');
        const darkIcon = themeToggle.querySelector('.dark-icon');

        if (body.classList.contains('dark-mode')) {
            lightIcon.style.display = 'none';
            darkIcon.style.display = 'inline-block';
        } else {
            lightIcon.style.display = 'inline-block';
            darkIcon.style.display = 'none';
        }
    }
});