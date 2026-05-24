from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from contracts.models import Contract
from invitations.models import SigningInvitation

User = get_user_model()


def home(request: HttpRequest):
    return render(request, 'home.html')


@login_required
def search_view(request: HttpRequest):
    q = request.GET.get('q', '').strip()

    if not q:
        return render(request, 'core/search_results.html', {
            'q': '', 'contracts': [], 'users': [], 'invitations': [], 'total': 0,
        })

    # Contracts by title or UUID, scoped to what the user can see
    contract_filter = Q(title_ar__icontains=q) | Q(title_en__icontains=q)
    try:
        contract_filter |= Q(id=UUID(q))
    except (ValueError, AttributeError):
        pass

    contracts = list(
        Contract.objects.filter(contract_filter)
        .filter(Q(creator=request.user) | Q(signing_invitations__invitee_user=request.user))
        .distinct()
    )

    # Invitations by reference number (received only — reference number is how invitees identify theirs)
    invitations = list(
        SigningInvitation.objects.filter(reference_number__icontains=q, invitee_user=request.user)
        .select_related('contract')
    )

    # Users by name or email (exclude self)
    users = list(
        User.objects.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
        ).exclude(pk=request.user.pk)
    )

    total = len(contracts) + len(invitations) + len(users)

    # Direct redirect when exactly one result is a contract or invitation
    if total == 1:
        if contracts:
            return redirect('contracts:contract_detail', pk=contracts[0].pk)
        if invitations:
            return redirect('invitations:invitation_contract_detail', invitation_id=invitations[0].pk)

    return render(request, 'core/search_results.html', {
        'q': q,
        'contracts': contracts,
        'users': users,
        'invitations': invitations,
        'total': total,
    })

