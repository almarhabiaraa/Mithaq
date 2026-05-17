# =============================================================================
# subscriptions/views.py
# OWNED BY: Ghadi
#
# RULE: Views are thin. Each view makes at most ONE service/DB call and returns.
#       All business logic lives in subscriptions/services/subscription_service.py.
#
# API ENDPOINTS (JSON — require JWT or session auth unless noted):
#   GET  /api/subscriptions/plans/            → PlanListView         (public)
#   GET  /api/subscriptions/status/           → SubscriptionStatusView
#   GET  /api/subscriptions/upgrade-options/  → UpgradeOptionsView
#
# TEMPLATE PAGES (HTML — require session login unless noted):
#   GET  /api/subscriptions/plans-page/              → plans_page()
#   GET  /api/subscriptions/checkout-page/<id>/      → checkout_page()
#   GET  /api/subscriptions/dashboard/               → subscription_dashboard_page()
#   GET  /api/subscriptions/payment/success/         → payment_success_page()
#   GET  /api/subscriptions/payment/failed/          → payment_failed_page()
#
# HOW TEMPLATES FIND PLANS:
#   plans_page() passes 'plans' as a dict keyed by template name:
#       plans['basic']        → the SINGLE plan  (29 SAR)
#       plans['professional'] → the MONTHLY plan (99 SAR)
#   This maps the actual DB plan_types to the template card names.
#
# FUTURE WORK (Ghadi):
#   - Add cancel/manage subscription page
#   - Add webhook handler if Moyasar supports server-side notifications
# =============================================================================

import logging
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import PaymentRecord  # (added by ghadi: to show invoice history and payment details)
from .models import SubscriptionPlan
from .serializers import SubscriptionPlanSerializer
from .services.subscription_service import get_user_subscription

logger = logging.getLogger(__name__)

# (added by ghadi: 15% VAT rate applied to all subscription prices in Saudi Arabia)
VAT_RATE = Decimal('0.15')


# ── REST API Views ────────────────────────────────────────────────────────────

class PlanListView(APIView):
    """
    GET /api/subscriptions/plans/
    Public — no auth needed.
    Returns all active plans as JSON (used by mobile apps or external integrations).
    """

    permission_classes = [AllowAny]

    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
        return Response(SubscriptionPlanSerializer(plans, many=True).data)


class SubscriptionStatusView(APIView):
    """
    GET /api/subscriptions/status/
    Returns the authenticated user's active subscription as JSON.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = get_user_subscription(request.user)
        if not sub:
            return Response(
                {'error': 'لا يوجد اشتراك نشط'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            'plan':           sub.plan.name,
            'plan_ar':        sub.plan.name_ar,
            'status':         sub.status,
            'contracts_used': sub.contracts_used,
            'contract_limit': sub.plan.contract_limit,
            'expires_at':     sub.expires_at.date().isoformat() if sub.expires_at else None,
        })


class UpgradeOptionsView(APIView):
    """
    GET /api/subscriptions/upgrade-options/
    Returns the user's current plan and all plans with a higher price they can upgrade to.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = get_user_subscription(request.user)
        if not sub:
            return Response(
                {'error': 'لا يوجد اشتراك نشط'},
                status=status.HTTP_404_NOT_FOUND,
            )

        options = SubscriptionPlan.objects.filter(
            is_active=True,
            price__gt=sub.plan.price,
        ).order_by('price')

        return Response({
            'current_plan':    sub.plan.name,
            'current_plan_ar': sub.plan.name_ar,
            'contracts_used':  sub.contracts_used,
            'contract_limit':  sub.plan.contract_limit,
            'can_create':      sub.can_create_contract(),
            'upgrade_options': SubscriptionPlanSerializer(options, many=True).data,
        })


# ── HTML Template Views ───────────────────────────────────────────────────────

def plans_page(request):
    """
    GET /api/subscriptions/plans-page/
    Renders the plan selection page.

    (added by ghadi: passes plans as a dict so the template can reference
     plans.basic, plans.professional, plans.enterprise by name instead of
     iterating — each card in the template is hardcoded with specific features)

    Plan type mapping (actual DB types → template card names):
        SINGLE  → plans['basic']        (cheapest paid plan)
        MONTHLY → plans['professional'] (featured plan)
    """
    all_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    sub = get_user_subscription(request.user) if request.user.is_authenticated else None

    # (added by ghadi: map actual plan_type values to template-expected dict keys)
    plans = {}
    for plan in all_plans:
        if plan.plan_type == SubscriptionPlan.PlanType.SINGLE:
            plans['basic'] = plan
        elif plan.plan_type == SubscriptionPlan.PlanType.MONTHLY:
            plans['professional'] = plan
        # Enterprise plan doesn't exist yet — plans['enterprise'] stays None

    return render(request, 'subscriptions/plans.html', {
        'plans':       plans,       # dict: {'basic': <plan>, 'professional': <plan>}
        'current_sub': sub,         # current UserSubscription or None
    })


@login_required(login_url='accounts:sign_in')
def checkout_page(request, plan_id):
    """
    GET /api/subscriptions/checkout-page/<plan_id>/
    Renders the checkout/payment confirmation page.

    (added by ghadi: calculates VAT (15%) and total before rendering so the
     template can display them without any arithmetic in the template itself)
    """
    plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)

    # (added by ghadi: Saudi VAT is 15% — calculated server-side so frontend can't manipulate it)
    vat           = (plan.price * VAT_RATE).quantize(Decimal('0.01'))
    total_with_vat = plan.price + vat

    return render(request, 'subscriptions/checkout.html', {
        'plan':          plan,
        'vat':           vat,
        'total_with_vat': total_with_vat,
        'billing_type':  'شهري',   # default — yearly toggle is client-side only
        'plan_id':       plan.id,
    })


@login_required(login_url='accounts:sign_in')
def subscription_dashboard_page(request):
    """
    GET /api/subscriptions/dashboard/
    Renders the subscription management dashboard.

    (added by ghadi: shows current subscription info + full invoice history
     from PaymentRecord — imported from the payments app)
    """
    sub = get_user_subscription(request.user)

    # (added by ghadi: fetch all payment records for this user, newest first)
    payments = (
        PaymentRecord.objects
        .filter(user=request.user)
        .select_related('plan')
        .order_by('-created_at')
    )
    last_payment = payments.first()  # most recent payment for "طريقة الدفع" display

    return render(request, 'subscriptions/subscription_dashboard.html', {
        'subscription': sub,         # UserSubscription or None
        'payments':     payments,    # queryset of all PaymentRecords
        'last_payment': last_payment,
    })


@login_required(login_url='accounts:sign_in')
def payment_success_page(request):
    """
    GET /api/subscriptions/payment/success/
    Shown after Moyasar confirms a successful payment.
    The payments/views.py callback redirects here after activating the subscription.

    (added by ghadi: fetches the freshly-activated subscription and the most
     recent PAID PaymentRecord so the success page can display plan name,
     amount paid, renewal date, and reference number)
    """
    sub = get_user_subscription(request.user)

    # (added by ghadi: get the most recent paid record for the reference number display)
    payment = (
        PaymentRecord.objects
        .filter(user=request.user, status=PaymentRecord.Status.PAID)
        .order_by('-created_at')
        .first()
    )

    return render(request, 'subscriptions/payment_success.html', {
        'subscription': sub,      # freshly activated UserSubscription
        'payment':      payment,  # most recent PaymentRecord with status=PAID
    })


def payment_failed_page(request):
    """
    GET /api/subscriptions/payment/failed/
    Shown after a payment fails or is cancelled on Moyasar.
    The payments/views.py callback redirects here on failure.

    (added by ghadi: reads plan_id from query params so the 'Try again' button
     can link back to the correct checkout page)
    """
    # (added by ghadi: the callback passes ?plan_id=X so the retry button works)
    plan_id = request.GET.get('plan_id', '')

    return render(request, 'subscriptions/payment_failed.html', {
        'plan_id': plan_id,
    })
