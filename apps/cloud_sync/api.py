from rest_framework.decorators import action
from rest_framework.response import Response

from orgs.mixins.api import OrgBulkModelViewSet
from .models import CloudSyncAccount, CloudSyncExecution
from .serializers import CloudSyncAccountSerializer, CloudSyncExecutionSerializer
from .providers import get_provider
from .sync import run_sync


class CloudSyncAccountViewSet(OrgBulkModelViewSet):
    model = CloudSyncAccount
    search_fields = ['name', 'provider', 'comment']
    filterset_fields = ['provider', 'is_active']
    serializer_class = CloudSyncAccountSerializer

    @action(methods=['post'], detail=True, url_path='sync')
    def sync(self, request, *args, **kwargs):
        account = self.get_object()
        execution = run_sync(account)
        return Response({'status': execution.status, **execution.summary})

    @action(methods=['post'], detail=True, url_path='test')
    def test(self, request, *args, **kwargs):
        account = self.get_object()
        try:
            get_provider(account).test()
            return Response({'ok': True})
        except Exception as e:
            return Response({'ok': False, 'error': str(e)}, status=400)


class CloudSyncExecutionViewSet(OrgBulkModelViewSet):
    model = CloudSyncExecution
    http_method_names = ['get', 'head', 'options']
    filterset_fields = ['account', 'status']
    search_fields = ['account__name']
    serializer_class = CloudSyncExecutionSerializer
