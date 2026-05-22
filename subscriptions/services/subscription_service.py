# =============================================================================
# subscriptions/services/subscription_service.py
# OWNED BY: Ghadi
#
# PURPOSE:
#   All subscription business logic lives here.
#   Views and other apps call these functions — they never touch models directly.
#
# HOW IT CONNECTS TO OTHER APPS:
#
#   accounts/views.py → assign_free_plan(user)
#       Called right after User.objects.create_user() in sign_up().
#       Every new user automatically gets the Free plan (1 contract limit).
#
#   payments/services/moyasar_service.py → activate_subscription(user, plan)
#       Called inside handle_callback() after Moyasar confirms a payment.
#       Upgrades the user's plan and resets contracts_used to 0.
#
#   contracts/services/contract_workflow.py → check_contract_limit(user)  ✓ DONE
#       Called as the first line of ContractWorkflowService.create_contract()
#       before any DB write. Raises PermissionDenied if the user has no active
#       subscription or has reached their plan's contract limit.
#       ContractListCreateView catches PermissionDenied and returns HTTP 403.
#
# FUTURE WORK (Ghadi):
#   - Schedule expire_subscriptions to run nightly:
#       python manage.py expire_subscriptions
#       Add to server cron or Celery beat later in the project.
# =============================================================================

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from subscriptions.models import SubscriptionPlan, UserSubscription

logger = logging.getLogger(__name__)


# ── Called from: accounts/views.py → sign_up() ────────────────────────────────
def assign_free_plan(user) -> UserSubscription:
    """
    Assign the Free plan to a newly registered user.

    Creates an ACTIVE UserSubscription with no expiry date (duration_days=0
    means the Free plan never expires). Must be called immediately after
    user creation. Raises RuntimeError if the Free plan has not been seeded yet.
    """
    try:
        free_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.FREE)
    except SubscriptionPlan.DoesNotExist:
        raise RuntimeError(
            "Free plan not found. Run: python manage.py seed_plans"
        )

    return UserSubscription.objects.create( 
        user=user,
        plan=free_plan,
        status=UserSubscription.Status.ACTIVE,
        contracts_used=0,
        started_at=timezone.now(),
        expires_at=None,
    )


# ── Called from: everywhere that needs to know the user's current plan ─────────
def get_user_subscription(user) -> UserSubscription | None:
    """
    Return the active UserSubscription for the given user, or None.
    Eagerly loads the related plan to avoid extra queries.
    """
    return (
        UserSubscription.objects
        .select_related('plan')
        .filter(user=user, status=UserSubscription.Status.ACTIVE)
        .first()
    )


# ── Internal helper — prefer check_contract_limit() for user-facing enforcement ─
def increment_contracts_used(user) -> UserSubscription:
    """
    Atomically increment contracts_used on the user's active subscription.

    Uses SELECT FOR UPDATE to prevent a race condition where two concurrent
    requests both pass the can_create_contract() check before either saves.
    Raises ValueError if the user has no active subscription or has hit their
    plan's contract limit.
    """
    with transaction.atomic():
        try:
            sub = (
                UserSubscription.objects
                .select_for_update()
                .select_related('plan')
                .get(user=user, status=UserSubscription.Status.ACTIVE)
            )
        except UserSubscription.DoesNotExist:
            raise ValueError("المستخدم لا يملك اشتراكاً نشطاً")

        if not sub.can_create_contract():
            raise ValueError(
                "لقد وصلت إلى الحد الأقصى من العقود المسموح بها في باقتك الحالية"
            )

        sub.contracts_used += 1
        sub.save(update_fields=['contracts_used', 'updated_at'])
        return sub


# ── Called from: payments/services/moyasar_service.py → handle_callback() ──────
def activate_subscription(user, plan: SubscriptionPlan) -> UserSubscription:
    """
    Activate or upgrade a user's subscription after a successful payment.

    If the user already has a UserSubscription it is updated in place; otherwise
    a new one is created. contracts_used is reset to 0 on every activation.
    expires_at is computed from plan.duration_days (None when duration_days == 0,
    meaning the plan never expires — e.g. the Free plan).

    Uses SELECT FOR UPDATE to prevent concurrent activations for the same user.
    Returns the saved UserSubscription.
    """
    with transaction.atomic():
        try:
            sub = UserSubscription.objects.select_for_update().get(user=user)
            sub.plan = plan
            sub.status = UserSubscription.Status.ACTIVE
            sub.contracts_used = 0
            sub.started_at = timezone.now()
            sub.expires_at = (
                timezone.now() + timedelta(days=plan.duration_days)
                if plan.duration_days > 0
                else None
            )
            sub.save()
        except UserSubscription.DoesNotExist:
            sub = UserSubscription.objects.create(
                user=user,
                plan=plan,
                status=UserSubscription.Status.ACTIVE,
                contracts_used=0,
                started_at=timezone.now(),
                expires_at=(
                    timezone.now() + timedelta(days=plan.duration_days)
                    if plan.duration_days > 0
                    else None
                ),
            )
    return sub


# ── Called from: contracts/services/contract_workflow.py → create_contract() ───
def check_contract_limit(user) -> UserSubscription:
    """
    Enforce contract creation limits before allowing a new contract.

    Unlike increment_contracts_used (which raises ValueError), this function
    raises PermissionDenied so views can return HTTP 403 directly to the user.

    Checks subscription existence and status first (without a lock), then
    acquires SELECT FOR UPDATE before incrementing contracts_used to prevent
    a race condition under concurrent requests.

    Returns the updated UserSubscription on success.
    """
    from django.core.exceptions import PermissionDenied

    try:
        sub = UserSubscription.objects.select_related('plan').get(user=user)
    except UserSubscription.DoesNotExist:
        raise PermissionDenied("لا يوجد اشتراك نشط. يرجى اختيار خطة.")

    if sub.status == UserSubscription.Status.EXPIRED:
        raise PermissionDenied("انتهت صلاحية اشتراكك. يرجى التجديد.")

    with transaction.atomic():
        sub = (
            UserSubscription.objects
            .select_for_update()
            .select_related('plan')
            .get(user=user)
        )

        if sub.status != UserSubscription.Status.ACTIVE:
            raise PermissionDenied("لا يوجد اشتراك نشط. يرجى اختيار خطة.")

        if not sub.can_create_contract():
            raise PermissionDenied("لقد استنفدت عدد العقود المسموح به في خطتك الحالية.")

        sub.contracts_used += 1
        sub.save(update_fields=['contracts_used', 'updated_at'])

    return sub


# ── Run via: python manage.py expire_subscriptions (nightly cron later) ────────
def check_and_expire_subscriptions() -> int:
    """
    Expire all active subscriptions whose expires_at timestamp has passed,
    and send a 3-day warning notification to subscriptions expiring soon.

    Returns the count of subscriptions that were expired.
    """
    from notifications.services import NotificationService
    from notifications.models import Notification

    now = timezone.now()

    # ── Expire overdue subscriptions ──────────────────────────────────────────
    due = UserSubscription.objects.filter(
        status=UserSubscription.Status.ACTIVE,
        expires_at__isnull=False,
        expires_at__lte=now,
    ).select_related('user', 'plan')

    count = 0
    for sub in due:
        sub.status = UserSubscription.Status.EXPIRED
        sub.save(update_fields=['status', 'updated_at'])
        NotificationService.notify(
            user=sub.user,
            notification_type=Notification.SUBSCRIPTION_EXPIRED,
        )
        count += 1

    # ── Warn users whose subscription expires within 3 days ───────────────────
    three_days_from_now = now + timedelta(days=3)
    expiring_soon = UserSubscription.objects.filter(
        status=UserSubscription.Status.ACTIVE,
        expires_at__isnull=False,
        expires_at__gt=now,
        expires_at__lte=three_days_from_now,
    ).select_related('user')

    # Avoid re-sending the warning if one was already sent in the last 24 hours
    already_warned_ids = set(
        Notification.objects.filter(
            notification_type=Notification.SUBSCRIPTION_EXPIRING,
            created_at__gte=now - timedelta(days=1),
        ).values_list('user_id', flat=True)
    )

    for sub in expiring_soon:
        if sub.user_id not in already_warned_ids:
            NotificationService.notify(
                user=sub.user,
                notification_type=Notification.SUBSCRIPTION_EXPIRING,
            )

    return count


# ── Available for future use (e.g. admin-initiated plan change) ────────────────
def upgrade_subscription(user, new_plan: SubscriptionPlan) -> UserSubscription:
    """
    Switch the user's subscription to a new plan.

    Resets contracts_used to 0, updates started_at/expires_at based on the
    new plan's duration_days, and marks the subscription ACTIVE. Uses
    SELECT FOR UPDATE to prevent concurrent upgrades on the same user.
    """
    with transaction.atomic():
        sub = UserSubscription.objects.select_for_update().get(user=user)
        sub.plan = new_plan
        sub.status = UserSubscription.Status.ACTIVE
        sub.contracts_used = 0
        sub.started_at = timezone.now()
        sub.expires_at = (
            timezone.now() + timedelta(days=new_plan.duration_days)
            if new_plan.duration_days > 0
            else None
        )
        sub.save()
        return sub
