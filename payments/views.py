# =============================================================================
# payments/views.py
# OWNED BY: Ghadi
#
# PAYMENT FLOW (full picture):
#
#   1. User opens /api/subscriptions/checkout-page/<plan_id>/  (HTML page)
#   2. User clicks "ادفع الآن" → JS fetch() POSTs to:
#        POST /api/payments/checkout/<plan_id>/    ← CheckoutView
#        → Creates PaymentRecord (status=INITIATED)
#        → Calls Moyasar API → gets payment URL
#        → Returns { "payment_url": "https://..." }
#   3. JS redirects browser to Moyasar hosted payment page
#   4. User completes payment on Moyasar
#   5. Moyasar redirects browser to:
#        GET /api/payments/callback/?id=<moyasar_id>&status=paid
#        → PaymentCallbackView re-fetches from Moyasar API (never trusts params)
#        → Verifies amount, updates PaymentRecord to PAID
#        → Calls activate_subscription(user, plan) in subscription_service.py
#        → Redirects to /api/subscriptions/payment/success/ or /payment/failed/
#   6. Dashboard success/failed pages shown to user (subscriptions app)
#
# AUTH NOTE:
#   CheckoutView requires IsAuthenticated (JWT or session).
#   PaymentCallbackView is PUBLIC — Moyasar calls it, not the user.
#   Sessions work here because SessionAuthentication is in DRF settings.
#
# FUTURE WORK (Ghadi):
#   - Add a PaymentHistoryView: GET /api/payments/history/ → list user's PaymentRecords
#   - Handle refunds when Moyasar sends REFUNDED status
#   - Add webhook endpoint if Moyasar supports server-side webhooks
# =============================================================================

import logging

from django.conf import settings
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import PaymentRecord  # same package — no circular import
from subscriptions.models import SubscriptionPlan
from subscriptions.services.subscription_service import get_user_subscription

from .services.moyasar_service import MoyasarError, handle_callback, initiate_payment

logger = logging.getLogger(__name__)

# Module-level constant — no need to rebuild this dict on every request
METHOD_MAP = {
    'card':     'creditcard',  # credit/debit card via Moyasar hosted form
    'stcpay':   'stcpay',
    'applepay': 'applepay',
}


class CheckoutView(APIView):
    """POST /api/payments/checkout/<plan_id>/ — initiate a Moyasar payment session."""

    permission_classes = [IsAuthenticated]

    def post(self, request, plan_id):
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {'error': 'الباقة غير موجودة'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if plan.price == 0:
            return Response(
                {'error': 'هذه الباقة مجانية ولا تتطلب دفعاً'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sub = get_user_subscription(request.user)
        if sub and sub.plan.plan_type != SubscriptionPlan.PlanType.FREE:
            return Response(
                {'error': 'لديك اشتراك نشط بالفعل'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment_method = METHOD_MAP.get(
            request.data.get('payment_method', 'card'),
            'creditcard',   # default if frontend sends an unexpected value
        )

        try:
            payment_url = initiate_payment(request.user, plan, payment_method)
        except MoyasarError as exc:
            logger.error('Moyasar error during checkout | user=%s plan=%s error=%s',
                         request.user.id, plan_id, exc)
            return Response(
                {'error': 'خدمة الدفع غير متاحة حالياً، يرجى المحاولة لاحقاً'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({'payment_url': payment_url})


class PaymentCallbackView(APIView):
    """
    GET /api/payments/callback/
    Public endpoint — Moyasar redirects the user here after payment.
    Always re-verifies status with the Moyasar API before activating anything.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        moyasar_payment_id = request.GET.get('id')

        if not moyasar_payment_id:
            logger.warning('Callback received with no payment ID in query params')
            return redirect('/api/subscriptions/payment/failed/')

        try:
            result = handle_callback(moyasar_payment_id)
        except Exception as exc:
            logger.error('Callback error | payment_id=%s error=%s', moyasar_payment_id, exc)
            return redirect('/api/subscriptions/payment/failed/')

        if result == 'paid':
            # (added by ghadi: success page lives in subscriptions app — extends dashboard_base.html)
            return redirect('/api/subscriptions/payment/success/')

        # (added by ghadi: look up plan_id from the PaymentRecord so the failed page
        #  can link the "Try again" button back to the correct checkout page)
        plan_id = ''
        try:
            record = (
                PaymentRecord.objects
                .filter(moyasar_payment_id=moyasar_payment_id)
                .select_related('plan')
                .first()
            )
            if record:
                plan_id = str(record.plan.id)
        except Exception:
            pass  # plan_id stays '' — retry button on failed page won't have a target, that's acceptable

        return redirect(f'/api/subscriptions/payment/failed/?plan_id={plan_id}')


class PaymentHistoryView(APIView):
    """
    GET /api/payments/history/
    Returns the authenticated user's payment records, newest first.
    Skips orphaned tmp_ records (created if the Moyasar API call timed out before
    returning a real ID — those are deleted by initiate_payment on failure,
    but this filter is a safety net).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        records = (
            PaymentRecord.objects
            .filter(user=request.user)
            .exclude(moyasar_payment_id__startswith='tmp_')
            .select_related('plan')
            .order_by('-created_at')
        )

        data = [
            {
                'id':                 str(r.id),
                'plan_name':          r.plan.name,
                'plan_name_ar':       r.plan.name_ar,
                'amount':             str(r.amount),
                'currency':           r.currency,
                'status':             r.status,
                'payment_method':     r.payment_method,
                'moyasar_payment_id': r.moyasar_payment_id,
                'created_at':         r.created_at.isoformat(),
            }
            for r in records
        ]
        return Response(data)


class WebhookView(APIView):
    """
    POST /api/payments/webhook/
    Server-to-server notification from Moyasar (fires independently of the
    browser callback). Moyasar includes a secret_token in the request body
    that must match MOYASAR_WEBHOOK_SECRET in settings.

    This reuses handle_callback() so all the same idempotency and amount-
    integrity checks apply. Configure the webhook URL in your Moyasar dashboard:
        https://dashboard.moyasar.com → Settings → Webhooks
        URL: https://yourdomain.com/api/payments/webhook/
    """

    # Auth is done by verifying the secret_token in the body, not by JWT/session
    permission_classes = [AllowAny]

    def post(self, request):
        # Step 1: verify the webhook secret — reject anything that doesn't match
        incoming_secret = request.data.get('secret_token', '')
        expected_secret = settings.MOYASAR_WEBHOOK_SECRET

        if not expected_secret:
            logger.error('MOYASAR_WEBHOOK_SECRET is not configured — rejecting webhook')
            return Response({'error': 'webhook not configured'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if not incoming_secret or incoming_secret != expected_secret:
            logger.warning(
                'Webhook rejected: invalid secret_token | ip=%s',
                request.META.get('REMOTE_ADDR'),
            )
            return Response({'error': 'unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        # Step 2: extract the Moyasar payment ID from the webhook body
        moyasar_payment_id = request.data.get('id')
        if not moyasar_payment_id:
            logger.warning('Webhook received with no payment ID in body')
            return Response({'error': 'missing payment id'}, status=status.HTTP_400_BAD_REQUEST)

        logger.info('Webhook received | payment_id=%s', moyasar_payment_id)

        # Step 3: process — same as the browser callback
        # handle_callback() re-fetches from Moyasar, verifies amount, updates DB
        try:
            result = handle_callback(moyasar_payment_id)
            logger.info('Webhook processed | payment_id=%s result=%s', moyasar_payment_id, result)
        except ValueError as exc:
            # PaymentRecord not found — Moyasar fired a webhook for an unknown payment
            logger.error('Webhook: PaymentRecord not found | payment_id=%s error=%s', moyasar_payment_id, exc)
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logger.error('Webhook processing error | payment_id=%s error=%s', moyasar_payment_id, exc)
            return Response({'error': 'processing failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Return 200 so Moyasar stops retrying
        return Response({'status': result})


# ── Legacy result page URLs ───────────────────────────────────────────────────
# These URLs (/api/payments/success/ and /api/payments/failed/) still exist in
# payments/urls.py. The callback no longer sends users here — it goes to
# /api/subscriptions/payment/success/ and /payment/failed/ instead.
# These views redirect to the correct pages so direct navigation still works.

def payment_success(request):
    """Redirect to the dashboard-integrated success page in the subscriptions app."""
    return redirect('/api/subscriptions/payment/success/')


def payment_failed(request):
    """Redirect to the dashboard-integrated failed page in the subscriptions app."""
    plan_id = request.GET.get('plan_id', '')
    return redirect(f'/api/subscriptions/payment/failed/?plan_id={plan_id}')
