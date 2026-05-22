from .models import Notification


class NotificationService:

    @staticmethod
    def notify(user, notification_type, contract=None, message=''):
        """Create a single notification for a specific user"""
        try:
            n = Notification.objects.create(
                user=user,
                contract=contract,
                notification_type=notification_type,
                message=message,
            )
            print(f"[Notification SAVED] id={n.id} user_id={user.id} type={notification_type}")
        except Exception as exc:
            import traceback
            print(f"[Notification ERROR] type={notification_type} user_id={getattr(user, 'id', '?')} error={exc}")
            traceback.print_exc()

    @staticmethod
    def notify_all_parties(contract, notification_type, exclude_user=None, message=''):
        """Send notification to all ContractParty records except who triggered it.
        Used by the legacy API views (ApproveView, SignView, CancelView)."""
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

    @staticmethod
    def notify_contract_stakeholders(contract, notification_type, exclude_user=None, message=''):
        """Notify the contract creator + all invitees who have linked a Mithaq account.
        Use this for invitation-based flows where parties are SigningInvitation records."""
        notified_ids = set()

        # Notify the contract creator
        if not exclude_user or contract.creator_id != exclude_user.id:
            NotificationService.notify(contract.creator, notification_type, contract, message)
            notified_ids.add(contract.creator_id)

        # Notify invitees who have linked their account (invitee_user is set)
        for inv in contract.signing_invitations.filter(
            invitee_user__isnull=False
        ).select_related('invitee_user'):
            uid = inv.invitee_user_id
            if uid in notified_ids:
                continue
            if exclude_user and uid == exclude_user.id:
                continue
            NotificationService.notify(inv.invitee_user, notification_type, contract, message)
            notified_ids.add(uid)