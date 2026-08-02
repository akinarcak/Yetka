from rest_framework import serializers

from orgs.mixins.serializers import BulkOrgResourceModelSerializer
from .models import CloudSyncAccount, CloudSyncExecution, CloudSyncQuarantine
from .validation import validate_custom_endpoint


class CloudSyncAccountSerializer(BulkOrgResourceModelSerializer):
    CREDENTIAL_FIELDS = {
        'aws': {'access_key_id', 'secret_access_key', 'endpoint_url'},
        'azure': {'tenant_id', 'client_id', 'client_secret', 'subscription_id'},
        'mock': set(),
    }

    def validate_credentials(self, value):
        provider = self.initial_data.get('provider') or getattr(self.instance, 'provider', None)
        allowed = self.CREDENTIAL_FIELDS.get(provider)
        if allowed is None:
            raise serializers.ValidationError('Unsupported cloud provider.')
        unknown = set(value or {}) - allowed
        if unknown:
            raise serializers.ValidationError('Credentials contain unsupported fields.')
        required = allowed - {'endpoint_url'}
        missing = sorted(field for field in required if not str((value or {}).get(field, '')).strip())
        if missing:
            raise serializers.ValidationError(
                'Required provider credential fields are missing.'
            )
        if provider == 'aws':
            validate_custom_endpoint((value or {}).get('endpoint_url'))
        return value

    class Meta:
        model = CloudSyncAccount
        fields = [
            'id', 'name', 'provider', 'credentials', 'regions', 'node', 'platform',
            'hostname_strategy', 'use_public_ip', 'is_active', 'date_last_sync',
            'comment', 'date_created', 'date_updated',
        ]
        extra_kwargs = {
            # Credential'lar yalnizca yazilir; GET'te asla donmez
            'credentials': {'write_only': True},
            'date_last_sync': {'read_only': True},
        }


class CloudSyncExecutionSerializer(BulkOrgResourceModelSerializer):
    summary = serializers.JSONField(read_only=True)

    class Meta:
        model = CloudSyncExecution
        fields = [
            'id', 'account', 'status', 'date_start', 'date_finished',
            'total', 'created', 'updated', 'failed', 'error', 'summary',
            'date_created',
        ]
        read_only_fields = fields


class CloudSyncQuarantineSerializer(BulkOrgResourceModelSerializer):
    class Meta:
        model = CloudSyncQuarantine
        fields = [
            'id', 'account', 'execution', 'provider_object_id', 'reason_code',
            'reason_detail', 'observed', 'resolved', 'date_created', 'date_updated',
        ]
        read_only_fields = fields
