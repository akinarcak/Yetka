from rest_framework import serializers

from orgs.mixins.serializers import BulkOrgResourceModelSerializer
from .models import CloudSyncAccount, CloudSyncExecution


class CloudSyncAccountSerializer(BulkOrgResourceModelSerializer):
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
