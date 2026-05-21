const resetForm = document.getElementById(
    "resetPasswordForm"
);

const passwordInput = document.getElementById(
    "password"
);

const confirmPasswordInput =
    document.getElementById(
        "confirmPassword"
    );

const passwordError =
    document.getElementById(
        "passwordError"
    );

if (resetForm) {
    resetForm.addEventListener(
        "submit",
        function (event) {

            passwordError.textContent = "";

            const password =
                passwordInput.value.trim();

            const confirmPassword =
                confirmPasswordInput.value.trim();

            if (password.length < 8) {
                event.preventDefault();

                passwordError.textContent =
                    "كلمة المرور يجب أن تكون 8 أحرف على الأقل.";

                return;
            }

            if (password !== confirmPassword) {
                event.preventDefault();

                passwordError.textContent =
                    "كلمتا المرور غير متطابقتين.";
            }
        }
    );
}