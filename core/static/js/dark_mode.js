(function () {
    var STORAGE_KEY = 'mithaq_dark_mode';

    function isDark() {
        return localStorage.getItem(STORAGE_KEY) === 'true';
    }

    function applyDark(dark) {
        document.body.classList.toggle('dark-mode', dark);
        document.documentElement.classList.toggle('dark-mode', dark);
    }

    // Apply on load based on stored preference
    function init() {
        applyDark(isDark());
    }

    // Toggle dark mode and persist
    function toggleDarkMode() {
        var dark = !isDark();
        localStorage.setItem(STORAGE_KEY, dark ? 'true' : 'false');
        applyDark(dark);

        // Update any toggle labels on the page
        var labels = document.querySelectorAll('.dark-mode-label');
        labels.forEach(function (el) {
            el.textContent = dark ? 'داكن' : 'فاتح';
        });

        var toggles = document.querySelectorAll('.dark-mode-toggle-track');
        toggles.forEach(function (el) {
            el.classList.toggle('active', dark);
        });
    }

    // Expose globally
    window.toggleDarkMode = toggleDarkMode;
    window.isDarkMode = isDark;

    // Run immediately
    init();
})();
