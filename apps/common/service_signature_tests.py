import hashlib
import hmac
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .permissions import ServiceAccountSignaturePermission


class ServiceSignatureReplayTests(SimpleTestCase):
    def setUp(self):
        self.key = SimpleNamespace(
            id='key', is_active=True,
            user=SimpleNamespace(is_active=True, is_service_account=True),
            secret='secret',
        )
        self.permission = ServiceAccountSignaturePermission()

    def request(self, body=b'payload', tenant='tenant-a', nonce='nonce', timestamp='100'):
        request = SimpleNamespace(
            META={}, method='POST', body=body,
            customer_tenant=SimpleNamespace(id=tenant),
            get_full_path=lambda: '/api/v1/service/?mode=sync',
        )
        digest = hashlib.sha256(body).hexdigest()
        canonical = '\n'.join((
            'POST', '/api/v1/service/?mode=sync', digest,
            timestamp, nonce, tenant,
        ))
        signature = hmac.new(
            self.key.secret.encode(), canonical.encode(), hashlib.sha256
        ).hexdigest()
        request.META['HTTP_X_JMS_SVC'] = (
            f'SignV2 key:{timestamp}:{nonce}:{tenant}:hmac-sha256:{signature}'
        )
        return request

    @patch('common.permissions.cache')
    @patch('authentication.models.AccessKey.objects')
    def test_v2_signature_is_bound_and_nonce_consumed_once(self, access_keys, cache):
        access_keys.filter.return_value.first.return_value = self.key
        cache.add.side_effect = [True, False]
        request = self.request()
        with patch('common.permissions.time.time', return_value=100):
            self.assertTrue(self.permission.has_permission(request, None))
            self.assertFalse(self.permission.has_permission(request, None))
        cache.add.assert_called_once_with(
            'jms-service-signature:v2:key:nonce', True, timeout=31
        )

    @patch('common.permissions.cache')
    @patch('authentication.models.AccessKey.objects')
    def test_v2_rejects_body_tampering(self, access_keys, cache):
        access_keys.filter.return_value.first.return_value = self.key
        request = self.request()
        request.body = b'attacker'
        with patch('common.permissions.time.time', return_value=100):
            self.assertFalse(self.permission.has_permission(request, None))
        cache.add.assert_not_called()

    @patch('common.permissions.cache')
    @patch('authentication.models.AccessKey.objects')
    def test_v2_rejects_cross_tenant_request(self, access_keys, cache):
        access_keys.filter.return_value.first.return_value = self.key
        request = self.request()
        request.customer_tenant = SimpleNamespace(id='tenant-b')
        with patch('common.permissions.time.time', return_value=100):
            self.assertFalse(self.permission.has_permission(request, None))
        cache.add.assert_not_called()

    @patch('authentication.models.AccessKey.objects')
    def test_v2_rejects_stale_timestamp(self, access_keys):
        access_keys.filter.return_value.first.return_value = self.key
        with patch('common.permissions.time.time', return_value=131):
            self.assertFalse(self.permission.has_permission(self.request(), None))

    @patch('common.permissions.cache')
    @patch('common.utils.crypto.get_aes_crypto')
    @patch('authentication.models.AccessKey.objects')
    def test_legacy_requires_explicit_compatibility_flag(self, access_keys, crypto, cache):
        access_keys.filter.return_value.first.return_value = self.key
        crypto.return_value.decrypt.return_value = '100'
        request = SimpleNamespace(META={'HTTP_X_JMS_SVC': 'Sign key:encrypted'})
        with patch('common.permissions.time.time', return_value=100):
            self.assertFalse(self.permission.has_permission(request, None))
            with self.settings(SECURITY_SERVICE_SIGNATURE_ALLOW_LEGACY=True):
                cache.add.return_value = True
                self.assertTrue(self.permission.has_permission(request, None))
