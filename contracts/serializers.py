from rest_framework import serializers
from contracts.models import (
    Contract, ContractVersion, ContractClause, ContractParty
)
from signatures.models import Signature


class ClauseSerializer(serializers.ModelSerializer):
    id          = serializers.UUIDField(read_only=True)
    order_index = serializers.IntegerField(read_only=True)  # ← أضف read_only=True

    class Meta:
        model  = ContractClause
        fields = [
            'id', 'order_index', 'clause_type',
            'title_ar', 'title_en',
            'content_ar', 'content_en',
        ]

    def validate_content_ar(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('محتوى البند لا يمكن أن يكون فارغاً')
        if len(value.strip()) < 10:
            raise serializers.ValidationError('محتوى البند قصير جداً — 10 أحرف على الأقل')
        return value.strip()


class ContractPartySerializer(serializers.ModelSerializer):
    id       = serializers.UUIDField(read_only=True)
    user_id  = serializers.UUIDField(source='user.id', read_only=True)
    name     = serializers.CharField(source='user.full_name', read_only=True)
    email    = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model  = ContractParty
        fields = [
            'id', 'user_id', 'name', 'email',
            'role', 'approval_status', 'approved_at', 'joined_at',
        ]


class ContractVersionSerializer(serializers.ModelSerializer):
    id      = serializers.UUIDField(read_only=True)
    clauses = ClauseSerializer(many=True, read_only=True)

    class Meta:
        model  = ContractVersion
        fields = [
            'id', 'version_number', 'change_summary',
            'created_at', 'clauses',
        ]


class SignatureSerializer(serializers.ModelSerializer):
    id        = serializers.UUIDField(read_only=True)
    signer_id = serializers.UUIDField(source='signer.id', read_only=True)
    name      = serializers.CharField(source='signer.full_name', read_only=True)

    class Meta:
        model  = Signature
        fields = [
            'id', 'signer_id', 'name',
            'signed_hash', 'signed_at', 'ip_address',
        ]


class ContractSerializer(serializers.ModelSerializer):
    id              = serializers.UUIDField(read_only=True)
    creator_id      = serializers.UUIDField(source='creator.id', read_only=True)
    creator_name    = serializers.CharField(source='creator.full_name', read_only=True)
    parties         = ContractPartySerializer(many=True, read_only=True)
    current_version = ContractVersionSerializer(read_only=True)
    signatures      = SignatureSerializer(many=True, read_only=True)

    class Meta:
        model  = Contract
        fields = [
            'id', 'title_ar', 'title_en',
            'description_ar', 'description_en',
            'status', 'creator_id', 'creator_name',
            'canonical_hash', 'created_at', 'updated_at', 'completed_at',
            'parties', 'current_version', 'signatures',
        ]
        read_only_fields = [
            'id', 'status', 'canonical_hash',
            'created_at', 'updated_at', 'completed_at',
        ]


class ContractCreateSerializer(serializers.Serializer):
    """للإنشاء فقط — مش للعرض"""
    title_ar       = serializers.CharField(max_length=255)
    title_en       = serializers.CharField(max_length=255, required=False, allow_blank=True)
    description_ar = serializers.CharField(required=False, allow_blank=True)
    description_en = serializers.CharField(required=False, allow_blank=True)
    contract_type  = serializers.ChoiceField(
                         choices=Contract.ContractType.choices,
                         required=False,
                         allow_blank=True,
                     )
    contract_html  = serializers.CharField(required=False, allow_blank=True)
    clauses        = ClauseSerializer(many=True)

    def validate_clauses(self, value):
        if not value:
            raise serializers.ValidationError('العقد يجب أن يحتوي على بند واحد على الأقل')
        return value