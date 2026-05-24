function hideAllCards() {
    const cards = [
        "card-anchored",
        "card-pending",
        "card-notfound",
        "card-invalid",
        "card-error",
    ];

    cards.forEach(function (id) {
        const card = document.getElementById(id);
        if (card) {
            card.style.display = "none";
        }
    });
}

function setLoading(isLoading) {
    const btn = document.getElementById("verify-btn");
    const label = document.getElementById("btn-label");
    const spinner = document.getElementById("btn-spinner");

    if (!btn || !label || !spinner) return;

    btn.disabled = isLoading;
    label.textContent = isLoading ? "جارٍ التحقق..." : "تحقق الآن";
    spinner.style.display = isLoading ? "inline-block" : "none";
}

function showInputError(message) {
    const error = document.getElementById("input-error");

    if (!error) return;

    if (!message) {
        error.style.display = "none";
        error.textContent = "";
        return;
    }

    error.textContent = message;
    error.style.display = "block";
}

function fillValid(contract) {
    document.getElementById("a-title").textContent = contract.title || "-";
    document.getElementById("a-type").textContent = contract.contract_type_display || "-";
    document.getElementById("a-id").textContent = contract.id || "-";
    document.getElementById("a-status").textContent = contract.status_display || "-";
    document.getElementById("a-confirmed").textContent = contract.created_at || "-";
    document.getElementById("a-signed").textContent = contract.updated_at || "-";

    document.getElementById("a-parties").textContent =
        `${contract.signed_parties || 0} / ${contract.parties_count || 0}`;

    // (added by ghadi: show blockchain confirmation if available)
    const txLink = document.getElementById("a-tx-link");
    if (txLink) {
        if (contract.blockchain_tx) {
            txLink.textContent = contract.blockchain_confirmed_at
                ? 'مؤكّد على البلوك تشين — ' + contract.blockchain_confirmed_at
                : 'مسجّل على البلوك تشين';
            txLink.href = 'https://sepolia.etherscan.io/tx/' + contract.blockchain_tx;
            txLink.target = '_blank';
            txLink.rel = 'noopener';
        } else {
            txLink.textContent = 'محفوظ داخل ميثاق — بانتظار تأكيد البلوك تشين';
            txLink.removeAttribute('href');
        }
    }

    document.getElementById("card-anchored").style.display = "block";
}

function fillPending(contract) {
    document.getElementById("p-title").textContent = contract.title || "-";
    document.getElementById("p-id").textContent = contract.id || "-";
    document.getElementById("p-status").textContent = contract.status_display || "-";
    document.getElementById("p-created").textContent = contract.created_at || "-";
    document.getElementById("p-signed").textContent = contract.updated_at || "-";

    document.getElementById("p-parties").textContent =
        `${contract.signed_parties || 0} / ${contract.parties_count || 0}`;

    document.getElementById("card-pending").style.display = "block";
}

async function runVerify() {
    hideAllCards();
    showInputError("");

    const input =
        document.getElementById("contract-input") ||
        document.getElementById("hash-input") ||
        document.querySelector(".hash-input");

    if (!input) {
        alert("لم يتم العثور على حقل رقم العقد");
        return;
    }

    const contractId = input.value.trim();
    const apiUrl = input.dataset.apiUrl;

    if (!apiUrl) {
        alert("رابط التحقق غير موجود");
        return;
    }

    const uuidRegex =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

    if (!uuidRegex.test(contractId)) {
        const invalidCard = document.getElementById("card-invalid");

        if (invalidCard) {
            invalidCard.style.display = "block";
        }

        showInputError("يرجى إدخال رقم عقد صحيح مثل الرقم الموجود في صفحة تفاصيل العقد.");
        return;
    }

    setLoading(true);

    try {
        const response = await fetch(
            `${apiUrl}?contract_id=${encodeURIComponent(contractId)}`
        );

        const data = await response.json();

        hideAllCards();

        if (data.result === "VALID_COMPLETED") {
            fillValid(data.contract);
            return;
        }

        if (data.result === "VALID_PENDING_SIGNATURES") {
            fillPending(data.contract);
            return;
        }

        if (data.result === "NOT_FOUND") {
            document.getElementById("card-notfound").style.display = "block";
            return;
        }

        document.getElementById("card-invalid").style.display = "block";

    } catch (error) {
        console.error(error);
        document.getElementById("card-error").style.display = "block";
    } finally {
        setLoading(false);
    }
}

document.addEventListener("DOMContentLoaded", function () {
    hideAllCards();

    const input =
        document.getElementById("contract-input") ||
        document.getElementById("hash-input") ||
        document.querySelector(".hash-input");

    if (input) {
        input.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                runVerify();
            }
        });
    }
});