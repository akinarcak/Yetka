import hashlib
import hmac
import base64
from datetime import datetime, timezone
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import call, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import AuthenticationFailed

from authentication.backends.drf import ServiceAuthentication
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
        cache.add.assert_has_calls([
            call('jms-service-signature:v2:key:nonce', True, timeout=31),
            call('jms-service-signature:v2:key:nonce', True, timeout=31),
        ])
        self.assertEqual(cache.add.call_count, 2)

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


class ServiceHTTPSignatureSecurityTests(SimpleTestCase):
    strict_headers = (
        '(request-target) date digest x-jms-nonce x-jms-org x-yetka-tenant'
    )

    def setUp(self):
        self.authentication = ServiceAuthentication()
        self.integration = SimpleNamespace(id='app-key', org_id='org-a')
        self.now = datetime(2026, 8, 3, 1, 0, tzinfo=timezone.utc)

    def request(self, body=b'payload', tenant='tenant-a', org='org-a',
                nonce='request-12345678', seconds=0):
        signed_at = self.now.replace(second=seconds)
        digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
        return SimpleNamespace(
            body=body,
            customer_tenant=SimpleNamespace(id=tenant),
            META={
                'HTTP_DATE': format_datetime(signed_at, usegmt=True),
                'HTTP_DIGEST': f'SHA-256={digest}',
                'HTTP_X_JMS_NONCE': nonce,
                'HTTP_X_JMS_ORG': org,
                'HTTP_X_YETKA_TENANT': tenant,
            },
        )

    def fields(self, headers=None):
        return {
            'algorithm': 'hmac-sha256',
            'headers': headers or self.strict_headers,
        }

    @patch('common.auth.signature.cache')
    @patch('tenants.models.TenantOrganization.objects')
    def test_strict_signature_consumes_nonce_once(self, tenant_orgs, cache):
        tenant_orgs.filter.return_value.exists.return_value = True
        cache.add.side_effect = [True, False]
        request = self.request()
        with patch('common.auth.signature.timezone.now', return_value=self.now):
            self.authentication.validate_verified_request(
                request, self.fields(), 'app-key', self.integration
            )
            with self.assertRaises(AuthenticationFailed):
                self.authentication.validate_verified_request(
                    request, self.fields(), 'app-key', self.integration
                )

    @patch('common.auth.signature.cache')
    @patch('tenants.models.TenantOrganization.objects')
    def test_strict_signature_rejects_body_tampering(self, tenant_orgs, cache):
        tenant_orgs.filter.return_value.exists.return_value = True
        request = self.request()
        request.body = b'attacker'
        with patch('common.auth.signature.timezone.now', return_value=self.now):
            with self.assertRaises(AuthenticationFailed):
                self.authentication.validate_verified_request(
                    request, self.fields(), 'app-key', self.integration
                )
        cache.add.assert_not_called()

    @patch('common.auth.signature.cache')
    @patch('tenants.models.TenantOrganization.objects')
    def test_strict_signature_rejects_cross_tenant(self, tenant_orgs, cache):
        tenant_orgs.filter.return_value.exists.return_value = False
        request = self.request()
        with patch('common.auth.signature.timezone.now', return_value=self.now):
            with self.assertRaises(AuthenticationFailed):
                self.authentication.validate_verified_request(
                    request, self.fields(), 'app-key', self.integration
                )
        cache.add.assert_not_called()

    @patch('common.auth.signature.cache')
    def test_strict_signature_rejects_stale_date(self, cache):
        request = self.request()
        later = self.now.replace(minute=1)
        with patch('common.auth.signature.timezone.now', return_value=later):
            with self.assertRaises(AuthenticationFailed):
                self.authentication.validate_verified_request(
                    request, self.fields(), 'app-key', self.integration
                )
        cache.add.assert_not_called()

    def test_legacy_http_signature_requires_explicit_flag(self):
        legacy_fields = {
            'algorithm': 'hmac-sha256',
            'headers': '(request-target) date',
        }
        with self.assertRaises(AuthenticationFailed):
            self.authentication.get_required_headers(None, legacy_fields)
        with self.settings(SECURITY_SERVICE_SIGNATURE_ALLOW_LEGACY=True):
            self.assertEqual(
                self.authentication.get_required_headers(None, legacy_fields),
                ['(request-target)', 'date'],
            )

    def test_service_profile_rejects_non_hmac_algorithm(self):
        fields = self.fields()
        fields['algorithm'] = 'rsa-sha256'
        with self.assertRaises(AuthenticationFailed):
            self.authentication.get_required_headers(None, fields)

    @patch('common.auth.signature.cache')
    @patch('tenants.models.TenantOrganization.objects')
    def test_digest_and_org_comparisons_are_constant_time(
            self, tenant_orgs, cache):
        tenant_orgs.filter.return_value.exists.return_value = True
        cache.add.return_value = True
        request = self.request()
        original = hmac.compare_digest
        with patch('common.auth.signature.timezone.now', return_value=self.now), \
                patch('common.auth.signature.hmac.compare_digest', wraps=original) as compare:
            self.authentication.validate_verified_request(
                request, self.fields(), 'app-key', self.integration
            )
        self.assertGreaterEqual(compare.call_count, 3)

    @patch('common.auth.signature.HeaderVerifier')
    @patch('common.auth.signature.cache')
    @patch('tenants.models.TenantOrganization.objects')
    def test_authentication_flow_applies_strict_profile(
            self, tenant_orgs, cache, verifier):
        tenant_orgs.filter.return_value.exists.return_value = True
        cache.add.return_value = True
        verifier.return_value.verify.return_value = True
        request = self.request()
        request.method = 'POST'
        request.get_full_path = lambda: '/api/v1/service/'
        request.META.update({
            'HTTP_X_SOURCE': 'jms-pam',
            'HTTP_AUTHORIZATION': (
                'Signature keyId="app-key",algorithm="hmac-sha256",'
                f'headers="{self.strict_headers}",signature="signed"'
            ),
        })
        with patch.object(
                self.authentication, 'fetch_user_data',
                return_value=(self.integration, 'secret')), patch.object(
                self.authentication, 'is_ip_allow', return_value=True), patch.object(
                self.authentication, 'after_authenticate_update_date'), patch(
                'common.auth.signature.timezone.now', return_value=self.now):
            authenticated, key_id = self.authentication.authenticate(request)
        self.assertIs(authenticated, self.integration)
        self.assertEqual(key_id, 'app-key')
        verifier.assert_called_once()
