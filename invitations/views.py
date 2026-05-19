import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from contracts.models import Contract
from .models import SigningInvitation
from .services import SigningInvitationService
import hashlib
from django.utils import timezone
from django.views.decorators.http import require_POST

from signatures.models import Signature


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
            messages.error(request, "يجب إضافة طرف واحد على الأقل قبل المتابعة")
            return redirect("invitations:create_signing_invitation", contract_id=contract.id)

        invitation_secrets = {}
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
                messages.error(request, "اسم الطرف ورقم الجوال مطلوبان لكل طرف")
                return redirect("invitations:create_signing_invitation", contract_id=contract.id)

            if not signer_email:
                messages.error(request, "البريد الإلكتروني مطلوب لإرسال طلب التوقيع")
                return redirect("invitations:create_signing_invitation", contract_id=contract.id)

            if SigningInvitation.objects.filter(
                contract=contract,
                signer_mobile=signer_mobile
            ).exists():
                messages.error(request, f"رقم الجوال {signer_mobile} مضاف مسبقًا لهذا العقد")
                return redirect("invitations:create_signing_invitation", contract_id=contract.id)

            if party_type == SigningInvitation.PartyType.INDIVIDUAL and not signer_national_id:
                messages.error(request, "رقم الهوية مطلوب إذا كان الطرف فردًا")
                return redirect("invitations:create_signing_invitation", contract_id=contract.id)

            if party_type == SigningInvitation.PartyType.ORGANIZATION:
                if not organization_name or not commercial_registration:
                    messages.error(request, "اسم المنشأة ورقم السجل التجاري مطلوبان إذا كان الطرف منشأة")
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

            invitation_secrets[str(invitation.id)] = secret
            last_invitation = invitation

        request.session["invitation_secrets"] = invitation_secrets

        messages.success(request, "تم حفظ أطراف العقد بنجاح")
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
        sent_count = 0
        failed_count = 0
        missing_secret_count = 0

        invitation_secrets = request.session.get("invitation_secrets", {})

        for item in unique_invitations:
            if item.status in [
                SigningInvitation.Status.PENDING,
                SigningInvitation.Status.FAILED,
            ]:
                secret = invitation_secrets.get(str(item.id))

                if not secret:
                    item.mark_as_failed("رابط الدعوة غير متوفر. يرجى إعادة إنشاء الدعوة")
                    missing_secret_count += 1
                    failed_count += 1
                    continue

                SigningInvitationService.send_existing_invitation(item, secret)
                item.refresh_from_db()

                if item.status == SigningInvitation.Status.SENT:
                    sent_count += 1
                elif item.status == SigningInvitation.Status.FAILED:
                    failed_count += 1

        if sent_count and not failed_count:
            messages.success(request, "تم إرسال طلبات التوقيع عبر البريد الإلكتروني بنجاح")
        elif sent_count and failed_count:
            messages.warning(
                request,
                f"تم إرسال {sent_count} دعوة، وتعذر إرسال {failed_count} دعوة"
            )
        elif missing_secret_count:
            messages.error(
                request,
                "رابط الدعوة غير متوفر لهذه الدعوات. احذفي الدعوات القديمة أو أعيدي إنشاء أطراف العقد ثم أرسليها من جديد"
            )
        else:
            messages.error(
                request,
                "تعذر إرسال طلبات التوقيع. تأكدي من البريد الإلكتروني أو أعيدي إنشاء الدعوة"
            )

        return redirect(
            "invitations:review_signing_invitation",
            invitation_id=invitation.id
        )

    return render(request, "invitations/review_signing_invitation.html", {
        "invitation": invitation,
        "invitations": unique_invitations,
        "contract": contract,
    })


@login_required
def access_invitation(request, secret):
    secret_hash = SigningInvitation.hash_secret(secret)

    invitation = get_object_or_404(
        SigningInvitation,
        secret_hash=secret_hash
    )

    if invitation.is_expired:
        invitation.status = SigningInvitation.Status.EXPIRED
        invitation.save(update_fields=["status", "updated_at"])
        messages.error(request, "انتهت صلاحية رابط الدعوة")
        return redirect("home")

    if invitation.status == SigningInvitation.Status.CANCELLED:
        messages.error(request, "تم إلغاء هذه الدعوة")
        return redirect("home")

    if invitation.invitee_user and invitation.invitee_user != request.user:
        messages.error(request, "هذه الدعوة مرتبطة بحساب آخر")
        return redirect("home")

    if invitation.signer_email and request.user.email:
        if invitation.signer_email.lower() != request.user.email.lower():
            messages.error(request, "يجب الدخول بنفس البريد الإلكتروني المرسل له طلب التوقيع")
            return redirect("home")

    if not invitation.invitee_user:
        invitation.link_to_user(request.user)

    if invitation.status == SigningInvitation.Status.SENT:
        invitation.mark_as_viewed()

    return redirect("invitations:my_contracts")


@login_required
def my_contracts(request):
    sent_invitations = SigningInvitation.objects.filter(
        invited_by=request.user
    ).select_related("contract", "invitee_user", "invited_by")

    received_invitations = SigningInvitation.objects.filter(
        invitee_user=request.user
    ).select_related("contract", "invitee_user", "invited_by")

    direction = request.GET.get("direction", "all")
    status_filter = request.GET.get("status", "")

    if direction == "sent":
        invitations = sent_invitations
    elif direction == "received":
        invitations = received_invitations
    else:
        invitations = sent_invitations | received_invitations

    if status_filter:
        invitations = invitations.filter(status=status_filter)

    invitations = invitations.order_by("-created_at")
    all_invitations = sent_invitations | received_invitations

    stats = {
        "total": all_invitations.count(),
        "sent": sent_invitations.count(),
        "received": received_invitations.count(),
        "pending": all_invitations.filter(status__in=[
            SigningInvitation.Status.PENDING,
            SigningInvitation.Status.SENT,
            SigningInvitation.Status.VIEWED,
        ]).count(),
        "signed": all_invitations.filter(status=SigningInvitation.Status.SIGNED).count(),
        "rejected": all_invitations.filter(status=SigningInvitation.Status.REJECTED).count(),
    }

    paginator = Paginator(invitations, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "invitations/my_contracts.html", {
        "page_obj": page_obj,
        "invitations": page_obj.object_list,
        "direction": direction,
        "status_filter": status_filter,
        "statuses": SigningInvitation.Status.choices,
        "stats": stats,
    })


@login_required
def invitation_contract_detail(request, invitation_id):
    invitation = get_object_or_404(
        SigningInvitation.objects.select_related(
            "contract",
            "contract__creator",
            "invited_by",
            "invitee_user",
        ),
        id=invitation_id,
    )

    contract = invitation.contract

    is_owner = contract.creator == request.user
    is_invited_user = invitation.invitee_user == request.user

    if not is_owner and not is_invited_user:
        messages.error(request, "ليس لديك صلاحية للوصول إلى هذا العقد")
        return redirect("invitations:my_contracts")

    contract_invitations = SigningInvitation.objects.filter(
        contract=contract
    ).select_related(
        "invited_by",
        "invitee_user",
    ).order_by("signing_order", "created_at")

    total_parties = contract_invitations.count()

    signed_parties = contract_invitations.filter(
        status=SigningInvitation.Status.SIGNED
    ).count()

    failed_parties = contract_invitations.filter(
        status=SigningInvitation.Status.FAILED
    ).count()

    sent_parties = contract_invitations.filter(
        status__in=[
            SigningInvitation.Status.SENT,
            SigningInvitation.Status.VIEWED,
            SigningInvitation.Status.SIGNED,
        ]
    ).count()

    progress_percentage = int((signed_parties / total_parties) * 100) if total_parties else 0

    if total_parties and signed_parties == total_parties:
        display_contract_status = "مكتمل"
        display_contract_status_class = "signed"
    elif total_parties and failed_parties == total_parties:
        display_contract_status = "فشل الإرسال"
        display_contract_status_class = "failed"
    elif failed_parties and sent_parties:
        display_contract_status = "أرسل جزئيًا"
        display_contract_status_class = "partial"
    elif sent_parties:
        display_contract_status = "قيد المتابعة"
        display_contract_status_class = "sent"
    else:
        display_contract_status = invitation.get_status_display()
        display_contract_status_class = invitation.status.lower()

    permissions = {
        "can_view_contract": True if is_owner else invitation.can_view_contract,
        "can_comment": False if is_owner else invitation.can_comment,
        "can_edit": False if is_owner else invitation.can_edit,
        "can_upload_files": False,
        "can_sign": False if is_owner else invitation.can_sign,
        "can_manage": is_owner,
    }

    role_label = "منشئ العقد" if is_owner else invitation.get_contract_role_display()
    direction_label = "صادر" if is_owner else "وارد"

    can_create_new_version = False
    contract_versions = []

    return render(request, "invitations/invitation_contract_detail.html", {
        "contract": contract,
        "invitation": invitation,
        "contract_invitations": contract_invitations,
        "permissions": permissions,
        "is_owner": is_owner,
        "is_invited_user": is_invited_user,
        "role_label": role_label,
        "direction_label": direction_label,
        "total_parties": total_parties,
        "signed_parties": signed_parties,
        "progress_percentage": progress_percentage,
        "display_contract_status": display_contract_status,
        "display_contract_status_class": display_contract_status_class,
        "can_create_new_version": can_create_new_version,
        "contract_versions": contract_versions,
    })

@login_required
@require_POST
def reject_invitation_contract(request, invitation_id):
    invitation = get_object_or_404(
        SigningInvitation,
        id=invitation_id,
        invitee_user=request.user
    )

    if invitation.status in [
        SigningInvitation.Status.SIGNED,
        SigningInvitation.Status.REJECTED,
        SigningInvitation.Status.CANCELLED,
        SigningInvitation.Status.EXPIRED,
    ]:
        messages.warning(request, "لا يمكن رفض هذا العقد في حالته الحالية")
        return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)

    invitation.mark_as_rejected()

    messages.success(request, "تم رفض العقد بنجاح")
    return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)


def _get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")

@login_required
@require_POST
def sign_invitation_contract(request, invitation_id):
    invitation = get_object_or_404(
        SigningInvitation.objects.select_related(
            "contract",
            "invitee_user",
        ),
        id=invitation_id,
        invitee_user=request.user
    )

    contract = invitation.contract

    if not invitation.can_sign:
        messages.error(request, "لا تملك صلاحية التوقيع على هذا العقد")
        return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)

    if invitation.status == SigningInvitation.Status.SIGNED:
        messages.warning(request, "تم توقيع هذا العقد مسبقًا")
        return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)

    if invitation.status in [
        SigningInvitation.Status.REJECTED,
        SigningInvitation.Status.CANCELLED,
        SigningInvitation.Status.EXPIRED,
    ]:
        messages.error(request, "لا يمكن توقيع هذا العقد في حالته الحالية")
        return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)

    typed_name = request.POST.get("typed_name", "").strip()
    confirm_acceptance = request.POST.get("confirm_acceptance")

    expected_name = invitation.signer_full_name.strip()

    if not typed_name:
        messages.error(request, "يرجى كتابة الاسم الكامل لإتمام التوقيع")
        return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)

    if typed_name.lower() != expected_name.lower():
        messages.error(request, "الاسم المدخل لا يطابق اسم الطرف المسجل في الدعوة")
        return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)

    if confirm_acceptance != "on":
        messages.error(request, "يجب تأكيد الموافقة على محتوى العقد قبل التوقيع")
        return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)

    contract_version = getattr(contract, "current_version", None)

    if not contract_version and hasattr(contract, "versions"):
        contract_version = contract.versions.order_by("-created_at").first()

    if not contract_version:
        messages.error(request, "لا توجد نسخة عقد مرتبطة لإتمام التوقيع")
        return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)

    if Signature.objects.filter(contract=contract, signer=request.user).exists():
        invitation.mark_as_signed()
        messages.warning(request, "تم توقيع هذا العقد مسبقًا")
        return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)

    raw_signature = (
        f"{contract.id}|"
        f"{contract_version.id}|"
        f"{request.user.id}|"
        f"{typed_name}|"
        f"{timezone.now().isoformat()}|"
        f"{invitation.reference_number}"
    )

    signed_hash = hashlib.sha256(raw_signature.encode("utf-8")).hexdigest()

    Signature.objects.create(
        contract=contract,
        contract_version=contract_version,
        signer=request.user,
        signed_hash=signed_hash,
        ip_address=_get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    invitation.mark_as_signed()

    messages.success(request, "تم توقيع العقد وحفظ بيانات التوقيع بنجاح")
    return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)