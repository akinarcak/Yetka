from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from common.security_config import validate_production_config


class ProductionConfigValidationTests(SimpleTestCase):
    def valid(self, **overrides):
        values = {
            'debug': False,
            'secret_key': 'ci-only-secret-not-for-production',
            'bootstrap_token': 'ci-only-bootstrap-not-for-production',
            'ssh_known_hosts_file': '/etc/yetka/known_hosts',
            'ssh_allow_unpinned_host_keys': False,
        }
        values.update(overrides)
        return validate_production_config(**values)

    def test_valid_nonproduction_secret_values_are_accepted(self):
        self.assertIsNone(self.valid())

    def test_empty_or_placeholder_secrets_are_rejected(self):
        for field in ('secret_key', 'bootstrap_token'):
            with self.subTest(field=field), self.assertRaises(ImproperlyConfigured):
                self.valid(**{field: ''})

    def test_unpinned_ssh_is_rejected_in_production(self):
        with self.assertRaises(ImproperlyConfigured):
            self.valid(ssh_allow_unpinned_host_keys=True)

    def test_relative_known_hosts_path_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            self.valid(ssh_known_hosts_file='known_hosts')

    def test_debug_mode_keeps_local_development_bootable(self):
        self.assertIsNone(self.valid(
            debug=True, secret_key='', bootstrap_token='', ssh_known_hosts_file='known_hosts'
        ))
