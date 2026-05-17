# =============================================================================
# payments/urls.py   →   mounted at: api/payments/ (Mithaq/urls.py)
# OWNED BY: Ghadi
#
# FULL URL MAP:
#
#   AUTHENTICATED:
#       POST /api/payments/checkout/<plan_id>/  ← JS fetch() from checkout.html
#       GET  /api/payments/history/             ← user's payment records list
#
#   PUBLIC (Moyasar calls these, not the user):
#       GET  /api/payments/callback/    ← browser redirect after payment
#       POST /api/payments/webhook/     ← server-to-server Moyasar notification
#                                          (verified by MOYASAR_WEBHOOK_SECRET)
#
#   LEGACY REDIRECTS (kept so old links still work):
#       GET  /api/payments/success/     → /api/subscriptions/payment/success/
#       GET  /api/payments/failed/      → /api/subscriptions/payment/failed/
#
#   CALLBACK URL in .env:
#       MOYASAR_CALLBACK_URL=http://localhost:8000/api/payments/callback/
#   WEBHOOK URL to set in Moyasar dashboard:
#       https://yourdomain.com/api/payments/webhook/
# =============================================================================

from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    # Authenticated endpoints
    path('checkout/<int:plan_id>/', views.CheckoutView.as_view(),        name='checkout'),
    path('history/',                views.PaymentHistoryView.as_view(),   name='history'),

    # Public endpoints (Moyasar calls these)
    path('callback/',               views.PaymentCallbackView.as_view(), name='callback'),
    path('webhook/',                views.WebhookView.as_view(),          name='webhook'),

    # Legacy redirects
    path('success/',                views.payment_success,                name='success'),
    path('failed/',                 views.payment_failed,                 name='failed'),
]
