import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from contracts.models import Contract
from .models import SigningInvitation
from .services import SigningInvitationService


def _as_bool(value):
    return value in [True, "true", "True", "1", 1, "on"]


@login_required
def create_signing_invitation(request, contract_id):
    contract = get_object_or_404(
        Contract,
        id=contract_id,
        creator=request.user
    )

    if request.method == "POST":
        parties_payload = request.POST.get("parties_payload", "[]")

        try:
            parties = json.loads(parties_payload)
        except json.JSONDecodeError:
            parties = []

        if not parties:
            messages.error(request, "يجب إضافة طرف واحد على الأقل قبل المتابعة.")
            return redirect("invitations:create_signing_invitation", contract_id=contract.id)

        last_invitation = None

        for index, party in enumerate(parties, start=1):
            signer_full_name = party.get("full_name", "").strip()
            signer_mobile = party.get("mobile", "").strip()
            signer_email = party.get("email", "").strip()

            party_type = party.get("party_type", SigningInvitation.PartyType.INDIVIDUAL)
            contract_role = party.get("contract_role", SigningInvitation.ContractRole.SECOND_PARTY)
            signing_role = party.get("signing_role", SigningInvitation.SigningRole.SIGNER)

            signer_national_id = party.get("national_id", "").strip()
            signer_nationality = party.get("nationality", "").strip()

            organization_name = party.get("organization_name", "").strip()
            commercial_registration = party.get("commercial_registration", "").strip()
            tax_number = party.get("tax_number", "").strip()

            invitation_message = party.get("invitation_message", "").strip()

            if not signer_full_name or not signer_mobile:
                messages.error(request, "اسم الطرف ورقم الجوال مطلوبان لكل طرف.")
                return redirect("invitations:create_signing_invitation", contract_id=contract.id)

            if SigningInvitation.objects.filter(
                contract=contract,
                signer_mobile=signer_mobile
            ).exists():
                messages.error(request, f"رقم الجوال {signer_mobile} مضاف مسبقًا لهذا العقد.")
                return redirect("invitations:create_signing_invitation", contract_id=contract.id)

            if party_type == SigningInvitation.PartyType.INDIVIDUAL and not signer_national_id:
                messages.error(request, "رقم الهوية مطلوب إذا كان الطرف فردًا.")
                return redirect("invitations:create_signing_invitation", contract_id=contract.id)

            if party_type == SigningInvitation.PartyType.ORGANIZATION:
                if not organization_name or not commercial_registration:
                    messages.error(request, "اسم المنشأة ورقم السجل التجاري مطلوبان إذا كان الطرف منشأة.")
                    return redirect("invitations:create_signing_invitation", contract_id=contract.id)

            invitation, secret = SigningInvitation.create_invitation(
                contract=contract,
                invited_by=request.user,
                signer_full_name=signer_full_name,
                signer_mobile=signer_mobile,
                signer_email=signer_email,
                party_type=party_type,
                contract_role=contract_role,
                signing_role=signing_role,
                signer_national_id=signer_national_id,
                signer_nationality=signer_nationality,
                organization_name=organization_name,
                commercial_registration=commercial_registration,
                tax_number=tax_number,
                can_view_contract=_as_bool(party.get("can_view_contract", True)),
                can_comment=_as_bool(party.get("can_comment", False)),
                can_edit=_as_bool(party.get("can_edit", False)),
                can_upload_files=_as_bool(party.get("can_upload_files", False)),
                can_sign=_as_bool(party.get("can_sign", True)),
                signing_order=int(party.get("signing_order") or index),
                invitation_message=invitation_message,
            )

            last_invitation = invitation

        messages.success(request, "تم حفظ أطراف العقد بنجاح.")
        return redirect(
            "invitations:review_signing_invitation",
            invitation_id=last_invitation.id
        )

    return render(request, "invitations/create_signing_invitation.html", {
        "contract": contract,
        "party_types": SigningInvitation.PartyType.choices,
        "contract_roles": SigningInvitation.ContractRole.choices,
        "signing_roles": SigningInvitation.SigningRole.choices,
    })


@login_required
def review_signing_invitation(request, invitation_id):
    invitation = get_object_or_404(
        SigningInvitation,
        id=invitation_id,
        invited_by=request.user
    )

    contract = invitation.contract

    invitations_queryset = SigningInvitation.objects.filter(
        contract=contract,
        invited_by=request.user
    ).order_by("signing_order", "created_at")

    unique_invitations = []
    seen_mobiles = set()

    for item in invitations_queryset:
        if item.signer_mobile not in seen_mobiles:
            unique_invitations.append(item)
            seen_mobiles.add(item.signer_mobile)

    if request.method == "POST":
        for item in unique_invitations:
            if item.status in [
                SigningInvitation.Status.PENDING,
                SigningInvitation.Status.FAILED,
            ]:
                SigningInvitationService.send_existing_invitation(item)

        messages.success(request, "تم إرسال طلبات التوقيع عبر SMS بنجاح.")
        return redirect("contracts:contract_detail", pk=contract.id)

    return render(request, "invitations/review_signing_invitation.html", {
        "invitation": invitation,
        "invitations": unique_invitations,
        "contract": contract,
    })