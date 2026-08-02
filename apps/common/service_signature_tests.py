from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from .permissions import ServiceAccountSignaturePermission


class ServiceSignatureReplayTests(TestCase):
    @patch('common.permissions.cache')
    @patch('common.utils.crypto.get_aes_crypto')
    @patch('authentication.models.AccessKey.objects')
    def test_signature_nonce_is_consumed_once(self, access_keys, crypto, cache):
        key = SimpleNamespace(
            is_active=True,
            user=SimpleNamespace(is_active=True, is_service_account=True),
            secret='secret',
        )
        access_keys.filter.return_value.first.return_value = key
        crypto.return_value.decrypt.return_value = '1'
        cache.add.side_effect = [True, False]
        request = SimpleNamespace(META={'HTTP_X_JMS_SVC': 'Sign key:encrypted'})
        permission = ServiceAccountSignaturePermission()
        with patch('common.permissions.time.time', return_value=1):
            self.assertTrue(permission.has_permission(request, None))
            self.assertFalse(permission.has_permission(request, None))
        cache.add.assert_called_once()
