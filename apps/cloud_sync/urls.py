from rest_framework_bulk.routes import BulkRouter

from . import api

app_name = 'cloud_sync'

router = BulkRouter()
router.register(r'accounts', api.CloudSyncAccountViewSet, 'cloud-sync-account')
router.register(r'executions', api.CloudSyncExecutionViewSet, 'cloud-sync-execution')
router.register(r'quarantine', api.CloudSyncQuarantineViewSet, 'cloud-sync-quarantine')

urlpatterns = router.urls
