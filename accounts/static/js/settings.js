(function () {

    function syncToggle() {

        const dark =
            localStorage.getItem(
                "mithaq_dark_mode"
            ) === "true";

        document
            .querySelectorAll(".dark-mode-label")
            .forEach(function (element) {

                element.textContent =
                    dark ? "داكن" : "فاتح";

            });

        document
            .querySelectorAll(".dark-mode-toggle-track")
            .forEach(function (element) {

                element.classList.toggle(
                    "active",
                    dark
                );

            });
    }

    syncToggle();

    const originalToggle =
        window.toggleDarkMode;

    window.toggleDarkMode =
        function () {

            if (originalToggle) {
                originalToggle();
            }

            syncToggle();
        };

})();