from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from django.utils.html import strip_tags

from twilio.rest import Client

from .models import SigningInvitation


class SigningInvitationService:

    @staticmethod
    def build_invitation_link(secret):

        path = reverse(

            "invitations:access_invitation",

            kwargs={"secret": secret}

        )

        base_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8000")

        return f"{base_url}{path}"
    @staticmethod
    def build_email_subject(invitation):
        return f"طلب توقيع عقد جديد: {invitation.contract.title_ar}"
    
    @staticmethod
    def build_email_html(invitation, secret):
        invitation_link = SigningInvitationService.build_invitation_link(secret)
        contract = invitation.contract
        role = invitation.get_signing_role_display()

        return f"""
        <div dir="rtl" style="font-family:Arial,Tahoma,sans-serif;background:#24231f;padding:32px;">
            <div style="max-width:620px;margin:auto;background:#1f2023;border:1px solid #3a3528;border-radius:22px;padding:34px;text-align:center;">
                
                <h1 style="color:#ffffff;margin:0 0 18px;">طلب توقيع عقد جديد</h1>

                <p style="color:#b8bdc9;line-height:1.9;font-size:17px;">
                    مرحبًا {invitation.signer_full_name}، لديك طلب توقيع جديد على منصة ميثاق.
                </p>

                <div style="border:1px solid #3a3528;border-radius:18px;padding:20px;margin:24px 0;color:#ffffff;">
                    <p><strong>العقد:</strong> {contract.title_ar}</p>
                    <p><strong>رقم الطلب:</strong> {invitation.reference_number}</p>
                    <p><strong>دورك:</strong> {role}</p>
                    <p><strong>ترتيب التوقيع:</strong> {invitation.signing_order}</p>
                </div>

                <p style="color:#b8bdc9;line-height:1.9;">
                    يرجى مراجعة تفاصيل العقد ثم إكمال التوقيع من خلال المنصة.
                </p>

                <a href="{invitation_link}"
                style="display:inline-block;margin-top:24px;background:#dbe6ff;color:#111827;text-decoration:none;padding:16px 30px;border-radius:16px;font-weight:bold;font-size:18px;">
                    مراجعة العقد والتوقيع
                </a>

                <p style="color:#8f95a3;font-size:13px;line-height:1.8;margin-top:26px;">
                    إذا لم يعمل الزر، انسخ الرابط التالي وافتحه في المتصفح:<br>
                    <span style="color:#dbe6ff;word-break:break-all;">{invitation_link}</span>
                </p>

            </div>
        </div>
        """

    @staticmethod
    def build_email_text(invitation, secret):
        invitation_link = SigningInvitationService.build_invitation_link(secret)

        return (
            f"مرحبًا {invitation.signer_full_name}\n\n"
            f"لديك طلب توقيع عقد جديد على منصة ميثاق.\n\n"
            f"العقد: {invitation.contract.title_ar}\n"
            f"رقم الطلب: {invitation.reference_number}\n"
            f"الرابط: {invitation_link}\n\n"
            f"يرجى مراجعة العقد والتوقيع."
        )
    
    @staticmethod
    def send_email(invitation, secret):
        if not invitation.signer_email:
            return {
                "success": False,
                "provider": "gmail","message_id": "",
                "error": "لا يوجد بريد إلكتروني لهذا الطرف",
            }

        if not secret:
            return {
                "success": False,
                "provider": "gmail",
                "message_id": "",
                "error": "رابط الدعوة غير متوفر. يرجى إعادة إنشاء الدعوة",
            }

        subject = SigningInvitationService.build_email_subject(invitation)
        html_content = SigningInvitationService.build_email_html(invitation, secret)
        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[invitation.signer_email],
        )

        email.attach_alternative(html_content, "text/html")
        email.send()

        return {
            "success": True,
            "provider": "gmail",
            "message_id": "gmail-sent",
            "error": "",
        }

    @staticmethod
    def build_sms_message(invitation):
        contract = invitation.contract
        role = invitation.get_signing_role_display()

        return (
            f"ميثاق:\n"
            f"لديك طلب توقيع جديد\n"
            f"العقد: {contract.title_ar}\n"
            f"الدور: {role}\n"
            f"رقم الطلب: {invitation.reference_number}\n"
            f"يرجى مراجعة العقد والتوقيع"
        )

    @staticmethod
    def send_sms(invitation):
        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )

        sms = client.messages.create(
            body=SigningInvitationService.build_sms_message(invitation),
            from_=settings.TWILIO_PHONE_NUMBER,
            to=invitation.signer_mobile
        )

        return {
            "success": True,
            "provider": "twilio",
            "message_id": sms.sid,
            "error": "",
        }

    @classmethod
    def send_existing_invitation(cls, invitation, secret):
        message = cls.build_email_text(invitation, secret)

        try:
            email_result = cls.send_email(invitation, secret)

            if email_result["success"]:
                invitation.mark_as_sent(
                    message=message,
                    provider=email_result["provider"],
                    provider_message_id=email_result["message_id"],
                )
                return invitation

            invitation.mark_as_failed(email_result["error"])
            return invitation

        except Exception as error:
            print("EMAIL SEND ERROR:",error)
            invitation.mark_as_failed(str(error))
            return invitation