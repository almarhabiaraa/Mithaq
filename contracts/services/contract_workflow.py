from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from contracts.models import Contract, ContractVersion, ContractClause, ContractParty
from audit.services import log_event
from audit.constants import EventType


class ContractWorkflowService:

    @staticmethod
    @transaction.atomic
    def create_contract(creator, data):
        """
        data = {
            'title_ar': '...',
            'title_en': '...',           ← اختياري
            'description_ar': '...',     ← اختياري
            'description_en': '...',     ← اختياري
            'template': <instance>,      ← اختياري
            'clauses': [
                {
                    'content_ar': '...',
                    'title_ar': '...',       ← اختياري
                    'clause_type': '...',    ← اختياري، default: GENERAL
                },
            ]
        }
        """

        # ── 1. Validation ─────────────────────────────────────
        if not data.get('title_ar'):
            raise ValidationError('عنوان العقد مطلوب')

        clauses_data = data.get('clauses', [])
        if not clauses_data:
            raise ValidationError('العقد يجب أن يحتوي على بند واحد على الأقل')

        for i, clause in enumerate(clauses_data, start=1):
            if not clause.get('content_ar', '').strip():
                raise ValidationError(f'البند {i} لا يمكن أن يكون فارغاً')

        # ── 2. أنشئ Contract ──────────────────────────────────
        contract = Contract.objects.create(
            title_ar       = data['title_ar'],
            title_en       = data.get('title_en', ''),
            description_ar = data.get('description_ar', ''),
            description_en = data.get('description_en', ''),
            status         = Contract.Status.DRAFT,
            creator        = creator,
            template       = data.get('template'),
        )

        # ── 3. أنشئ Version 1 ─────────────────────────────────
        version = ContractVersion.objects.create(
            contract       = contract,
            version_number = 1,
            created_by     = creator,
            change_summary = 'النسخة الأولى',
             canonical_json = {
                     'contract_html': data.get('contract_html', ''),  # Step 3: added by Remas — saves contract HTML for PDF generation
                 }
        )

        # ── 4. أنشئ Clauses ───────────────────────────────────
        ContractClause.objects.bulk_create([
            ContractClause(
                version     = version,
                order_index = i,
                clause_type = c.get('clause_type', ContractClause.ClauseType.GENERAL),
                title_ar    = c.get('title_ar', ''),
                title_en    = c.get('title_en', ''),
                content_ar  = c['content_ar'],
                content_en  = c.get('content_en', ''),
            )
            for i, c in enumerate(clauses_data, start=1)
        ])

        # ── 5. اربط الـ current_version بالـ Contract ─────────
        contract.current_version = version
        contract.save(update_fields=['current_version'])

        # ── 6. أنشئ ContractParty للمنشئ ──────────────────────
        ContractParty.objects.create(
            contract        = contract,
            user            = creator,
            role            = ContractParty.Role.CREATOR,
            approval_status = ContractParty.ApprovalStatus.APPROVED,
        )

        # ── 7. سجّل الحدث ─────────────────────────────────────
        log_event(
            contract   = contract,
            event_type = EventType.CONTRACT_CREATED,
            actor      = creator,
            payload    = {'title_ar': contract.title_ar},
        )

        return contract

    # ──────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def create_new_version(contract, actor, clauses_data):
        """
        يُستدعى عند تعديل أي بند — ينشئ نسخة جديدة كاملة.
        clauses_data = قائمة البنود الجديدة كاملة (مش الفرق فقط)
        """

        # ── 1. Validation ─────────────────────────────────────
        if contract.status != Contract.Status.DRAFT:
            raise ValidationError('لا يمكن تعديل العقد بعد إغلاقه للتوقيع')

        if not clauses_data:
            raise ValidationError('يجب أن يحتوي العقد على بند واحد على الأقل')

        for i, clause in enumerate(clauses_data, start=1):
            if not clause.get('content_ar', '').strip():
                raise ValidationError(f'البند {i} لا يمكن أن يكون فارغاً')

        # ── 2. رقم النسخة الجديدة ─────────────────────────────
        last_version       = contract.versions.order_by('-version_number').first()
        new_version_number = last_version.version_number + 1 if last_version else 1

        # ── 3. أنشئ Version جديد ──────────────────────────────
        new_version = ContractVersion.objects.create(
            contract       = contract,
            version_number = new_version_number,
            created_by     = actor,
            change_summary = f'تعديل بواسطة {actor.get_full_name() or actor.email}',
        )

        # ── 4. أنشئ Clauses للنسخة الجديدة ───────────────────
        ContractClause.objects.bulk_create([
            ContractClause(
                version     = new_version,
                order_index = i,
                clause_type = c.get('clause_type', ContractClause.ClauseType.GENERAL),
                title_ar    = c.get('title_ar', ''),
                title_en    = c.get('title_en', ''),
                content_ar  = c['content_ar'],
                content_en  = c.get('content_en', ''),
            )
            for i, c in enumerate(clauses_data, start=1)
        ])

        # ── 5. حدّث current_version ───────────────────────────
        contract.current_version = new_version
        contract.save(update_fields=['current_version', 'updated_at'])

        # ── 6. أعد موافقات الأطراف ────────────────────────────
        contract.parties.exclude(
            role=ContractParty.Role.CREATOR
        ).update(
            approval_status = ContractParty.ApprovalStatus.PENDING,
            approved_at     = None,
        )

        # ── 7. سجّل الحدث ─────────────────────────────────────
        log_event(
            contract   = contract,
            event_type = EventType.VERSION_CREATED,
            actor      = actor,
            payload    = {'version_number': new_version.version_number},
        )

        return new_version

    # ──────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def approve_contract(contract, party):
        """
        party = ContractParty instance
        """

        # ── 1. Validation ─────────────────────────────────────
        if contract.status != Contract.Status.DRAFT:
            raise ValidationError('لا يمكن الموافقة — العقد مو في مرحلة المسودة')

        if party.approval_status == ContractParty.ApprovalStatus.APPROVED:
            raise ValidationError('وافقت على العقد مسبقاً')

        # ── 2. سجّل الموافقة ──────────────────────────────────
        party.approval_status = ContractParty.ApprovalStatus.APPROVED
        party.approved_at     = timezone.now()
        party.save(update_fields=['approval_status', 'approved_at'])

        # ── 3. سجّل الحدث ─────────────────────────────────────
        log_event(
            contract   = contract,
            event_type = EventType.PARTY_APPROVED,
            actor      = party.user,
            payload    = {'party_role': party.role},
        )

        # ── 4. تحقق إذا كل الأطراف وافقوا ────────────────────
        all_approved = not contract.parties.filter(
            approval_status=ContractParty.ApprovalStatus.PENDING
        ).exists()

        if all_approved:
            ContractWorkflowService.lock_for_signing(contract)

        return contract

    # ──────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def lock_for_signing(contract):

        # ── 1. Validation ─────────────────────────────────────
        if contract.status != Contract.Status.DRAFT:
            raise ValidationError('العقد مو في مرحلة المسودة')

        if not contract.current_version:
            raise ValidationError('العقد ما عنده نسخة حالية')

        if contract.parties.count() < 2:
            raise ValidationError('العقد يحتاج طرفين على الأقل')

        # ── 2. احسب الـ canonical_hash ────────────────────────
        from contracts.services.signing_service import SigningService
        canonical_hash = SigningService.compute_canonical_hash(contract.current_version)

        # ── 3. حوّل الحالة ────────────────────────────────────
        contract.status         = Contract.Status.PENDING_SIGNATURES
        contract.canonical_hash = canonical_hash
        contract.save(update_fields=['status', 'canonical_hash', 'updated_at'])

        # ── 4. سجّل الحدث ─────────────────────────────────────
        log_event(
            contract   = contract,
            event_type = EventType.CONTRACT_LOCKED,
            actor      = None,
            payload    = {'canonical_hash': canonical_hash},
        )

        return contract

    # ──────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def cancel_contract(contract, actor):

        # ── 1. Validation ─────────────────────────────────────
        if contract.status != Contract.Status.DRAFT:
            raise ValidationError('لا يمكن إلغاء العقد — الحالة الحالية: ' + contract.status)

        if contract.creator != actor:
            raise ValidationError('فقط منشئ العقد يمكنه الإلغاء')

        # ── 2. ألغِ العقد ─────────────────────────────────────
        contract.status = Contract.Status.CANCELLED
        contract.save(update_fields=['status', 'updated_at'])

        # ── 3. سجّل الحدث ─────────────────────────────────────
        log_event(
            contract   = contract,
            event_type = EventType.CONTRACT_CANCELLED,
            actor      = actor,
            payload    = {},
        )

        return contract