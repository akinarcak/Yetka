from celery import shared_task
from django.utils.translation import gettext_lazy as _

from orgs.utils import tmp_to_root_org
from .models import CloudSyncAccount
from .sync import run_sync


@shared_task(verbose_name=_('Cloud sync instances'))
def sync_cloud_account(account_id):
    with tmp_to_root_org():
        account = CloudSyncAccount.objects.filter(id=account_id).first()
    if not account:
        return
    return run_sync(account).status


@shared_task(verbose_name=_('Cloud sync all active accounts'))
def sync_all_cloud_accounts():
    with tmp_to_root_org():
        ids = list(CloudSyncAccount.objects.filter(is_active=True).values_list('id', flat=True))
    for aid in ids:
        sync_cloud_account(aid)
