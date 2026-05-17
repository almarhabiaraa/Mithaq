# =============================================================================
# verification/serializers.py
# OWNED BY: Ghadi
# (added by ghadi: defines the exact shape of the verification API response)
#
# PURPOSE:
#   One read-only serializer: VerificationResultSerializer
#   It takes the dict returned by verify_contract_hash() and makes sure
#   every field is properly typed before sending it as JSON to the browser.
#
# READ-ONLY:
#   No create/update operations. The verification endpoint is GET only.
# =============================================================================

from rest_framework import serializers


class VerificationResultSerializer(serializers.Serializer):
    """
    Read-only serializer for contract verification results.
    No write operations — this serializer only validates output shape.
    Contains NO PII: no names, emails, national IDs, or clause content.
    """

    hash                    = serializers.CharField()
    verification_status     = serializers.CharField()
    contract_id             = serializers.UUIDField(allow_null=True)
    contract_status         = serializers.CharField(allow_null=True)
    signed_at               = serializers.DateTimeField(allow_null=True)
    parties_count           = serializers.IntegerField(allow_null=True)
    blockchain_tx           = serializers.CharField(allow_null=True)
    blockchain_confirmed_at = serializers.DateTimeField(allow_null=True)
    blockchain_block_number = serializers.IntegerField(allow_null=True)
