from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.db.models import Q
from django.utils import timezone

from dashboard.models import DashboardSubscription
from contracts.models import Contract


STATUS_MAP = {
    'draft':             Contract.Status.DRAFT,
    'pending_signature': Contract.Status.PENDING_SIGNATURES,
    'signed':            Contract.Status.SIGNED,
    'completed':         Contract.Status.COMPLETED,
    'cancelled':         Contract.Status.CANCELLED,
}


def dashboard_view(request: HttpRequest):
    status_filter    = request.GET.get('status', '')
    type_filter      = request.GET.get('type', '')
    date_filter      = request.GET.get('date', 'newest')
    contracts              = Contract.objects.none()
    total_contracts        = 0
    completed_contracts    = 0
    active_contracts       = 0
    pending_signatures     = 0
    draft_contracts        = 0
    completed_this_month   = 0
    avg_completion         = 0
    current_subscription   = None

    if request.user.is_authenticated:
        current_subscription = (
            DashboardSubscription.objects
            .filter(user=request.user, is_active=True)
            .first()
        )

        # All contracts where this user is creator or party
        base_qs = Contract.objects.filter(
            Q(creator=request.user) | Q(parties__user=request.user)
        ).distinct()

        # Stats computed on the unfiltered set
        total_contracts     = base_qs.count()
        completed_contracts = base_qs.filter(status=Contract.Status.COMPLETED).count()
        pending_signatures  = base_qs.filter(status=Contract.Status.PENDING_SIGNATURES).count()
        active_contracts    = pending_signatures
        draft_contracts     = base_qs.filter(status=Contract.Status.DRAFT).count()
        signed_contracts    = base_qs.filter(status=Contract.Status.SIGNED).count()

        now = timezone.now()
        completed_this_month = base_qs.filter(
            status=Contract.Status.COMPLETED,
            completed_at__year=now.year,
            completed_at__month=now.month,
        ).count()

        if total_contracts:
            progress_sum = (
                draft_contracts     * 25 +
                pending_signatures  * 50 +
                signed_contracts    * 75 +
                completed_contracts * 100
            )
            avg_completion = round(progress_sum / total_contracts)

        # Apply filters
        qs = base_qs

        if status_filter and status_filter in STATUS_MAP:
            qs = qs.filter(status=STATUS_MAP[status_filter])

        if type_filter == 'created':
            qs = qs.filter(creator=request.user)
        elif type_filter == 'received':
            qs = qs.exclude(creator=request.user)

        qs = qs.order_by('created_at' if date_filter == 'oldest' else '-created_at')

        contracts = qs.select_related('creator')

    context = {
        'contracts':            contracts,
        'total_contracts':      total_contracts,
        'completed_contracts':  completed_contracts,
        'active_contracts':     active_contracts,
        'pending_signatures':   pending_signatures,
        'rejected_contracts':   0,
        'draft_contracts':      draft_contracts,
        'pending_approvals':    0,
        'received_invitations': 0,
        'under_review_contracts': 0,
        'completed_this_month': completed_this_month,
        'avg_completion':       avg_completion,
        'current_subscription': current_subscription,
        'selected_status':      status_filter,
        'selected_type':        type_filter,
        'selected_date':        date_filter,
    }

    return render(request, 'dashboard/dashboard.html', context)
