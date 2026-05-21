/* verify.js — contract hash verification logic for verify.html
 *
 * Reads the API base URL from the input element's data-api-url attribute,
 * which is injected by VerifyPageView via template context: {{ api_url }}
 */

const STATUS_AR = {
    DRAFT:              'مسودة',
    PENDING_SIGNATURES: 'بانتظار التوقيعات',
    SIGNED:             'موقّع',
    COMPLETED:          'مكتمل',
    CANCELLED:          'ملغي',
};

function fmtDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('ar-SA', {
        year: 'numeric', month: 'long', day: 'numeric',
    });
}

function hideAll() {
    document.querySelectorAll('.result-card').forEach(function (c) {
        c.classList.remove('show');
    });
}

function showCard(id) {
    hideAll();
    const card = document.getElementById(id);
    if (card) {
        card.classList.add('show');
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function setLoading(on) {
    const btn     = document.getElementById('verify-btn');
    const label   = document.getElementById('btn-label');
    const spinner = document.getElementById('btn-spinner');
    const input   = document.getElementById('hash-input');
    btn.disabled      = on;
    input.disabled    = on;
    label.textContent = on ? 'جارٍ التحقق...' : 'تحقق الآن';
    spinner.style.display = on ? 'block' : 'none';
}

async function runVerify() {
    const input   = document.getElementById('hash-input');
    const errorEl = document.getElementById('input-error');
    const hash    = input.value.trim();

    errorEl.style.display = 'none';
    hideAll();

    if (!hash) {
        errorEl.textContent = 'يرجى إدخال رمز العقد';
        errorEl.style.display = 'block';
        return;
    }
    if (hash.length !== 64) {
        errorEl.textContent = 'الرمز يجب أن يكون 64 حرفاً (أدخلت ' + hash.length + ')';
        errorEl.style.display = 'block';
        return;
    }

    setLoading(true);

    try {
        const apiUrl = input.dataset.apiUrl || '/api/verify/';
        const res    = await fetch(apiUrl + encodeURIComponent(hash) + '/');
        setLoading(false);
        const data   = await res.json();

        switch (data.verification_status) {
            case 'VALID_AND_ANCHORED':
                document.getElementById('a-id').textContent      = data.contract_id || '—';
                document.getElementById('a-status').textContent  = STATUS_AR[data.contract_status] || data.contract_status || '—';
                document.getElementById('a-signed').textContent  = fmtDate(data.signed_at);
                document.getElementById('a-parties').textContent = (data.parties_count || 0) + ' طرف';
                var link = document.getElementById('a-tx-link');
                if (data.blockchain_tx) {
                    link.href        = 'https://sepolia.etherscan.io/tx/' + data.blockchain_tx;
                    link.textContent = data.blockchain_tx.slice(0, 22) + '…';
                } else { link.textContent = '—'; }
                document.getElementById('a-confirmed').textContent = fmtDate(data.blockchain_confirmed_at);
                showCard('card-anchored');
                break;
            case 'VALID_PENDING_CHAIN':
                document.getElementById('p-id').textContent      = data.contract_id || '—';
                document.getElementById('p-signed').textContent  = fmtDate(data.signed_at);
                document.getElementById('p-parties').textContent = (data.parties_count || 0) + ' طرف';
                showCard('card-pending');
                break;
            case 'NOT_FOUND':    showCard('card-notfound'); break;
            case 'INVALID_HASH': showCard('card-invalid');  break;
            default:             showCard('card-invalid');
        }
    } catch (err) {
        setLoading(false);
        showCard('card-error');
    }
}

// Allow pressing Enter in the input to trigger verification
document.addEventListener('DOMContentLoaded', function () {
    var input = document.getElementById('hash-input');
    if (input) {
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') runVerify();
        });
    }
});
