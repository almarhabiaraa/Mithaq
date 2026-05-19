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
#   PUBLIC (Moyasar redirects the user's browser here after payment):
#       GET  /api/payments/callback/    ← Moyasar sends the user here after paying
#
#   LEGACY REDIRECTS (kept so old links still work):
#       GET  /api/payments/success/     → /api/subscriptions/payment/success/
#       GET  /api/payments/failed/      → /api/subscriptions/payment/failed/
#
#   CALLBACK URL in .env:
#       MOYASAR_CALLBACK_URL=http://localhost:8000/api/payments/callback/
# =============================================================================

from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    # Authenticated endpoints
    path('checkout/<int:plan_id>/', views.CheckoutView.as_view(),        name='checkout'),
    path('history/',                views.PaymentHistoryView.as_view(),   name='history'),

    # Public endpoint (Moyasar redirects user's browser here)
    path('callback/',               views.PaymentCallbackView.as_view(), name='callback'),

    # Legacy redirects
    path('success/',                views.payment_success,                name='success'),
    path('failed/',                 views.payment_failed,                 name='failed'),
]
