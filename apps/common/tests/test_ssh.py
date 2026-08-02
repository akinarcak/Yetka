from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from common.ssh import configure_ssh_client, known_hosts_file


class SSHHostKeyPolicyTests(SimpleTestCase):
    def test_default_policy_loads_pinned_file_and_rejects_unknown_hosts(self):
        client = Mock()
        with TemporaryDirectory() as directory:
            known_hosts = Path(directory) / 'known_hosts'
            known_hosts.write_text('')
            configure_ssh_client(client, known_hosts)

        client.load_system_host_keys.assert_called_once_with()
        client.load_host_keys.assert_called_once_with(str(known_hosts))
        client.set_missing_host_key_policy.assert_called_once()
        policy = client.set_missing_host_key_policy.call_args.args[0]
        self.assertIsInstance(policy, __import__('paramiko').RejectPolicy)

    def test_missing_pinned_file_still_fails_closed(self):
        client = Mock()
        configure_ssh_client(client, '/path/that/cannot/be/a/known_hosts/file')

        client.load_system_host_keys.assert_called_once_with()
        client.load_host_keys.assert_not_called()
        policy = client.set_missing_host_key_policy.call_args.args[0]
        self.assertIsInstance(policy, __import__('paramiko').RejectPolicy)

    def test_weaker_policy_requires_explicit_opt_in(self):
        client = Mock()
        with patch('common.ssh.Path.is_file', return_value=False):
            configure_ssh_client(client, allow_unpinned=True)

        policy = client.set_missing_host_key_policy.call_args.args[0]
        self.assertIsInstance(policy, __import__('paramiko').WarningPolicy)

    @override_settings(SSH_KNOWN_HOSTS_FILE='/run/yetka/known_hosts')
    def test_configured_path_is_used(self):
        self.assertEqual(known_hosts_file(), '/run/yetka/known_hosts')
