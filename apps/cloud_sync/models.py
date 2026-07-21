from django.db import models
from django.utils.translation import gettext_lazy as _

from common.db.fields import EncryptJsonDictTextField
from orgs.mixins.models import JMSOrgBaseModel
from .const import CloudProvider, SyncStatus, HostnameStrategy


class CloudSyncAccount(JMSOrgBaseModel):
    """AWS/Azure gibi bir bulut hesabi; envanteri Yetka'ya asset olarak senkronlar."""
    name = models.CharField(max_length=128, verbose_name=_('Name'))
    provider = models.CharField(
        max_length=16, choices=CloudProvider.choices, verbose_name=_('Provider')
    )
    # AWS: {access_key_id, secret_access_key}
    # Azure: {tenant_id, client_id, client_secret, subscription_id}
    credentials = EncryptJsonDictTextField(default=dict, verbose_name=_('Credentials'))
    regions = models.JSONField(default=list, blank=True, verbose_name=_('Regions'))
    node = models.ForeignKey(
        'assets.Node', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='cloud_sync_accounts', verbose_name=_('Target node')
    )
    platform = models.ForeignKey(
        'assets.Platform', null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name=_('Default platform')
    )
    hostname_strategy = models.CharField(
        max_length=32, choices=HostnameStrategy.choices,
        default=HostnameStrategy.instance_name, verbose_name=_('Hostname strategy')
    )
    use_public_ip = models.BooleanField(default=False, verbose_name=_('Use public IP'))
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    date_last_sync = models.DateTimeField(null=True, blank=True, verbose_name=_('Last sync'))
    comment = models.TextField(blank=True, default='', verbose_name=_('Comment'))

    class Meta:
        verbose_name = _('Cloud sync account')
        unique_together = [('org_id', 'name')]

    def __str__(self):
        return f'{self.name}({self.provider})'


class CloudSyncedAsset(JMSOrgBaseModel):
    """account + bulut instance_id -> olusturulan asset eslesmesi (idempotent sync icin)."""
    account = models.ForeignKey(
        CloudSyncAccount, on_delete=models.CASCADE, related_name='synced_assets'
    )
    instance_id = models.CharField(max_length=256, verbose_name=_('Instance ID'))
    asset = models.ForeignKey(
        'assets.Asset', on_delete=models.CASCADE, related_name='cloud_synced'
    )

    class Meta:
        verbose_name = _('Cloud synced asset')
        unique_together = [('account', 'instance_id')]


class CloudSyncExecution(JMSOrgBaseModel):
    account = models.ForeignKey(
        CloudSyncAccount, on_delete=models.CASCADE, related_name='executions'
    )
    status = models.CharField(
        max_length=16, choices=SyncStatus.choices, default=SyncStatus.pending
    )
    date_start = models.DateTimeField(null=True, blank=True)
    date_finished = models.DateTimeField(null=True, blank=True)
    total = models.IntegerField(default=0)
    created = models.IntegerField(default=0)
    updated = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    error = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = _('Cloud sync execution')
        ordering = ['-date_created']

    @property
    def summary(self):
        return {
            'total': self.total, 'created': self.created,
            'updated': self.updated, 'failed': self.failed,
        }
