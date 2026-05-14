from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from notifications.services import NotificationService
from notifications.models import Notification

from contracts.models import Contract, ContractParty, ContractVersion
from contracts.serializers import (
    ContractSerializer, ContractCreateSerializer, ContractVersionSerializer
)
from contracts.permissions import (
    IsContractParty, IsContractCreator, CanEditClauses, CanSign
)
from contracts.services.contract_workflow import ContractWorkflowService
from contracts.services.signing_service import SigningService


# ── Contract List + Create ─────────────────────────────────────────────────
class ContractListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """قائمة عقود المستخدم فقط"""
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
        """إنشاء عقد جديد"""
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


# ── Contract Detail ────────────────────────────────────────────────────────
class ContractDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_contract(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        self.check_object_permissions(request, contract)
        return contract

    def get(self, request, pk):
        """تفاصيل عقد"""
        self.permission_classes = [IsAuthenticated, IsContractParty]
        contract = self.get_contract(request, pk)
        return Response(ContractSerializer(contract).data)

    def patch(self, request, pk):
        """تعديل العنوان والوصف فقط — DRAFT فقط"""
        self.permission_classes = [IsAuthenticated, IsContractParty, CanEditClauses]
        contract = self.get_contract(request, pk)

        allowed = ['title_ar', 'title_en', 'description_ar', 'description_en']
        data = {k: v for k, v in request.data.items() if k in allowed}

        serializer = ContractSerializer(contract, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(ContractSerializer(contract).data)

    def delete(self, request, pk):
        """حذف ناعم — creator + DRAFT فقط"""
        self.permission_classes = [IsAuthenticated, IsContractCreator, CanEditClauses]
        contract = self.get_contract(request, pk)
        contract.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Approve ────────────────────────────────────────────────────────────────
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

        return Response(ContractSerializer(contract).data)


# ── Sign ───────────────────────────────────────────────────────────────────
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


# ── Cancel ─────────────────────────────────────────────────────────────────
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

        return Response(ContractSerializer(contract).data)


# ── Versions ───────────────────────────────────────────────────────────────
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

        version = get_object_or_404(ContractVersion, contract=contract, version_number=version_number)
        return Response(ContractVersionSerializer(version).data)
