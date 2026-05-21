function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);

    if (parts.length === 2) {
        return parts.pop().split(";").shift();
    }
}

function statusBadge(status) {

    const map = {
        DRAFT: ["badge-draft", "مسودة"],

        PENDING_SIGNATURES: [
            "badge-pending",
            "بانتظار التوقيعات"
        ],

        SIGNED: [
            "badge-signed",
            "موقّع"
        ],

        COMPLETED: [
            "badge-completed",
            "مكتمل"
        ],

        CANCELLED: [
            "badge-cancelled",
            "ملغي"
        ],
    };

    const [cls, label] = map[status] || ["", status];

    return `
        <span class="badge ${cls}">
            ${label}
        </span>
    `;
}