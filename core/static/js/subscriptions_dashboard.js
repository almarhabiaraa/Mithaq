/* subscriptions_dashboard.js — cancel subscription modal logic */

// ── Modal controls ──────────────────────────────────────────────────────────

function openCancelModal() {
    // BUG FIX: use style.display instead of classList.add/remove('hidden')
    // because Tailwind is not loaded in dashboard_base — 'hidden' has no effect.
    document.getElementById('cancel-modal').style.display = 'flex';
}

function closeCancelModal() {
    document.getElementById('cancel-modal').style.display = 'none';
}

// Close when clicking the dark overlay (not the card itself)
document.addEventListener('DOMContentLoaded', function () {
    const overlay = document.getElementById('cancel-modal');
    if (overlay) {
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeCancelModal();
        });
    }
});

// ── Cancel subscription API call ────────────────────────────────────────────

async function cancelSubscription() {
    const btn = document.getElementById('confirm-cancel-btn');
    btn.textContent = 'جارٍ الإلغاء...';
    btn.disabled = true;

    const csrfToken = document.cookie.split(';')
        .map(c => c.trim())
        .find(c => c.startsWith('csrftoken='))
        ?.split('=')[1] || '';

    try {
        const response = await fetch('/api/subscriptions/cancel/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
        });

        const data = await response.json();

        if (response.ok) {
            closeCancelModal();
            showToast('تم إلغاء اشتراكك بنجاح');
            setTimeout(() => window.location.reload(), 1500);
        } else {
            throw new Error(data.error || 'حدث خطأ غير متوقع');
        }
    } catch (err) {
        showToast(err.message, 'error');
        btn.textContent = 'نعم، إلغاء الاشتراك';
        btn.disabled = false;
    }
}

// ── Toast notification ──────────────────────────────────────────────────────

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    // BUG FIX: use inline styles instead of Tailwind classes.
    // Tailwind is not loaded in dashboard_base so those classes have no effect.
    toast.style.cssText = [
        'position:fixed',
        'bottom:24px',
        'left:50%',
        'transform:translateX(-50%)',
        'padding:12px 24px',
        'border-radius:10px',
        'color:#fff',
        'font-weight:700',
        'font-size:14px',
        'box-shadow:0 4px 20px rgba(0,0,0,.2)',
        'z-index:200',
        'font-family:inherit',
        'white-space:nowrap',
        `background:${type === 'error' ? '#C0392B' : '#16A34A'}`,
    ].join(';');
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
