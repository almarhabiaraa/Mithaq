from django.db import models
from django.conf import settings


class Notification(models.Model):

    # Notification types
    CONTRACT_CREATED       = 'contract_created'
    CONTRACT_RECEIVED      = 'contract_received'
    CONTRACT_ACCEPTED      = 'contract_accepted'
    CONTRACT_REJECTED      = 'contract_rejected'
    CONTRACT_SIGNED        = 'contract_signed'
    CONTRACT_COMPLETED     = 'contract_completed'
    INVITATION_RECEIVED    = 'invitation_received'
    INVITATION_EXPIRED     = 'invitation_expired'
    CONTRACT_MODIFIED      = 'contract_modified'
    SUBSCRIPTION_EXPIRING  = 'subscription_expiring'
    SUBSCRIPTION_EXPIRED   = 'subscription_expired'
    CONTRACT_LIMIT_REACHED = 'contract_limit_reached'

    NOTIFICATION_TYPES = [
        (CONTRACT_CREATED,       'تم إنشاء العقد وإرسال الدعوات'),
        (CONTRACT_RECEIVED,      'لديك عقد جديد للمراجعة'),
        (CONTRACT_ACCEPTED,      'تم قبول العقد من الطرف الآخر'),
        (CONTRACT_REJECTED,      'تم رفض العقد من الطرف الآخر'),
        (CONTRACT_SIGNED,        'تم التوقيع على العقد'),
        (CONTRACT_COMPLETED,     'تم توثيق العقد على البلوكشين'),
        (INVITATION_RECEIVED,    'لديك دعوة توقيع جديدة'),
        (INVITATION_EXPIRED,     'انتهت صلاحية دعوة التوقيع'),
        (CONTRACT_MODIFIED,      'تم اقتراح تعديل على العقد'),
        (SUBSCRIPTION_EXPIRING,  'اشتراكك سينتهي خلال 3 أيام'),
        (SUBSCRIPTION_EXPIRED,   'انتهت صلاحية اشتراكك'),
        (CONTRACT_LIMIT_REACHED, 'لقد وصلت إلى الحد الأقصى من العقود'),
    ]

    # The user who receives the notification
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    # Link to the contract
    contract = models.ForeignKey(
        'contracts.Contract',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )

    # Notification type
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES
    )

    # Optional extra message
    message = models.TextField(blank=True)

    # Has the user read this notification?
    is_read = models.BooleanField(default=False)

    # When was the notification created?
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'notifications'

    def __str__(self):
        return f"{self.user.email} - {self.notification_type}"

    def get_message(self):
        # Returns the Arabic message based on notification type
        return dict(self.NOTIFICATION_TYPES).get(self.notification_type, '')