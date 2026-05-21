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