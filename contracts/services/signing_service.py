import hashlib
import json

from django.db import transaction
from django.core.exceptions import ValidationError

from contracts.models import Contract, ContractParty
from signatures.models import Signature
from audit.services import log_event
from audit.constants import EventType
from accounts.services.face_verification_service import is_user_verified # (added by ghadi: to check if user is verified before allowing contract signatures)



# (added by ghadi: helper function to check identity verification before signing)
def sign_contract(contract, signer, request):
    """
    Handle contract signing with identity verification check.
    """
    # Check identity verification first
    if not is_user_verified(signer):
        raise PermissionError(
            'يجب التحقق من هويتك أولاً قبل توقيع العقد. '
            'اذهب إلى صفحة التحقق من الهوية.'
        )


class SigningService:

    @staticmethod
    def compute_canonical_hash(version):
        clauses = version.clauses.order_by('order_index')

        payload = {
            'contract_id':    str(version.contract.id),
            'version_number': version.version_number,
            'title_ar':       version.contract.title_ar,
            'clauses': [
                {
                    'order':      c.order_index,
                    'type':       c.clause_type,
                    'title_ar':   c.title_ar,
                    'content_ar': c.content_ar,
                    'content_en': c.content_en,
                }
                for c in clauses
            ]
        }

        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    @staticmethod
    @transaction.atomic
    def validate_and_sign(contract, signer, submitted_hash, request=None):

        # ── 1. select_for_update ───────────────────────────────
        contract = Contract.objects.select_for_update().get(pk=contract.pk)

        # ── 2. تحقق من حالة العقد ─────────────────────────────
        if contract.status != Contract.Status.PENDING_SIGNATURES:
            raise ValidationError('العقد مو في مرحلة التوقيع')

        # ── 3. تحقق أن الـ signer طرف في العقد ───────────────
        try:
            party = ContractParty.objects.get(contract=contract, user=signer)
        except ContractParty.DoesNotExist:
            raise ValidationError('لست طرفاً في هذا العقد')

        # ── 4. تحقق أنه ما وقّع مسبقاً ───────────────────────
        if Signature.objects.filter(contract=contract, signer=signer).exists():
            raise ValidationError('وقّعت على هذا العقد مسبقاً')

        # ── 5. تحقق أن الـ hash متطابق ────────────────────────
        if submitted_hash != contract.canonical_hash:
            raise ValidationError('الـ hash غير متطابق — العقد تغيّر')

        # ── 6. سجّل التوقيع ───────────────────────────────────
        ip_address = None
        user_agent = ''
        if request:
            ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')

        signature = Signature.objects.create(
            contract         = contract,
            contract_version = contract.current_version,
            signer           = signer,
            signed_hash      = submitted_hash,
            ip_address       = ip_address,
            user_agent       = user_agent,
        )

        # ── 7. سجّل الحدث ─────────────────────────────────────
        log_event(
            contract   = contract,
            event_type = EventType.CONTRACT_SIGNED,
            actor      = signer,
            payload    = {'signed_hash': submitted_hash},
        )

        # ── 8. تحقق إذا كل الأطراف وقّعوا ────────────────────
        total_parties    = contract.parties.count()
        total_signatures = Signature.objects.filter(contract=contract).count()

        if total_signatures == total_parties:
            contract.status = Contract.Status.SIGNED
            contract.save(update_fields=['status', 'updated_at'])

            log_event(
                contract   = contract,
                event_type = EventType.ALL_PARTIES_SIGNED,
                actor      = None,
                payload    = {'total_signatures': total_signatures},
            )

            # ── 9. trigger blockchain بعد اكتمال الـ transaction
            def submit_to_chain():
                from blockchain.services import ChainTransactionStore
                store = ChainTransactionStore()
                store.create_operation(
                    contract        = contract,
                    contract_hash   = contract.canonical_hash,
                    idempotency_key = f'contract-{contract.id}-signed',
                )

            transaction.on_commit(submit_to_chain)

        return signature