from unittest import TestCase
from unittest.mock import Mock, patch


class SFTPHostKeyAuditTests(TestCase):
    @patch('common.storage.jms_storage.sftp.configure_ssh_client')
    @patch('common.storage.jms_storage.sftp.paramiko.SSHClient')
    def test_sftp_storage_configures_pinned_host_keys_before_connect(self, client_cls, configure):
        client = client_cls.return_value
        client.open_sftp.return_value = Mock()
        from common.storage.jms_storage.sftp import SFTPStorage

        SFTPStorage({'SFTP_HOST': 'fixture.invalid', 'SFTP_USERNAME': 'fixture'})
        configure.assert_called_once_with(client)
        client.connect.assert_called_once()
