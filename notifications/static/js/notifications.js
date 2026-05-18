function markAllRead() {
    fetch(markAllReadUrl, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken,
            'Content-Type': 'application/json',
        }
    }).then(res => {
        if (!res.ok) throw new Error();
        document.querySelectorAll('.notification-item.unread').forEach(item => {
            item.classList.remove('unread');
        });
        document.querySelector('.mark-all-btn')?.style.setProperty('display', 'none');
        document.querySelectorAll('.mithaq-badge').forEach(badge => badge.remove());
    }).catch(() => {
        alert('حدث خطأ، يرجى المحاولة مرة أخرى');
    });
}