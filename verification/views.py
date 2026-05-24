# =============================================================================
# verification/views.py
# OWNED BY: Ghadi
#
# HOW VERIFICATION IS CONNECTED TO CONTRACTS:
#   User enters the contract UUID (shown on contract detail page / signed PDF)
#   → JS calls GET /verify/api/verify-contract/?contract_id=<uuid>
#   → This view queries Contract by id
#   → Also queries SigningInvitation for signature status
#   → Also queries ChainTransaction for blockchain confirmation
#   → Returns result + contract summary (no private clause content or PII)
#
# RESULT VALUES (matched to verify_2.js expectations):
#   INVALID_CONTRACT_ID  — input is not a valid UUID
#   NOT_FOUND            — no contract with this id
#   VALID_COMPLETED      — all parties signed
#   VALID_PENDING_SIGNATURES — found but not all parties signed yet
#
# SECURITY:
#   Both endpoints are public (no login needed) so anyone can verify a contract.
#   The response includes contract title since the user typed the exact contract id.
#   No clause content, no party personal data is ever returned.
# =============================================================================

from uuid import UUID

from django.http import HttpRequest
from django.shortcuts import render

from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from blockchain.models import ChainTransaction
from contracts.models import Contract
from invitations.models import SigningInvitation


def verify_page(request: HttpRequest):
    """
    GET /verify/
    Public HTML page — no login required.
    Passes the API endpoint URL to the template so verify_2.js knows where to call.
    """
    return render(request, 'verification/verify.html', {
        'api_url': '/verify/api/verify-contract/',
    })


class VerifyContractAPIView(APIView):
    """
    GET /verify/api/verify-contract/?contract_id=<uuid>

    Public endpoint — no authentication required.
    Throttled 60 requests/hour per IP to prevent scraping.

    Looks up the contract by its UUID, checks signature and blockchain status,
    and returns a summary. This is intentionally called with the full UUID so
    callers already know the contract exists — no enumeration risk.

    Response shape consumed by verify_2.js:
        { "result": "VALID_COMPLETED" | "VALID_PENDING_SIGNATURES" | "NOT_FOUND" | "INVALID_CONTRACT_ID",
          "contract": { id, title, status, status_display, contract_type_display,
                        created_at, updated_at, parties_count, signed_parties,
                        all_signed, blockchain_tx, blockchain_confirmed_at } }
    """

    permission_classes = []
    throttle_classes = [AnonRateThrottle]

    def get(self, request: HttpRequest):
        contract_id = request.GET.get('contract_id', '').strip()

        # ── Validate UUID format ───────────────────────────────────────────────
        try:
            UUID(contract_id)
        except (ValueError, TypeError):
            return Response({'result': 'INVALID_CONTRACT_ID'}, status=400)

        # ── Look up the contract ───────────────────────────────────────────────
        contract = (
            Contract.objects
            .filter(id=contract_id)
            .first()
        )

        if not contract:
            return Response({'result': 'NOT_FOUND'}, status=404)

        # ── Signature status (via SigningInvitation) ───────────────────────────
        invitations    = SigningInvitation.objects.filter(contract=contract)
        total_parties  = invitations.count()
        signed_parties = invitations.filter(status=SigningInvitation.Status.SIGNED).count()
        all_signed     = total_parties > 0 and signed_parties == total_parties

        # ── Blockchain confirmation (added by ghadi) ───────────────────────────
        chain_tx = (
            ChainTransaction.objects
            .filter(contract=contract, status=ChainTransaction.Status.CONFIRMED)
            .first()
        )

        result = 'VALID_COMPLETED' if all_signed else 'VALID_PENDING_SIGNATURES'

        return Response({
            'result': result,
            'contract': {
                'id':                    str(contract.id),
                'title':                 contract.title_ar or 'عقد بدون عنوان',
                'status':                contract.status,
                'status_display':        contract.get_status_display(),
                'contract_type_display': (
                    contract.get_contract_type_display()
                    if contract.contract_type else 'غير محدد'
                ),
                'created_at':            (
                    contract.created_at.strftime('%Y-%m-%d')
                    if contract.created_at else '-'
                ),
                'updated_at':            (
                    contract.updated_at.strftime('%Y-%m-%d %H:%M')
                    if contract.updated_at else '-'
                ),
                'parties_count':         total_parties,
                'signed_parties':        signed_parties,
                'all_signed':            all_signed,
                # Blockchain info — shown in the a-tx-link cell of verify_2.js
                'blockchain_tx':         chain_tx.tx_hash if chain_tx else None,
                'blockchain_confirmed_at': (
                    chain_tx.confirmed_at.strftime('%Y-%m-%d %H:%M')
                    if chain_tx else None
                ),
            },
        })
