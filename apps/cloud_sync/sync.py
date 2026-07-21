import logging

from django.utils import timezone

from orgs.utils import set_current_org
from assets.models import Node, Platform
from assets.serializers.asset.host import HostSerializer
from .models import CloudSyncExecution, CloudSyncedAsset
from .providers import get_provider
from .const import SyncStatus, HostnameStrategy

logger = logging.getLogger(__name__)


def _default_platform_id(account, os_type):
    if account.platform_id:
        return account.platform_id
    name = 'Windows' if os_type == 'windows' else 'Linux'
    p = Platform.objects.filter(name=name).first() or Platform.objects.filter(name='Linux').first()
    return p.id if p else None


def _asset_name(account, inst):
    if account.hostname_strategy == HostnameStrategy.instance_id:
        return inst.instance_id
    return inst.name or inst.instance_id


def _pick_address(account, inst):
    if account.use_public_ip and inst.public_ip:
        return inst.public_ip
    return inst.private_ip or inst.public_ip


def _create_asset(account, node, inst, name):
    platform_id = _default_platform_id(account, inst.os_type)
    proto = 'rdp' if inst.os_type == 'windows' else 'ssh'
    port = 3389 if inst.os_type == 'windows' else 22
    address = _pick_address(account, inst)
    data = {
        'name': name, 'address': address,
        'platform': {'pk': platform_id},
        'nodes': [{'pk': str(node.id)}],
        'protocols': [{'name': proto, 'port': port}],
    }
    s = HostSerializer(data=data)
    if not s.is_valid():
        # isim cakismasi vb. -> instance_id ekiyle tekrar dene
        data['name'] = f'{name}-{inst.instance_id[-6:]}'
        s = HostSerializer(data=data)
        s.is_valid(raise_exception=True)
    return s.save()


def run_sync(account):
    set_current_org(account.org)
    execution = CloudSyncExecution.objects.create(
        account=account, org_id=account.org_id,
        status=SyncStatus.running, date_start=timezone.now(),
    )
    try:
        provider = get_provider(account)
        instances = provider.list_instances()
    except Exception as e:
        logger.exception('Cloud sync provider error')
        execution.status = SyncStatus.failed
        execution.error = str(e)
        execution.date_finished = timezone.now()
        execution.save()
        return execution

    node = account.node or Node.org_root()
    created = updated = failed = 0

    for inst in instances:
        address = _pick_address(account, inst)
        if not address:
            failed += 1
            continue
        name = _asset_name(account, inst)
        try:
            mapping = CloudSyncedAsset.objects.filter(
                account=account, instance_id=inst.instance_id
            ).first()
            if mapping:
                asset = mapping.asset
                fields = []
                if asset.address != address:
                    asset.address = address
                    fields.append('address')
                if asset.name != name:
                    asset.name = name
                    fields.append('name')
                if fields:
                    asset.save(update_fields=fields)
                updated += 1
            else:
                asset = _create_asset(account, node, inst, name)
                CloudSyncedAsset.objects.create(
                    account=account, org_id=account.org_id,
                    instance_id=inst.instance_id, asset=asset,
                )
                created += 1
        except Exception as e:
            logger.error('Cloud sync asset error %s: %s', inst.instance_id, e)
            failed += 1

    execution.total = len(instances)
    execution.created = created
    execution.updated = updated
    execution.failed = failed
    if failed and not (created or updated):
        execution.status = SyncStatus.failed
    elif failed:
        execution.status = SyncStatus.partial
    else:
        execution.status = SyncStatus.success
    execution.date_finished = timezone.now()
    execution.save()

    account.date_last_sync = timezone.now()
    account.save(update_fields=['date_last_sync'])
    return execution
