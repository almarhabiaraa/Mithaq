/* subscriptions_plans.js — billing toggle + checkout redirect logic
 *
 * IMPORTANT: this file reads window.PLAN_PRICES which must be injected
 * by the Django template before this script loads, e.g.:
 *
 *   <script>
 *     window.PLAN_PRICES = {
 *       basic:        parseFloat('{{ plans.basic.price|default:"0" }}'),
 *       professional: parseFloat('{{ plans.professional.price|default:"0" }}'),
 *     };
 *   </script>
 *   <script src="{% static 'js/subscriptions_plans.js' %}"></script>
 *
 * Static JS files are not processed by Django's template engine so
 * {{ }} variables must be passed via a data bridge like window.PLAN_PRICES.
 */

let isYearly = false;

// Yearly = monthly × 10  (2 months free ≈ 20% discount)
function yearlyPrice(monthly) {
    return (monthly * 10).toFixed(0);
}

function switchBilling() {
    isYearly = !isYearly;
    document.getElementById('billing-toggle').classList.toggle('yearly', isYearly);
    document.getElementById('lbl-monthly').style.color = isYearly ? 'var(--text-grey)' : 'var(--navy)';
    document.getElementById('lbl-yearly').style.color  = isYearly ? 'var(--navy)'      : 'var(--text-grey)';
    updatePrices();
}

function updatePrices() {
    const prices = window.PLAN_PRICES || {};
    ['basic', 'professional'].forEach(function (key) {
        const el     = document.getElementById('price-' + key);
        const period = document.getElementById('period-' + key);
        if (!el || prices[key] === undefined) return;

        // Fade out → update → fade in
        el.classList.add('fading');
        setTimeout(function () {
            el.textContent     = isYearly ? yearlyPrice(prices[key]) : prices[key].toFixed(0);
            period.textContent = isYearly ? 'سنوياً' : 'شهرياً';
            el.classList.remove('fading');
        }, 200);
    });
}

// Navigate to the checkout page for the selected plan
function goToCheckout(planId) {
    if (planId) {
        window.location.href = '/api/subscriptions/checkout-page/' + planId + '/';
    }
}
