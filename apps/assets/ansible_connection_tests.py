"""The 'smart' ansible connection must not come back.

'smart' picks between the ssh and paramiko connection plugins at runtime.
ansible-core deprecated it and removes the paramiko plugin in 2.21, so both
the platform constants and the stored platform records must name 'ssh'
directly. Two surfaces are covered: what new platforms are created with, and
what the data migration did to the ones that already existed.
"""
import importlib

from django.apps import apps as django_apps
from django.test import SimpleTestCase, TestCase

from assets.const.host import HostTypes

# The module name starts with a digit, so it cannot be imported by statement.
migration = importlib.import_module(
    'assets.migrations.0021_ansible_connection_smart_to_ssh'
)


class PlatformConstantsTest(SimpleTestCase):
    def test_no_platform_type_defaults_to_smart(self):
        offenders = []
        for platform_type, constrains in HostTypes._get_automation_constrains().items():
            connection = (constrains.get('ansible_config') or {}).get('ansible_connection')
            if connection == 'smart':
                offenders.append(str(platform_type))
        self.assertEqual(
            offenders, [],
            "'smart' is deprecated in ansible-core and falls back to the "
            'paramiko plugin, removed in 2.21: ' + ', '.join(offenders),
        )

    def test_host_defaults_name_ssh(self):
        constrains = HostTypes._get_automation_constrains()
        for key in ('*', HostTypes.WINDOWS):
            with self.subTest(platform_type=key):
                self.assertEqual(
                    constrains[key]['ansible_config']['ansible_connection'], 'ssh')


class SmartConnectionMigrationTest(TestCase):
    """Exercise the 0021 data migration against real rows."""

    def _automation(self, connection):
        platform_model = django_apps.get_model('assets', 'Platform')
        automation_model = django_apps.get_model('assets', 'PlatformAutomation')
        platform = platform_model.objects.create(
            name='smoke-%s' % (connection or 'none'), category='host', type='linux')
        config = {'ansible_shell_type': 'sh'}
        if connection is not None:
            config['ansible_connection'] = connection
        return automation_model.objects.create(
            platform=platform, ansible_enabled=True, ansible_config=config)

    def test_smart_rows_become_ssh(self):
        automation = self._automation('smart')
        migration.smart_to_ssh(django_apps, None)
        automation.refresh_from_db()
        self.assertEqual(automation.ansible_config['ansible_connection'], 'ssh')
        self.assertEqual(automation.ansible_config['ansible_shell_type'], 'sh')

    def test_other_connections_are_left_alone(self):
        winrm = self._automation('winrm')
        local = self._automation('local')
        missing = self._automation(None)
        migration.smart_to_ssh(django_apps, None)
        for automation, expected in ((winrm, 'winrm'), (local, 'local')):
            automation.refresh_from_db()
            self.assertEqual(automation.ansible_config['ansible_connection'], expected)
        missing.refresh_from_db()
        self.assertNotIn('ansible_connection', missing.ansible_config)

    def test_reverse_restores_smart(self):
        automation = self._automation('smart')
        migration.smart_to_ssh(django_apps, None)
        migration.ssh_to_smart(django_apps, None)
        automation.refresh_from_db()
        self.assertEqual(automation.ansible_config['ansible_connection'], 'smart')
