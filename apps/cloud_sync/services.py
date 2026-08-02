from django.db import transaction

from .const import SyncStatus
from .models import CloudSyncExecution
from .tasks import sync_cloud_execution


def queue_sync(account, tenant, idempotency_key):
    with transaction.atomic():
        execution, created = CloudSyncExecution.objects.get_or_create(
            account=account,
            idempotency_key=idempotency_key,
            defaults={
                'tenant': tenant,
                'org_id': account.org_id,
                'status': SyncStatus.pending,
            },
        )
        if created:
            execution_id = str(execution.id)
            tenant_id = str(tenant.id)
            transaction.on_commit(
                lambda: sync_cloud_execution.delay(execution_id, tenant_id)
            )
    return execution, created
