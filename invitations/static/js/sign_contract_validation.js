function validateSignerName() {
    const typedName = document.getElementById("typedName").value.trim();

    const expectedNameElement = document.getElementById("expectedSignerName");

    if (!expectedNameElement) {
        return true;
    }

    const expectedName = expectedNameElement.dataset.expectedName.trim();

    if (typedName !== expectedName) {
        alert("يجب كتابة الاسم مطابقًا تمامًا للاسم المسجل في العقد.");
        return false;
    }

    return true;
}
document.addEventListener("DOMContentLoaded", function () {
    const params = new URLSearchParams(window.location.search);

    if (params.get("open_sign_modal") === "1") {
        const signModalElement = document.getElementById("signContractModal");

        if (signModalElement && typeof bootstrap !== "undefined") {
            const modal = new bootstrap.Modal(signModalElement);
            modal.show();
        }
    }
});
