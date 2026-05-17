import uuid
from django.db import models
from django.conf import settings
from contracts.models import Contract




class AuditEvent(models.Model):


   class EventType(models.TextChoices):
       # ── User ──────────────────────────────
       USER_REGISTERED       = 'USER_REGISTERED',       'مستخدم سجّل'
       USER_LOGIN_FAILED     = 'USER_LOGIN_FAILED',     'فشل تسجيل دخول'
       USER_PROFILE_UPDATED  = 'USER_PROFILE_UPDATED',  'ملف شخصي حُدِّث'
       # ── Subscription ──────────────────────────────────────────────────────────
       # (added by ghadi: subscription lifecycle events written by subscription_service.py)
       SUBSCRIPTION_ACTIVATED  = 'SUBSCRIPTION_ACTIVATED',  'اشتراك فُعِّل'
       # (added by ghadi: these two are PENDING — waiting for the audit team to add them)
       # (they are already used in subscription_service.py but wrapped in try/except
       #  so the app won't crash — it just won't write audit events until added)
       # SUBSCRIPTION_EXPIRED   = 'SUBSCRIPTION_EXPIRED',   'اشتراك انتهى'
       # CONTRACT_LIMIT_CHECKED = 'CONTRACT_LIMIT_CHECKED', 'فُحص حد العقود'
       # → Full instructions: ghadi_works/for_audit_app/event_types.py
       # ── Contract ──────────────────────────
       CONTRACT_CREATED      = 'CONTRACT_CREATED',      'عقد أُنشئ'
       CONTRACT_UPDATED      = 'CONTRACT_UPDATED',      'عقد حُدِّث'
       VERSION_CREATED       = 'VERSION_CREATED',       'نسخة جديدة'
       PARTY_INVITED         = 'PARTY_INVITED',         'طرف دُعي'
       PARTY_JOINED          = 'PARTY_JOINED',          'طرف انضم'
       PARTY_APPROVED        = 'PARTY_APPROVED',        'طرف وافق'
       APPROVAL_RESET        = 'APPROVAL_RESET',        'موافقات أُعيدت'
       CONTRACT_LOCKED       = 'CONTRACT_LOCKED',       'عقد قُفل للتوقيع'
       CONTRACT_SIGNED       = 'CONTRACT_SIGNED',       'طرف وقّع'
       ALL_PARTIES_SIGNED    = 'ALL_PARTIES_SIGNED',    'جميع الأطراف وقّعوا'
       CONTRACT_CANCELLED    = 'CONTRACT_CANCELLED',    'عقد أُلغي'
       CONTRACT_COMPLETED    = 'CONTRACT_COMPLETED',    'عقد اكتمل'
       PDF_EXPORTED          = 'PDF_EXPORTED',          'PDF صُدِّر'
       # ── Blockchain ────────────────────────
       ON_CHAIN_TX_SUBMITTED = 'ON_CHAIN_TX_SUBMITTED', 'معاملة أُرسلت'
       ON_CHAIN_TX_CONFIRMED = 'ON_CHAIN_TX_CONFIRMED', 'معاملة أُكِّدت'
       ON_CHAIN_TX_FAILED    = 'ON_CHAIN_TX_FAILED',    'معاملة فشلت'


   id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
   contract   = models.ForeignKey(
                    Contract, on_delete=models.RESTRICT,
                    null=True, blank=True,
                    related_name='audit_events'
                )
   actor      = models.ForeignKey(
                    settings.AUTH_USER_MODEL,
                    on_delete=models.RESTRICT,
                    null=True, blank=True,
                    related_name='audit_events'
                )
   event_type = models.CharField(max_length=50, choices=EventType.choices)
   payload    = models.JSONField(default=dict)
   ip_address = models.GenericIPAddressField(null=True, blank=True)
   user_agent = models.TextField(blank=True)
   created_at = models.DateTimeField(auto_now_add=True, db_index=True)


   class Meta:
       db_table = 'audit_events'
       indexes = [
           models.Index(fields=['contract', '-created_at'], name='audit_contract_idx'),
           models.Index(fields=['actor',    '-created_at'], name='audit_actor_idx'),
           models.Index(fields=['event_type','-created_at'],name='audit_type_idx'),
       ]


   def save(self, *args, **kwargs):
       if self.pk and AuditEvent.objects.filter(pk=self.pk).exists():
           raise ValueError('AuditEvent is append-only')
       super().save(*args, **kwargs)


   def delete(self, *args, **kwargs):
       raise ValueError('AuditEvent is append-only')


   def __str__(self):
       return f"{self.event_type} — {self.created_at}"