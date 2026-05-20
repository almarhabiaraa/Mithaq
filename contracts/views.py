from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404, render
from notifications.services import NotificationService
from notifications.models import Notification
from contracts.models import Contract, ContractParty, ContractVersion
from contracts.serializers import (ContractSerializer, ContractCreateSerializer, ContractVersionSerializer)
from contracts.permissions import (IsContractParty, IsContractCreator, CanEditClauses, CanSign)
from contracts.services.contract_workflow import ContractWorkflowService
from contracts.services.signing_service import SigningService
from signatures.models import Signature

from django.db import transaction
from invitations.models import SigningInvitation
from invitations.services import SigningInvitationService


# ══════════════════════════════════════════════════════════════
#  Template Views
# ══════════════════════════════════════════════════════════════


def contract_create_view(request):
    return render(request, 'contracts/contract_create.html')



def contract_detail_view(request, pk):
    contract = get_object_or_404(Contract, pk=pk)

    # ── مؤقت للتطوير — بدون login required ──
    if request.user.is_authenticated:
        user_party = ContractParty.objects.filter(
            contract=contract, user=request.user
        ).first()
        user_signed = Signature.objects.filter(
            contract=contract, signer=request.user
        ).exists()
    else:
        # للتطوير فقط — نعرض الصفحة بدون صلاحيات
        user_party  = contract.parties.first()
        user_signed = False

    return render(request, 'contracts/contract_detail.html', {
        'contract':    contract,
        'user_party':  user_party,
        'user_signed': user_signed,
    })


def version_history_view(request, pk):
    contract = get_object_or_404(Contract, pk=pk)

    user_party = ContractParty.objects.filter(
        contract=contract, user=request.user
    ).first()

    if not user_party:
        from django.http import Http404
        raise Http404

    versions = contract.versions.prefetch_related('clauses').order_by('-version_number')

    return render(request, 'contracts/version_history.html', {
        'contract': contract,
        'versions': versions,
    })


def audit_timeline_view(request, pk):
    contract = get_object_or_404(Contract, pk=pk)

    user_party = ContractParty.objects.filter(
        contract=contract, user=request.user
    ).first()

    if not user_party:
        from django.http import Http404
        raise Http404

    from audit.models import AuditEvent
    events = AuditEvent.objects.filter(
        contract=contract
    ).select_related('actor').order_by('-created_at')

    return render(request, 'contracts/audit_timeline.html', {
        'contract': contract,
        'events':   events,
    })


# ══════════════════════════════════════════════════════════════
#  API Views
# ══════════════════════════════════════════════════════════════

def _as_bool(value):
    return value in [True, "true", "True", "1", 1, "on"]

class ContractListCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user = request.user if request.user.is_authenticated else User.objects.first()

        invite_parties = request.data.get("invite_parties", [])

        serializer = ContractCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            contract = ContractWorkflowService.create_contract(
                creator=user,
                data=serializer.validated_data,
            )

            for index, party in enumerate(invite_parties, start=1):
                invitation, secret = SigningInvitation.create_invitation(
                    contract=contract,
                    invited_by=user,

                    signer_full_name=party.get("full_name", "").strip(),
                    signer_mobile=party.get("mobile", "").strip(),
                    signer_email=party.get("email", "").strip(),

                    party_type=party.get(
                        "party_type",
                        SigningInvitation.PartyType.INDIVIDUAL
                    ),
                    contract_role=party.get(
                        "contract_role",
                        SigningInvitation.ContractRole.SECOND_PARTY
                    ),
                    signing_role=party.get(
                        "signing_role",
                        SigningInvitation.SigningRole.SIGNER
                    ),

                    signer_national_id=party.get("national_id", "").strip(),
                    signer_nationality=party.get("nationality", "").strip(),

                    organization_name=party.get("organization_name", "").strip(),
                    commercial_registration=party.get("commercial_registration", "").strip(),
                    tax_number=party.get("tax_number", "").strip(),

                    can_view_contract=_as_bool(party.get("can_view_contract", True)),
                    can_comment=_as_bool(party.get("can_comment", False)),
                    can_edit=_as_bool(party.get("can_edit", False)),
                    can_upload_files=_as_bool(party.get("can_upload_files", False)),
                    can_sign=_as_bool(party.get("can_sign", True)),

                    signing_order=int(party.get("signing_order") or index),
                    invitation_message=party.get("invitation_message", "").strip(),
                )

                SigningInvitationService.send_existing_invitation(invitation, secret)

        first_invitation = contract.signing_invitations.first()

        return Response({
            "id": str(contract.id),
            "invitation_id": str(first_invitation.id) if first_invitation else None,
        }, status=status.HTTP_201_CREATED)
        
'''
class ContractListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        contracts = Contract.objects.filter(
            parties__user=request.user
        ).select_related(
            'creator', 'current_version'
        ).prefetch_related(
            'parties__user', 'current_version__clauses', 'signatures__signer'
        ).order_by('-created_at')

        serializer = ContractSerializer(contracts, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ContractCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        contract = ContractWorkflowService.create_contract(
            creator=request.user,
            data=serializer.validated_data,
        )

        # Notify all parties that a new contract has been received
        NotificationService.notify_all_parties(
            contract=contract,
            notification_type=Notification.CONTRACT_RECEIVED,
            exclude_user=request.user,
        )

        return Response(
            ContractSerializer(contract).data,
            status=status.HTTP_201_CREATED
        )
'''

class ContractDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_contract(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        self.check_object_permissions(request, contract)
        return contract

    def get(self, request, pk):
        self.permission_classes = [IsAuthenticated, IsContractParty]
        contract = self.get_contract(request, pk)
        return Response(ContractSerializer(contract).data)

    def patch(self, request, pk):
        self.permission_classes = [IsAuthenticated, IsContractParty, CanEditClauses]
        contract = self.get_contract(request, pk)

        allowed = ['title_ar', 'title_en', 'description_ar', 'description_en']
        data = {k: v for k, v in request.data.items() if k in allowed}

        serializer = ContractSerializer(contract, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(ContractSerializer(contract).data)

    def delete(self, request, pk):
        self.permission_classes = [IsAuthenticated, IsContractCreator, CanEditClauses]
        contract = self.get_contract(request, pk)
        contract.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ApproveView(APIView):
    permission_classes = [IsAuthenticated, IsContractParty]

    def post(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        self.check_object_permissions(request, contract)

        party = get_object_or_404(ContractParty, contract=contract, user=request.user)
        ContractWorkflowService.approve_contract(contract, party)

        # Notify all parties that the contract has been accepted
        NotificationService.notify_all_parties(
            contract=contract,
            notification_type=Notification.CONTRACT_ACCEPTED,
            exclude_user=request.user,
        )

        contract.refresh_from_db()
        return Response(ContractSerializer(contract).data)


class SignView(APIView):
    permission_classes = [IsAuthenticated, CanSign]

    def post(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        self.check_object_permissions(request, contract)

        submitted_hash = request.data.get('hash')
        if not submitted_hash:
            return Response(
                {'error': 'الـ hash مطلوب'},
                status=status.HTTP_400_BAD_REQUEST
            )

        SigningService.validate_and_sign(
            contract=contract,
            signer=request.user,
            submitted_hash=submitted_hash,
            request=request,
        )

        contract.refresh_from_db()


        # Notify all parties that the contract has been signed
        NotificationService.notify_all_parties(
            contract=contract,
            notification_type=Notification.CONTRACT_SIGNED,
            exclude_user=request.user,
        )

        # If contract is completed notify all parties
        if contract.status == Contract.Status.COMPLETED:
            NotificationService.notify_all_parties(
                contract=contract,
                notification_type=Notification.CONTRACT_COMPLETED,
            )

        return Response(ContractSerializer(contract).data)


class CancelView(APIView):
    permission_classes = [IsAuthenticated, IsContractCreator]

    def post(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        self.check_object_permissions(request, contract)

        ContractWorkflowService.cancel_contract(contract, request.user)


        # Notify all parties that the contract has been rejected
        NotificationService.notify_all_parties(
            contract=contract,
            notification_type=Notification.CONTRACT_REJECTED,
            exclude_user=request.user,
        )

        contract.refresh_from_db()
        return Response(ContractSerializer(contract).data)


class VersionListView(APIView):
    permission_classes = [IsAuthenticated, IsContractParty]

    def get(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        self.check_object_permissions(request, contract)

        versions = contract.versions.prefetch_related('clauses').order_by('version_number')
        return Response(ContractVersionSerializer(versions, many=True).data)


class VersionDetailView(APIView):
    permission_classes = [IsAuthenticated, IsContractParty]

    def get(self, request, pk, version_number):
        contract = get_object_or_404(Contract, pk=pk)
        self.check_object_permissions(request, contract)

        version = get_object_or_404(
            ContractVersion,
            contract=contract,
            version_number=version_number
        )
        return Response(ContractVersionSerializer(version).data)