const togglePassword =
    document.getElementById("togglePassword");

if (togglePassword) {

    togglePassword.addEventListener(
        "click",
        function () {

            const input =
                document.getElementById("password");

            input.type =
                input.type === "password"
                    ? "text"
                    : "password";

            this.classList.toggle("bi-eye-slash");
            this.classList.toggle("bi-eye");
        }
    );
}


const toggleConfirmPassword =
    document.getElementById(
        "toggleConfirmPassword"
    );

if (toggleConfirmPassword) {

    toggleConfirmPassword.addEventListener(
        "click",
        function () {

            const input =
                document.getElementById(
                    "confirmPassword"
                );

            input.type =
                input.type === "password"
                    ? "text"
                    : "password";

            this.classList.toggle("bi-eye-slash");
            this.classList.toggle("bi-eye");
        }
    );
}