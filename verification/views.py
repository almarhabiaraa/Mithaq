from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.core.exceptions import ValidationError
from django.utils.dateformat import DateFormat
from uuid import UUID

from contracts.models import Contract
from invitations.models import SigningInvitation


@require_GET
def verify_page(request: HttpRequest):
    return render(
        request,
        "verification/verify.html",
        {
            "api_url": reverse("verification:verify_contract_api")
        }
    )


@require_GET
def verify_contract_api(request: HttpRequest):
    contract_id = request.GET.get("contract_id", "").strip()

    try:
        UUID(contract_id)
    except (ValueError, TypeError):
        return JsonResponse(
            {"result": "INVALID_CONTRACT_ID"},
            status=400
        )

    contract = Contract.objects.filter(id=contract_id).first()

    if not contract:
        return JsonResponse(
            {"result": "NOT_FOUND"},
            status=404
        )

    invitations = SigningInvitation.objects.filter(contract=contract)

    total_parties = invitations.count()
    signed_parties = invitations.filter(
        status=SigningInvitation.Status.SIGNED
    ).count()

    all_signed = total_parties > 0 and signed_parties == total_parties

    if all_signed:
        result = "VALID_COMPLETED"
    else:
        result = "VALID_PENDING_SIGNATURES"

    return JsonResponse({
        "result": result,
        "contract": {
            "id": str(contract.id),
            "title": contract.title_ar or "عقد بدون عنوان",
            "status": contract.status,
            "status_display": contract.get_status_display(),
            "contract_type_display": contract.get_contract_type_display() if contract.contract_type else "غير محدد",
            "created_at": contract.created_at.strftime("%Y-%m-%d") if contract.created_at else "-",
            "updated_at": contract.updated_at.strftime("%Y-%m-%d %H:%M") if contract.updated_at else "-",
            "parties_count": total_parties,
            "signed_parties": signed_parties,
            "all_signed": all_signed,
        }
    })