import re

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from orgs.mixins.api import OrgBulkModelViewSet
from tenants.api import TenantScopedQuerySetMixin
from .models import CloudSyncAccount, CloudSyncExecution, CloudSyncQuarantine
from .serializers import (
    CloudSyncAccountSerializer, CloudSyncExecutionSerializer,
    CloudSyncQuarantineSerializer,
)
from .providers import get_provider
from .services import queue_sync


IDEMPOTENCY_KEY_RE = re.compile(r'^[A-Za-z0-9._:-]{8,64}$')


class CloudSyncAccountViewSet(TenantScopedQuerySetMixin, OrgBulkModelViewSet):
    model = CloudSyncAccount
    search_fields = ['name', 'provider', 'comment']
    filterset_fields = ['provider', 'is_active']
    serializer_class = CloudSyncAccountSerializer

    @action(methods=['post'], detail=True, url_path='sync')
    def sync(self, request, *args, **kwargs):
        account = self.get_object()
        key = request.headers.get('Idempotency-Key', '')
        if not IDEMPOTENCY_KEY_RE.fullmatch(key):
            return Response(
                {'detail': 'Idempotency-Key must be 8-64 safe ASCII characters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        execution, created = queue_sync(account, request.customer_tenant, key)
        response_status = status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK
        return Response({
            'id': execution.id,
            'status': execution.status,
            'created': created,
        }, status=response_status)

    @action(methods=['post'], detail=True, url_path='test')
    def test(self, request, *args, **kwargs):
        account = self.get_object()
        try:
            get_provider(account).test()
            return Response({'ok': True})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=400)


class CloudSyncExecutionViewSet(TenantScopedQuerySetMixin, OrgBulkModelViewSet):
    model = CloudSyncExecution
    http_method_names = ['get', 'head', 'options']
    filterset_fields = ['account', 'status']
    search_fields = ['account__name']
    serializer_class = CloudSyncExecutionSerializer


class CloudSyncQuarantineViewSet(TenantScopedQuerySetMixin, OrgBulkModelViewSet):
    model = CloudSyncQuarantine
    http_method_names = ['get', 'head', 'options']
    filterset_fields = ['account', 'execution', 'reason_code', 'resolved']
    search_fields = ['provider_object_id', 'reason_detail']
    serializer_class = CloudSyncQuarantineSerializer
