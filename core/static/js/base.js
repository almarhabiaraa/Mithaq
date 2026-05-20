// Mobile menu toggle
const btn = document.getElementById('mobile-menu-btn');
const menu = document.getElementById('mobile-menu');
const iconOpen = document.getElementById('icon-open');
const iconClose = document.getElementById('icon-close');

if (btn) {
    btn.addEventListener('click', () => {
        const isHidden = menu.classList.toggle('hidden');
        iconOpen.classList.toggle('hidden', !isHidden);
        iconClose.classList.toggle('hidden', isHidden);
    });
}