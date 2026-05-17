from django.contrib import admin
from .models import SigningInvitation


@admin.register(SigningInvitation)
class SigningInvitationAdmin(admin.ModelAdmin):
    list_display = (
        "reference_number",
        "contract",
        "signer_full_name",
        "signer_mobile",
        "status",
        "sent_at",
        "expires_at",
        "created_at",
    )

    list_filter = (
        "status",
        "sms_provider",
        "created_at",
        "sent_at",
    )

    search_fields = (
        "reference_number",
        "signer_full_name",
        "signer_mobile",
        "signer_email",
        "contract__title_ar",
    )

    readonly_fields = (
        "id",
        "reference_number",
        "secret_hash",
        "sms_message",
        "sms_provider",
        "sms_provider_message_id",
        "send_attempts",
        "failure_reason",
        "sent_at",
        "viewed_at",
        "signed_at",
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)