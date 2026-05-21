import uuid
from django.db import models
from django.conf import settings
from core.models import SoftDeleteModel


# Contract models
class Contract(SoftDeleteModel):


   class Status(models.TextChoices):
       DRAFT              = 'DRAFT',              'مسودة'
       PENDING_SIGNATURES = 'PENDING_SIGNATURES', 'بانتظار التوقيعات'
       SIGNED             = 'SIGNED',             'موقّع'
       COMPLETED          = 'COMPLETED',          'مكتمل'
       CANCELLED          = 'CANCELLED',          'ملغي'


   class ContractType(models.TextChoices):
       SERVICES    = 'SERVICES',    'عقد خدمات'
       SUPPLY      = 'SUPPLY',      'عقد توريد'
       RENT        = 'RENT',        'عقد إيجار'
       PARTNERSHIP = 'PARTNERSHIP', 'عقد شراكة'
       CONSULTING  = 'CONSULTING',  'عقد استشاري'
       EMPLOYMENT  = 'EMPLOYMENT',  'عقد عمل'
       OTHER       = 'OTHER',       'أخرى'


   id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
   title_ar        = models.CharField(max_length=255)
   title_en        = models.CharField(max_length=255, blank=True)
   description_ar  = models.TextField(blank=True)
   description_en  = models.TextField(blank=True)
   status          = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
   contract_type   = models.CharField(max_length=20, choices=ContractType.choices, blank=True, default='')
   creator         = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.RESTRICT,related_name='created_contracts')
   current_version = models.ForeignKey('ContractVersion',on_delete=models.SET_NULL,null=True, blank=True,
                         related_name='active_for_contract'
                     )
   template        = models.ForeignKey(
                         'templates_lib.ContractTemplate',
                         on_delete=models.SET_NULL,
                         null=True, blank=True
                     )
   canonical_hash  = models.CharField(max_length=64, blank=True, db_index=True)
   deleted_at      = models.DateTimeField(null=True, blank=True)
   created_at      = models.DateTimeField(auto_now_add=True)
   updated_at      = models.DateTimeField(auto_now=True)
   completed_at    = models.DateTimeField(null=True, blank=True)


   @property
   def progress(self):
       return {
           self.Status.DRAFT:              25,
           self.Status.PENDING_SIGNATURES: 50,
           self.Status.SIGNED:             75,
           self.Status.COMPLETED:          100,
           self.Status.CANCELLED:          0,
       }.get(self.status, 0)


   class Meta:
       db_table = 'contracts'
       ordering = ['-created_at']
       indexes = [
           models.Index(fields=['status'],        name='contracts_status_idx'),
           models.Index(fields=['-created_at'],   name='contracts_created_idx'),
           models.Index(fields=['canonical_hash'], name='contracts_hash_idx'),
       ]


   def __str__(self):
       return f"{self.title_ar} [{self.status}]"




class ContractVersion(models.Model):


   id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
   contract       = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='versions')
   version_number = models.PositiveIntegerField()
   created_by     = models.ForeignKey(
                        settings.AUTH_USER_MODEL,
                        on_delete=models.RESTRICT,
                        related_name='created_versions'
                    )
   canonical_json = models.JSONField(default=dict)
   change_summary = models.TextField(blank=True)
   created_at     = models.DateTimeField(auto_now_add=True)


   class Meta:
       db_table        = 'contract_versions'
       unique_together = [['contract', 'version_number']]
       ordering        = ['version_number']


   def __str__(self):
       return f"{self.contract.title_ar} — v{self.version_number}"




class ContractClause(models.Model):


   class ClauseType(models.TextChoices):
       GENERAL  = 'GENERAL',  'عام'
       PAYMENT  = 'PAYMENT',  'دفع'
       DELIVERY = 'DELIVERY', 'تسليم'
       PENALTY  = 'PENALTY',  'غرامة'
       CUSTOM   = 'CUSTOM',   'مخصص'


   id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
   version     = models.ForeignKey(ContractVersion, on_delete=models.CASCADE, related_name='clauses')
   order_index = models.PositiveIntegerField()
   clause_type = models.CharField(max_length=50, choices=ClauseType.choices, default=ClauseType.GENERAL)
   title_ar    = models.CharField(max_length=300, blank=True)
   title_en    = models.CharField(max_length=300, blank=True)
   content_ar  = models.TextField()
   content_en  = models.TextField(blank=True)


   class Meta:
       db_table = 'contract_clauses'
       ordering = ['order_index']


   def __str__(self):
       return f"بند {self.order_index} — {self.version}"




class ContractParty(models.Model):


   class Role(models.TextChoices):
       CREATOR = 'CREATOR', 'منشئ'
       PARTY   = 'PARTY',   'طرف'


   class ApprovalStatus(models.TextChoices):
       PENDING  = 'PENDING',  'معلّق'
       APPROVED = 'APPROVED', 'موافق'


   id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
   contract        = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='parties')
   user            = models.ForeignKey(
                         settings.AUTH_USER_MODEL,
                         on_delete=models.RESTRICT,
                         related_name='contract_parties'
                     )
   role            = models.CharField(max_length=20, choices=Role.choices)
   approval_status = models.CharField(max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING)
   approved_at     = models.DateTimeField(null=True, blank=True)
   joined_at       = models.DateTimeField(auto_now_add=True)


   class Meta:
       db_table        = 'contract_parties'
       unique_together = [['contract', 'user']]
       indexes = [
           models.Index(fields=['user'], name='parties_user_idx'),
       ]


   def __str__(self):
       return f"{self.user} — {self.contract.title_ar} ({self.role})"

class ContractInvitedParty(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="invited_parties"
    )

    invitation = models.OneToOneField(
        "invitations.SigningInvitation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_invited_party"
    )

    title = models.CharField(max_length=20, blank=True)
    full_name = models.CharField(max_length=255)
    mobile = models.CharField(max_length=30)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(db_index=True)

    party_type = models.CharField(max_length=30, default="INDIVIDUAL")
    signing_role = models.CharField(max_length=30, default="SIGNER")

    national_id = models.CharField(max_length=50, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    address_country = models.CharField(max_length=100, blank=True)
    address_city = models.CharField(max_length=100, blank=True)

    organization_name = models.CharField(max_length=255, blank=True)
    commercial_registration = models.CharField(max_length=100, blank=True)
    tax_number = models.CharField(max_length=100, blank=True)

    can_view_contract = models.BooleanField(default=True)
    can_comment = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_upload_files = models.BooleanField(default=False)
    can_sign = models.BooleanField(default=True)

    signing_order = models.PositiveIntegerField(default=1)
    invitation_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "contract_invited_parties"
        unique_together = [["contract", "email"]]

    def __str__(self):
        return f"{self.full_name} — {self.email}"

class ContractModificationRequest(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "بانتظار المراجعة"
        SENT = "SENT", "تم الإرسال"
        VIEWED = "VIEWED", "تمت المشاهدة"
        SIGNED = "SIGNED", "تم التوقيع"
        EXPIRED = "EXPIRED", "منتهي"
        CANCELLED = "CANCELLED", "ملغي"
        FAILED = "FAILED", "فشل الإرسال"
        REJECTED = "REJECTED", "مرفوض"
        APPROVED = "APPROVED", "مقبول"
        SUPERSEDED = "SUPERSEDED", "تم استبدالها"



    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    contract = models.ForeignKey(Contract,on_delete=models.CASCADE,related_name="modification_requests")
    proposed_version = models.ForeignKey(ContractVersion,on_delete=models.CASCADE,related_name="modification_requests")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.RESTRICT,related_name="requested_contract_modifications")
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.PENDING,db_index=True)
    reason = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "contract_modification_requests"
        ordering = ["-created_at"]