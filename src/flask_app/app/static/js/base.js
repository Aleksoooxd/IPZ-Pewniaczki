// Sidebar toggle
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.body.classList.toggle('sidebar-open');
}

// Scroll to top button
const scrollToTopBtn = document.getElementById("scrollToTopBtn");

window.onscroll = function() {
  scrollToTopBtn.style.display =
    (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20)
      ? "flex" : "none";
};

scrollToTopBtn.addEventListener("click", function() {
  window.scrollTo({ top: 0, behavior: 'smooth' });
});


document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('theme-toggle');
    const html = document.documentElement;

    // Default: dark. Light mode = data-theme="light" on <html>
    const savedTheme = localStorage.getItem('theme') || 'dark';
    if (savedTheme === 'light') {
        html.setAttribute('data-theme', 'light');
    } else {
        html.removeAttribute('data-theme');
    }

    document.body.classList.add('theme-loaded');
    updateIcon();

    themeToggle.addEventListener('click', () => {
        const isLight = html.getAttribute('data-theme') === 'light';
        if (isLight) {
            html.removeAttribute('data-theme');
            localStorage.setItem('theme', 'dark');
        } else {
            html.setAttribute('data-theme', 'light');
            localStorage.setItem('theme', 'light');
        }
        updateIcon();
    });

    function updateIcon() {
        const isLight = html.getAttribute('data-theme') === 'light';
        const lightIcon = themeToggle.querySelector('.light-icon');
        const darkIcon  = themeToggle.querySelector('.dark-icon');
        if (lightIcon) lightIcon.style.display = isLight ? 'none' : 'inline-block';
        if (darkIcon)  darkIcon.style.display  = isLight ? 'inline-block' : 'none';
    }
});