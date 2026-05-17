from django.conf import settings
from django.db import transaction
from twilio.rest import Client
from .models import SigningInvitation


class SigningInvitationService:

    @staticmethod
    def build_sms_message(invitation):
        contract = invitation.contract

        role = invitation.get_signing_role_display()
        order = invitation.signing_order

        custom_message = ""
        if invitation.invitation_message:
            custom_message = f"\nملاحظة: {invitation.invitation_message}"

        return (
            f"ميثاق:\n"
            f"لديك طلب توقيع جديد.\n"
            f"العقد: {contract.title_ar}\n"
            f"الدور: {role}\n"
            f"ترتيب التوقيع: {order}\n"
            f"رقم الطلب: {invitation.reference_number}"
            f"{custom_message}\n"
            f"يرجى مراجعة العقد والتوقيع."
        )

    @staticmethod
    def send_sms(mobile, message):

        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )

        sms = client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=mobile
        )

        return {
            "success": True,
            "provider": "twilio",
            "message_id": sms.sid,
        }

    @classmethod
    @transaction.atomic
    def send_existing_invitation(cls, invitation):

        message = cls.build_sms_message(invitation)

        try:
            sms_result = cls.send_sms(
                mobile=invitation.signer_mobile,
                message=message
            )

            invitation.mark_as_sent(
                message=message,
                provider=sms_result["provider"],
                provider_message_id=sms_result["message_id"],
            )

        except Exception as error:

            invitation.mark_as_failed(str(error))

            raise error

        return invitation