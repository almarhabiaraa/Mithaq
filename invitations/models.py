import uuid
import secrets
import hashlib
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone


class SigningInvitation(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "بانتظار الإرسال"
        SENT = "SENT", "تم الإرسال"
        VIEWED = "VIEWED", "تمت المشاهدة"
        SIGNED = "SIGNED", "تم التوقيع"
        EXPIRED = "EXPIRED", "منتهي"
        CANCELLED = "CANCELLED", "ملغي"
        FAILED = "FAILED", "فشل الإرسال"
        REJECTED = "REJECTED", "مرفوض"

    class PartyType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "فرد"
        ORGANIZATION = "ORGANIZATION", "منشأة"

    class ContractRole(models.TextChoices):
        FIRST_PARTY = "FIRST_PARTY", "الطرف الأول"
        SECOND_PARTY = "SECOND_PARTY", "الطرف الثاني"
        WITNESS = "WITNESS", "شاهد"

    class SigningRole(models.TextChoices):
        SIGNER = "SIGNER", "موقّع"
        REVIEWER = "REVIEWER", "مراجع"
        APPROVER = "APPROVER", "معتمد"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey("contracts.Contract",on_delete=models.CASCADE,related_name="signing_invitations")
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.RESTRICT,related_name="sent_signing_invitations")
    party_type = models.CharField(max_length=20,choices=PartyType.choices,default=PartyType.INDIVIDUAL)
    contract_role = models.CharField(max_length=30,choices=ContractRole.choices,default=ContractRole.SECOND_PARTY)
    signing_role = models.CharField(max_length=30,choices=SigningRole.choices,default=SigningRole.SIGNER)
    signer_full_name = models.CharField(max_length=255)
    signer_mobile = models.CharField(max_length=15)
    signer_email = models.EmailField(blank=True)
    signer_national_id = models.CharField(max_length=20, blank=True)
    signer_nationality = models.CharField(max_length=100, blank=True)
    organization_name = models.CharField(max_length=255, blank=True)
    commercial_registration = models.CharField(max_length=50, blank=True)
    tax_number = models.CharField(max_length=50, blank=True)
    can_view_contract = models.BooleanField(default=True)
    can_comment = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_upload_files = models.BooleanField(default=False)
    can_sign = models.BooleanField(default=True)
    signing_order = models.PositiveIntegerField(default=1)
    invitation_message = models.TextField(blank=True)
    is_mobile_verified = models.BooleanField(default=False)
    is_identity_verified = models.BooleanField(default=False)
    reference_number = models.CharField(max_length=20, unique=True, db_index=True)
    secret_hash = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.PENDING,db_index=True)
    sms_message = models.TextField(blank=True)
    sms_provider = models.CharField(max_length=50, blank=True)
    sms_provider_message_id = models.CharField(max_length=255, blank=True)
    send_attempts = models.PositiveIntegerField(default=0)
    failure_reason = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "signing_invitations"
        ordering = ["signing_order", "-created_at"]
        unique_together = [["contract", "signer_mobile"]]
        indexes = [
            models.Index(fields=["contract", "status"], name="signinv_contract_status_idx"),
            models.Index(fields=["signer_mobile"], name="signinv_mobile_idx"),
            models.Index(fields=["reference_number"], name="signinv_ref_idx"),
            models.Index(fields=["-created_at"], name="signinv_created_idx"),
        ]

    def __str__(self):
        return f"{self.reference_number} - {self.signer_full_name} - {self.status}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_active(self):
        return self.status in [self.Status.PENDING, self.Status.SENT] and not self.is_expired

    def mark_as_sent(self, message="", provider="mock", provider_message_id=""):
        self.status = self.Status.SENT
        self.sms_message = message
        self.sms_provider = provider
        self.sms_provider_message_id = provider_message_id
        self.sent_at = timezone.now()
        self.send_attempts += 1
        self.save(update_fields=["status","sms_message","sms_provider","sms_provider_message_id","sent_at","send_attempts","updated_at",])

    def mark_as_failed(self, reason):
        self.status = self.Status.FAILED
        self.failure_reason = reason
        self.send_attempts += 1
        self.save(update_fields=["status","failure_reason","send_attempts","updated_at",])

    def mark_as_viewed(self):
        self.status = self.Status.VIEWED
        self.viewed_at = timezone.now()
        self.save(update_fields=["status", "viewed_at", "updated_at"])

    def mark_as_signed(self):
        self.status = self.Status.SIGNED
        self.signed_at = timezone.now()
        self.save(update_fields=["status", "signed_at", "updated_at"])

    def mark_as_rejected(self):
        self.status = self.Status.REJECTED
        self.rejected_at = timezone.now()
        self.save(update_fields=["status", "rejected_at", "updated_at"])

    @staticmethod
    def generate_secret():
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_secret(secret):
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_reference_number():
        random_part = secrets.randbelow(900000) + 100000
        return f"MTH-{random_part}"

    @classmethod
    def create_invitation(cls,contract,invited_by,signer_full_name,signer_mobile,signer_email="",party_type=PartyType.INDIVIDUAL,contract_role=ContractRole.SECOND_PARTY,signing_role=SigningRole.SIGNER,signer_national_id="",signer_nationality="",organization_name="",commercial_registration="",tax_number="",can_view_contract=True,can_comment=False,can_edit=False, can_upload_files=False, can_sign=True,signing_order=1, invitation_message="", expiry_hours=72,):
        secret = cls.generate_secret()
        secret_hash = cls.hash_secret(secret)
        reference_number = cls.generate_reference_number()
        
        while cls.objects.filter(reference_number=reference_number).exists():
            reference_number = cls.generate_reference_number()

        invitation = cls.objects.create(
            contract=contract,
            invited_by=invited_by,
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
            can_view_contract=can_view_contract,
            can_comment=can_comment,can_edit=can_edit,
            can_upload_files=can_upload_files,
            can_sign=can_sign,
            signing_order=signing_order,
            invitation_message=invitation_message,
            reference_number=reference_number,
            secret_hash=secret_hash,
            expires_at=timezone.now() + timedelta(hours=expiry_hours),
        )

        return invitation, secret
