# =============================================================================
# subscriptions/urls.py   →   mounted at: api/subscriptions/ (Mithaq/urls.py)
# OWNED BY: Ghadi
#
# FULL URL MAP:
#
#   PUBLIC (no auth):
#       GET  /api/subscriptions/plans/            → PlanListView (JSON)
#       GET  /api/subscriptions/plans-page/       → plans_page (HTML)
#
#   AUTHENTICATED (session or JWT):
#       GET  /api/subscriptions/status/                   → SubscriptionStatusView (JSON)
#       GET  /api/subscriptions/upgrade-options/          → UpgradeOptionsView (JSON)
#       GET  /api/subscriptions/checkout-page/<id>/       → checkout_page (HTML)
#       GET  /api/subscriptions/dashboard/                → subscription_dashboard_page (HTML)
#       GET  /api/subscriptions/payment/success/          → payment_success_page (HTML)
#       GET  /api/subscriptions/payment/failed/           → payment_failed_page (HTML)
#         └─ ?plan_id=<id> query param used by the "Try again" button
#
# PAYMENT FLOW:
#   plans-page → checkout-page → [POST /api/payments/checkout/] → Moyasar
#   → /api/payments/callback/ → redirects here → payment/success/ or payment/failed/
# =============================================================================

from django.urls import path

from . import views

app_name = "subscriptions"

urlpatterns = [
    # ── JSON API endpoints ────────────────────────────────────────────────────
    path('plans/',           views.PlanListView.as_view(),           name='plans'),
    path('status/',          views.SubscriptionStatusView.as_view(), name='status'),
    path('upgrade-options/', views.UpgradeOptionsView.as_view(),     name='upgrade_options'),

    # ── HTML template pages ───────────────────────────────────────────────────
    # (added by ghadi: connects each template to its view function)
    path('plans-page/',                  views.plans_page,                  name='plans_page'),
    path('checkout-page/<int:plan_id>/', views.checkout_page,               name='checkout_page'),
    path('dashboard/',                   views.subscription_dashboard_page, name='dashboard'),

    # (added by ghadi: result pages — the payments callback redirects here after Moyasar responds)
    path('payment/success/', views.payment_success_page, name='payment_success'),
    path('payment/failed/',  views.payment_failed_page,  name='payment_failed'),
]
