const forgotForm = document.getElementById(
    "forgotPasswordForm"
);

const emailInput = document.getElementById(
    "email"
);

const emailError = document.getElementById(
    "emailError"
);

if (forgotForm) {
    forgotForm.addEventListener(
        "submit",
        function (event) {

            emailError.textContent = "";

            const email = emailInput.value.trim();

            const emailRegex =
                /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

            if (!emailRegex.test(email)) {
                event.preventDefault();

                emailError.textContent =
                    "يرجى إدخال بريد إلكتروني صحيح.";
            }
        }
    );
}