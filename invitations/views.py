import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render, redirect
from django.views.decorators.http import require_POST
from contracts.models import Contract, ContractVersion, ContractModificationRequest, ContractClause
from .models import SigningInvitation
from .services import SigningInvitationService
import hashlib
from django.utils import timezone
from signatures.models import Signature





def _as_bool(value):
    return value in [True, "true", "True", "1", 1, "on"]

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
    selected_version_id = request.GET.get("version")
    contract_versions = contract.versions.all().order_by("version_number")

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

    selected_version = None
    version_data = {}
    display_description = contract.description_ar
    display_content = ""
    base_clauses = []
    pending_modification = None
    approved_modification = None
    rejected_modification = None
    selected_version_pending_modification = None
    selected_version_rejected_modification = None
    selected_version_superseded_modification = None
    superseded_modification = None
    pending_requested_by_me = False
    pending_waiting_for_me = False
    selected_version_pending_requested_by_me = False
    selected_version_pending_waiting_for_me = False



    if selected_version_id:
        selected_version = get_object_or_404(
            ContractVersion,
            id=selected_version_id,
            contract=contract
        )


    elif contract.current_version:
        selected_version = contract.current_version

    else:
        selected_version = contract_versions.last()

    if selected_version:
        version_data = selected_version.canonical_json or {}

        selected_version_pending_modification = ContractModificationRequest.objects.filter(
            contract=contract,
            proposed_version=selected_version,
            status=ContractModificationRequest.Status.PENDING
        ).first()

        if selected_version_pending_modification:
            selected_version_pending_requested_by_me = (
                selected_version_pending_modification.requested_by_id == request.user.id
            )

            selected_version_pending_waiting_for_me = (
                selected_version_pending_modification.requested_by_id != request.user.id
            )

        selected_version_rejected_modification = ContractModificationRequest.objects.filter(
            contract=contract,
            proposed_version=selected_version,
            status=ContractModificationRequest.Status.REJECTED
        ).first()

        selected_version_superseded_modification = ContractModificationRequest.objects.filter(
        contract=contract,
        proposed_version=selected_version,
        status=ContractModificationRequest.Status.SUPERSEDED
        ).first()

        display_description = (
            version_data.get("description_ar")
            or contract.description_ar
            or ""
        )

        display_content = (
            version_data.get("content_ar")
            or ""
        )

        base_clauses = ContractClause.objects.filter(
            version=selected_version
        ).order_by("order_index")

        pending_modification = ContractModificationRequest.objects.filter(
            contract=contract,
            status=ContractModificationRequest.Status.PENDING
        ).select_related("proposed_version").first()
        if pending_modification:
            pending_requested_by_me = pending_modification.requested_by_id == request.user.id
            pending_waiting_for_me = pending_modification.requested_by_id != request.user.id

        approved_modification = ContractModificationRequest.objects.filter(
            contract=contract,
            status=ContractModificationRequest.Status.APPROVED
        ).select_related("proposed_version").first()

        rejected_modification = ContractModificationRequest.objects.filter(
            contract=contract,
            status=ContractModificationRequest.Status.REJECTED
        ).select_related("proposed_version").first()

        superseded_modification = ContractModificationRequest.objects.filter(
            contract=contract,
            status=ContractModificationRequest.Status.SUPERSEDED
        ).select_related("proposed_version").first()


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
    print("CAN EDIT:", invitation.can_edit)

    role_label = "منشئ العقد" if is_owner else invitation.get_contract_role_display()
    direction_label = "صادر" if is_owner else "وارد"

    can_create_new_version = True

    if is_owner:
        template_name = "invitations/sent_contract_detail.html"
    else:
        template_name = "invitations/received_contract_detail.html"

    return render(request, template_name, {
        "invitation": invitation,
        "contract": contract,
        "contract_invitations": contract_invitations,
        "is_owner": is_owner,
        "permissions": permissions,
        "role_label": role_label,
        "direction_label": direction_label,
        "progress_percentage": progress_percentage,
        "signed_parties": signed_parties,
        "total_parties": total_parties,
        "display_contract_status": display_contract_status,
        "display_contract_status_class": display_contract_status_class,
        "can_create_new_version": can_create_new_version,
        "contract_versions": contract_versions,
        "has_pending_modification": False,
        "contract_versions": contract_versions,
        "selected_version": selected_version,
        "version_data": version_data,
        "pending_modification": pending_modification,
        "has_pending_modification": pending_modification is not None,
        "pending_requested_by_me": pending_requested_by_me,
        "pending_waiting_for_me": pending_waiting_for_me,
        "selected_version_pending_requested_by_me": selected_version_pending_requested_by_me,
        "selected_version_pending_waiting_for_me": selected_version_pending_waiting_for_me,
        "contract_versions": contract_versions,
        "selected_version": selected_version,
        "version_data": version_data,
        "display_description": display_description,
        "display_content": display_content,
        "approved_modification": approved_modification,
        "rejected_modification": rejected_modification,
        "base_clauses": base_clauses,
        "selected_version_pending_modification": selected_version_pending_modification,
        "selected_version_rejected_modification": selected_version_rejected_modification,
        "superseded_modification": superseded_modification,
        "selected_version_superseded_modification": selected_version_superseded_modification,
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
    print("TYPED:", typed_name)
    print("EXPECTED:", expected_name)

    if not typed_name:
        messages.error(request, "يرجى كتابة الاسم الكامل لإتمام التوقيع")
        return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)

    if typed_name != expected_name:
        print("NAME MISMATCH")
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


@login_required
@require_POST
def cancel_contract(request, invitation_id):
    invitation = get_object_or_404(
        SigningInvitation,
        id=invitation_id,
        invited_by=request.user
    )

    contract = invitation.contract

    contract.status = "CANCELLED"
    contract.save(update_fields=["status", "updated_at"])

    SigningInvitation.objects.filter(contract=contract).update(
        status=SigningInvitation.Status.CANCELLED,
        failure_reason="تم إلغاء العقد من قبل المنشئ"
    )

    messages.success(
        request,
        "تم إلغاء العقد بنجاح، وسيظهر للطرف الآخر أن العقد ملغي"
    )

    return redirect(
        "invitations:invitation_contract_detail",
        invitation_id=invitation.id
    )
@login_required
@require_POST
def submit_contract_modification(request, contract_id):
    contract = get_object_or_404(Contract, id=contract_id)

    is_owner = contract.creator == request.user

    invitation = SigningInvitation.objects.filter(
        contract=contract,
        invitee_user=request.user
    ).first()

    if not is_owner:
        if not invitation:
            messages.error(request, "ليس لديك صلاحية على هذا العقد")
            return redirect("invitations:my_contracts")

        if not invitation.can_edit:
            messages.error(request, "لا تملك صلاحية طلب تعديل على هذا العقد")
            return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)

        redirect_invitation = invitation
    else:
        redirect_invitation = contract.signing_invitations.first()
    ContractModificationRequest.objects.filter(
        contract=contract,
        status=ContractModificationRequest.Status.PENDING
    ).update(
        status=ContractModificationRequest.Status.SUPERSEDED,
        reviewed_at=timezone.now()
    )

    title_ar = request.POST.get("title_ar", "").strip()
    description_ar = request.POST.get("description_ar", "").strip()
    content_ar = request.POST.get("content_ar", "").strip()
    modification_type = request.POST.get("modification_type", "").strip()
    modification_note = request.POST.get("modification_note", "").strip()

    if not title_ar or not content_ar or not modification_type:
        messages.error(request, "يرجى تعبئة بيانات التعديل المطلوبة.")
        return redirect("invitations:invitation_contract_detail", invitation_id=redirect_invitation.id)

    last_version_number = contract.versions.count() + 1

    proposed_version = ContractVersion.objects.create(
        contract=contract,
        version_number=last_version_number,
        created_by=request.user,
        canonical_json={
            "title_ar": title_ar,
            "description_ar": description_ar,
            "content_ar": content_ar,
            "modification_type": modification_type,
        },
        change_summary=modification_note,
    )

    ContractModificationRequest.objects.create(
        contract=contract,
        proposed_version=proposed_version,
        requested_by=request.user,
        reason=modification_note,
    )

    messages.success(request, "تم إرسال طلب التعديل للطرف الآخر بنجاح.")

    return redirect("invitations:invitation_contract_detail", invitation_id=redirect_invitation.id)

@login_required
@require_POST
def add_contract_invitation(request, contract_id):
    contract = get_object_or_404(
        Contract,
        id=contract_id,
        creator=request.user
    )

    redirect_invitation = contract.signing_invitations.first()

    if not redirect_invitation:
        messages.error(request, "لا يمكن إضافة دعوة لأن العقد لا يحتوي على دعوات أساسية.")
        return redirect("invitations:my_contracts")

    signer_full_name = request.POST.get("full_name", "").strip()

    signer_mobile = request.POST.get("mobile", "").strip()

    signer_email = request.POST.get("email", "").strip().lower()

    signer_national_id = request.POST.get("national_id", "").strip()

    if not signer_full_name:
        messages.error(request, "الاسم الكامل مطلوب.")
        return redirect(
            "invitations:invitation_contract_detail",
            invitation_id=redirect_invitation.id
        )

    clean_mobile = signer_mobile.replace(" ", "").replace("-", "")

    if not clean_mobile:
        messages.error(request, "رقم الجوال مطلوب.")
        return redirect(
            "invitations:invitation_contract_detail",
            invitation_id=redirect_invitation.id
        )

    if not clean_mobile.startswith("+"):
        messages.error(request, "رقم الجوال يجب أن يبدأ برمز الدولة مثل +966.")
        return redirect(
            "invitations:invitation_contract_detail",
            invitation_id=redirect_invitation.id
        )

    if not clean_mobile[1:].isdigit() or len(clean_mobile) < 10 or len(clean_mobile) > 15:
        messages.error(request, "رقم الجوال غير صالح.")
        return redirect(
            "invitations:invitation_contract_detail",
            invitation_id=redirect_invitation.id
        )

    if not signer_email:
        messages.error(request, "البريد الإلكتروني مطلوب.")
        return redirect(
            "invitations:invitation_contract_detail",
            invitation_id=redirect_invitation.id
        )

    if "@" not in signer_email or "." not in signer_email:
        messages.error(request, "البريد الإلكتروني غير صالح.")
        return redirect(
            "invitations:invitation_contract_detail",
            invitation_id=redirect_invitation.id
        )

    if signer_national_id:
        if not signer_national_id.isdigit() or len(signer_national_id) != 10:
            messages.error(request, "رقم الهوية يجب أن يتكون من 10 أرقام.")
            return redirect(
                "invitations:invitation_contract_detail",
                invitation_id=redirect_invitation.id
            )

    if request.user.email and signer_email == request.user.email.lower():
        messages.error(request, "لا يمكنك إرسال دعوة لنفسك.")
        return redirect(
            "invitations:invitation_contract_detail",
            invitation_id=redirect_invitation.id
        )

    already_exists = SigningInvitation.objects.filter(
        contract=contract,
        signer_email__iexact=signer_email
    ).exists()

    if already_exists:
        messages.error(request, "تمت إضافة هذا الطرف مسبقًا لهذا العقد.")
        return redirect(
            "invitations:invitation_contract_detail",
            invitation_id=redirect_invitation.id
        )

    mobile_exists = SigningInvitation.objects.filter(
        contract=contract,
        signer_mobile=clean_mobile
    ).exists()

    if mobile_exists:
        messages.error(request, "رقم الجوال مستخدم بالفعل لطرف آخر في هذا العقد.")
        return redirect(
            "invitations:invitation_contract_detail",
            invitation_id=redirect_invitation.id
        )

    new_invitation, secret = SigningInvitation.create_invitation(
        contract=contract,
        invited_by=request.user,
        signer_full_name=signer_full_name,
        signer_mobile=clean_mobile,
        signer_email=signer_email,
        party_type=request.POST.get("party_type", SigningInvitation.PartyType.INDIVIDUAL),
        signing_role=request.POST.get("signing_role", SigningInvitation.SigningRole.SIGNER),
        signer_national_id=signer_national_id,
        signer_nationality=request.POST.get("signer_nationality", "").strip(),
        organization_name=request.POST.get("organization_name", "").strip(),
        commercial_registration=request.POST.get("commercial_registration", "").strip(),
        tax_number=request.POST.get("tax_number", "").strip(),
        can_view_contract=bool(request.POST.get("can_view_contract")),
        can_comment=bool(request.POST.get("can_comment")),
        can_edit=bool(request.POST.get("can_edit")),
        can_upload_files=bool(request.POST.get("can_upload_files")),
        can_sign=bool(request.POST.get("can_sign")),
        invitation_message=request.POST.get("invitation_message", "").strip(),
    )

    new_invitation = SigningInvitationService.send_existing_invitation(new_invitation, secret)

    if new_invitation.status == SigningInvitation.Status.FAILED:
        messages.warning(request, "تمت إضافة الطرف ولكن فشل إرسال البريد الإلكتروني — تحقق من إعدادات SMTP في وحدة التحكم.")
    else:
        messages.success(request, "تمت إضافة الطرف وإرسال الدعوة إلى بريده الإلكتروني.")

    return redirect(
        "invitations:invitation_contract_detail",
        invitation_id=redirect_invitation.id
    )

@login_required
@require_POST
def reject_contract_modification(request, modification_id):
    modification = get_object_or_404(
        ContractModificationRequest,
        id=modification_id,
        status=ContractModificationRequest.Status.PENDING
    )

    contract = modification.contract

    is_creator = contract.creator_id == request.user.id
    user_invitation = contract.signing_invitations.filter(
        invitee_user=request.user
    ).first()

    if not is_creator and not user_invitation:
        messages.error(request, "لا تملك صلاحية رفض هذا التعديل.")
        return redirect("invitations:my_contracts")

    if modification.requested_by_id == request.user.id:
        messages.error(request, "لا يمكنك رفض تعديل أرسلته أنت.")
        return redirect("invitations:invitation_contract_detail", invitation_id=user_invitation.id if user_invitation else contract.signing_invitations.first().id)

    modification.status = ContractModificationRequest.Status.REJECTED
    modification.reviewed_at = timezone.now()
    modification.save(update_fields=["status", "reviewed_at"])

    messages.success(request, "تم رفض تعديل العقد.")

    redirect_invitation = user_invitation or contract.signing_invitations.first()

    return redirect(
        "invitations:invitation_contract_detail",
        invitation_id=redirect_invitation.id
    )

@login_required
@require_POST
def accept_invitation_contract(request, invitation_id):
    invitation = get_object_or_404(
        SigningInvitation,
        id=invitation_id,
        invitee_user=request.user
    )

    if not invitation.can_view_contract:
        messages.error(request, "لا تملك صلاحية عرض أو قبول هذا العقد")
        return redirect("invitations:my_contracts")

    if invitation.status in [
        SigningInvitation.Status.SIGNED,
        SigningInvitation.Status.REJECTED,
        SigningInvitation.Status.CANCELLED,
        SigningInvitation.Status.EXPIRED,
    ]:
        messages.warning(request, "لا يمكن قبول هذا العقد في حالته الحالية")
        return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)

    invitation.mark_as_accepted()

    messages.success(request, "تم قبول العقد بنجاح")
    return redirect("invitations:invitation_contract_detail", invitation_id=invitation.id)


@login_required
@require_POST
def approve_contract_modification(request, modification_id):
    modification = get_object_or_404(
        ContractModificationRequest,
        id=modification_id,
        status=ContractModificationRequest.Status.PENDING
    )

    contract = modification.contract

    is_creator = contract.creator_id == request.user.id
    user_invitation = contract.signing_invitations.filter(
        invitee_user=request.user
    ).first()

    if not is_creator and not user_invitation:
        messages.error(request, "لا تملك صلاحية قبول هذا التعديل.")
        return redirect("invitations:my_contracts")

    if modification.requested_by_id == request.user.id:
        messages.error(request, "لا يمكنك قبول تعديل أرسلته أنت.")
        redirect_invitation = user_invitation or contract.signing_invitations.first()
        return redirect("invitations:invitation_contract_detail", invitation_id=redirect_invitation.id)

    contract.current_version = modification.proposed_version
    contract.title_ar = modification.proposed_version.canonical_json.get("title_ar", contract.title_ar)
    contract.description_ar = modification.proposed_version.canonical_json.get("description_ar", contract.description_ar)
    contract.save(update_fields=["current_version", "title_ar", "description_ar", "updated_at"])

    modification.status = ContractModificationRequest.Status.APPROVED
    modification.reviewed_at = timezone.now()
    modification.save(update_fields=["status", "reviewed_at"])

    messages.success(request, "تمت الموافقة على النسخة المعدلة. الآن يمكن للطرف المطلوب توقيعه إتمام التوقيع.")

    redirect_invitation = user_invitation or contract.signing_invitations.first()

    return redirect(
        "invitations:invitation_contract_detail",
        invitation_id=redirect_invitation.id
    )