document.getElementById('togglePassword').addEventListener('click', function() {
    const password = document.getElementById('password');
    if (password.type === 'password') {
        password.type = 'text';
        this.classList.replace('bi-eye-slash', 'bi-eye');
    } else {
        password.type = 'password';
        this.classList.replace('bi-eye', 'bi-eye-slash');
    }
});