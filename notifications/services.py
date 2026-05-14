from .models import Notification


class NotificationService:

    @staticmethod
    def notify(user, notification_type, contract=None, message=''):
        """Create a single notification for a specific user"""
        Notification.objects.create(
            user=user,
            contract=contract,
            notification_type=notification_type,
            message=message,
        )

    @staticmethod
    def notify_all_parties(contract, notification_type, exclude_user=None, message=''):
        """Send notification to all contract parties except who triggered it"""
        parties = contract.parties.select_related('user').all()
        for party in parties:
            if exclude_user and party.user == exclude_user:
                continue
            NotificationService.notify(
                user=party.user,
                notification_type=notification_type,
                contract=contract,
                message=message,
            )