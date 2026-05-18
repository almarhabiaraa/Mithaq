function toggleDeleteBtn() {
    const checkbox = document.getElementById('confirm-delete');
    const btn = document.getElementById('delete-btn');
    btn.disabled = !checkbox.checked;
}