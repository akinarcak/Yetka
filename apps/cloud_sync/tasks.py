from celery import shared_task
from django.utils.translation import gettext_lazy as _

from orgs.utils import tmp_to_root_org
from tenants.context import tenant_context
from .models import CloudSyncAccount, CloudSyncExecution
from .sync import run_sync


@shared_task(verbose_name=_('Cloud sync execution'))
def sync_cloud_execution(execution_id, tenant_id):
    with tmp_to_root_org():
        execution = CloudSyncExecution.objects.select_related('account').filter(
            id=execution_id,
            tenant_id=tenant_id,
            account__tenant_id=tenant_id,
        ).first()
    if not execution:
        return
    with tenant_context(execution.tenant):
        return run_sync(execution.account, execution=execution).status


@shared_task(verbose_name=_('Cloud sync instances'))
def sync_cloud_account(account_id, tenant_id):
    with tmp_to_root_org():
        account = CloudSyncAccount.objects.filter(
            id=account_id, tenant_id=tenant_id, is_active=True,
        ).first()
    if not account:
        return
    with tenant_context(account.tenant):
        return run_sync(account).status


@shared_task(verbose_name=_('Cloud sync all active accounts'))
def sync_all_cloud_accounts():
    with tmp_to_root_org():
        accounts = list(
            CloudSyncAccount.objects.filter(
                is_active=True, tenant__is_active=True,
            ).select_related('tenant')
        )
    for account in accounts:
        with tenant_context(account.tenant):
            sync_cloud_account.delay(str(account.id), str(account.tenant_id))
