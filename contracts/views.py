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
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db import transaction
from django.http import HttpResponse
from invitations.models import SigningInvitation
from invitations.services import SigningInvitationService
from weasyprint import HTML as WeasyHTML


# ══════════════════════════════════════════════════════════════
#  Template Views
# ══════════════════════════════════════════════════════════════


def contract_create_view(request):
    return render(request, 'contracts/contract_create.html')


@login_required(login_url='accounts:sign_in')
def contract_list_view(request):
    # Filters
    status_filter = request.GET.get('status', '')
    type_filter   = request.GET.get('type', '')
    date_filter   = request.GET.get('date', 'newest')

    STATUS_MAP = {
        'draft':             Contract.Status.DRAFT,
        'pending_signature': Contract.Status.PENDING_SIGNATURES,
        'signed':            Contract.Status.SIGNED,
        'completed':         Contract.Status.COMPLETED,
        'cancelled':         Contract.Status.CANCELLED,
    }

    # All contracts for this user
    qs = Contract.objects.filter(
        Q(creator=request.user) | Q(parties__user=request.user)
    ).distinct()

    # Apply filters
    if status_filter and status_filter in STATUS_MAP:
        qs = qs.filter(status=STATUS_MAP[status_filter])

    if type_filter == 'created':
        qs = qs.filter(creator=request.user)
    elif type_filter == 'received':
        qs = qs.exclude(creator=request.user)

    qs = qs.order_by('created_at' if date_filter == 'oldest' else '-created_at')

    return render(request, 'contracts/contract_list.html', {
        'contracts':       qs,
        'selected_status': status_filter,
        'selected_type':   type_filter,
        'selected_date':   date_filter,
    })



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
    

# Step 4: added by Remas — PDF generation view using WeasyPrint
# Takes the saved contract HTML from canonical_json and converts it to a downloadable PDF
def contract_pdf_view(request, pk):
    # Get contract
    contract = get_object_or_404(Contract, pk=pk)

    # PDF only available after signing
    if contract.status not in [Contract.Status.SIGNED, Contract.Status.COMPLETED]:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("العقد لم يكتمل بعد")

    # Get HTML from canonical_json
    contract_html = contract.current_version.canonical_json.get('contract_html', '')

    # Logo URL
    logo_url = request.build_absolute_uri('/static/images/mithaq-logo.png')

    # Full PDF HTML
    full_html = f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                direction: rtl;
                color: #0A1633;
                font-size: 13px;
                line-height: 1.8;
                padding: 40px;
            }}
            .pdf-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 2px solid #B99655;
                padding-bottom: 16px;
                margin-bottom: 32px;
            }}
            .pdf-logo {{ height: 48px; }}
            .pdf-meta {{
                text-align: left;
                font-size: 11px;
                color: #6F7482;
            }}
            .contract-bismillah {{
                text-align: center;
                font-size: 16px;
                font-weight: bold;
                margin: 16px 0;
            }}
            .contract-article {{
                margin-bottom: 20px;
            }}
            .contract-article h4 {{
                font-size: 14px;
                font-weight: bold;
                color: #061D3B;
                margin-bottom: 8px;
                border-bottom: 1px solid #E7E3DA;
                padding-bottom: 4px;
            }}
            .contract-signatures {{
                display: flex;
                gap: 40px;
                margin-top: 40px;
                border-top: 1px solid #E7E3DA;
                padding-top: 24px;
            }}
            .sig-block {{ flex: 1; text-align: center; }}
            .sig-line {{
                border-bottom: 1px solid #0A1633;
                margin: 16px 0 8px;
            }}
            .sig-label {{ font-size: 11px; color: #6F7482; }}
            .sig-name {{ font-size: 12px; font-weight: bold; }}
            .contract-clauses-list {{ padding-right: 20px; }}
            .contract-clauses-list li {{ margin-bottom: 6px; }}
            .pdf-footer {{
                margin-top: 40px;
                border-top: 1px solid #E7E3DA;
                padding-top: 12px;
                text-align: center;
                font-size: 10px;
                color: #9AA1AE;
            }}
            .hash-box {{
                background: #F8F7F4;
                border: 1px solid #E7E3DA;
                border-radius: 6px;
                padding: 10px;
                font-size: 9px;
                color: #6F7482;
                word-break: break-all;
                font-family: monospace;
                margin-top: 16px;
            }}
        </style>
    </head>
    <body>
        <!-- Header -->
        <div class="pdf-header">
            <img src="{logo_url}" class="pdf-logo" alt="ميثاق">
            <div class="pdf-meta">
                <p>رقم العقد: {contract.id}</p>
                <p>تاريخ الإنشاء: {contract.created_at.strftime('%Y/%m/%d')}</p>
                <p>الحالة: {contract.get_status_display()}</p>
            </div>
        </div>

        <!-- Contract HTML -->
        {contract_html}

        <!-- Blockchain Hash -->
        {'<div class="hash-box">توثيق البلوكشين: ' + contract.canonical_hash + '</div>' if contract.canonical_hash else ''}

        <!-- Footer -->
        <div class="pdf-footer">
            <p>تم إنشاء هذا المستند بواسطة منصة ميثاق — جميع الحقوق محفوظة</p>
            <p>هذا العقد موثق رقمياً ومحمي بتقنية البلوكشين</p>
        </div>
    </body>
    </html>
    """

    # Convert to PDF
    pdf = WeasyHTML(string=full_html, base_url=request.build_absolute_uri()).write_pdf()

    # Return PDF response
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="mithaq-contract-{contract.id}.pdf"'
    return response