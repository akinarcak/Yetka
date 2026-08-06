"""Retire the 'smart' ansible connection on existing platform records.

'smart' dates from 0003_auto_20180109_2331 and toggles between the ssh and
paramiko connection plugins depending on whether the controller's ssh has
ControlPersist. ansible-core deprecated it, and the paramiko plugin it can
fall back to is removed in 2.21. Every controller this ships on has
ControlPersist, so 'smart' already resolves to 'ssh' and this rewrite is the
resolution made explicit rather than a change in behaviour.
"""
from django.db import migrations

OLD = 'smart'
NEW = 'ssh'


def _rewrite(apps, old, new):
    automation_model = apps.get_model('assets', 'PlatformAutomation')
    updated = []
    for automation in automation_model.objects.all().iterator():
        config = automation.ansible_config or {}
        if config.get('ansible_connection') != old:
            continue
        config['ansible_connection'] = new
        automation.ansible_config = config
        updated.append(automation)
    if updated:
        automation_model.objects.bulk_update(updated, ['ansible_config'])


def smart_to_ssh(apps, schema_editor):
    _rewrite(apps, OLD, NEW)


def ssh_to_smart(apps, schema_editor):
    _rewrite(apps, NEW, OLD)


class Migration(migrations.Migration):
    dependencies = [
        ('assets', '0020_favoritefolder'),
    ]

    operations = [
        migrations.RunPython(smart_to_ssh, ssh_to_smart),
    ]
