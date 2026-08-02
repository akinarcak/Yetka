# -*- coding: utf-8 -*-
#
import hmac
import hashlib
import time

from django.conf import settings
from django.core.cache import cache
from rest_framework import permissions


class IsValidUser(permissions.IsAuthenticated):
    """Allows access to valid user, is active and not expired"""

    def has_permission(self, request, view):
        return super().has_permission(request, view) \
            and request.user.is_valid


class OnlySuperUser(IsValidUser):
    def has_permission(self, request, view):
        return super().has_permission(request, view) \
            and request.user.is_superuser


class OnlyAdminSuperUser(IsValidUser):
    def has_permission(self, request, view):
        return super().has_permission(request, view) \
            and request.user.is_superuser \
            and request.user.username == 'admin'


class IsServiceAccount(IsValidUser):
    def has_permission(self, request, view):
        return super().has_permission(request, view) \
            and request.user.is_service_account


class WithBootstrapToken(permissions.BasePermission):
    def check_can_register(self):
        enabled = settings.SECURITY_SERVICE_ACCOUNT_REGISTRATION
        if enabled == 'auto':
            if cache.get(f'APPLET_HOST_DELOYING'):
                return True
            return time.time() - settings.JUMPSERVER_UPTIME < 300
        elif enabled:
            return True
        else:
            return False

    def has_permission(self, request, view):
        authorization = request.META.get('HTTP_AUTHORIZATION', '')
        if not authorization:
            return False

        if not self.check_can_register():
            return False

        request_bootstrap_token = authorization.split()[-1]
        return hmac.compare_digest(
            settings.BOOTSTRAP_TOKEN.encode(),
            request_bootstrap_token.encode()
        )


class ServiceAccountSignaturePermission(permissions.BasePermission):
    window_seconds = 30

    @staticmethod
    def _request_body(request):
        body = getattr(request, 'body', b'') or b''
        return body if isinstance(body, bytes) else str(body).encode()

    @classmethod
    def _canonical_request(cls, request, timestamp, nonce, tenant_id):
        body_digest = hashlib.sha256(cls._request_body(request)).hexdigest()
        method = getattr(request, 'method', '').upper()
        path = request.get_full_path()
        return '\n'.join((method, path, body_digest, str(timestamp), nonce, tenant_id))

    def _verify_v2(self, request, ak, data):
        parts = data.split(':', 5)
        if len(parts) != 6:
            return False
        ak_id, timestamp, nonce, tenant_id, algorithm, signature = parts
        if str(ak.id) != ak_id or algorithm.lower() != 'hmac-sha256':
            return False
        if not timestamp.isdigit() or not nonce or not tenant_id or not signature:
            return False
        if abs(int(time.time()) - int(timestamp)) > self.window_seconds:
            return False

        request_tenant = getattr(request, 'customer_tenant', None)
        expected_tenant = str(request_tenant.id) if request_tenant is not None else '-'
        if not hmac.compare_digest(expected_tenant, tenant_id):
            return False

        canonical = self._canonical_request(request, timestamp, nonce, tenant_id)
        expected = hmac.new(
            str(ak.secret).encode(), canonical.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature.lower()):
            return False
        nonce_key = f'jms-service-signature:v2:{ak_id}:{nonce}'
        return cache.add(nonce_key, True, timeout=self.window_seconds + 1)

    def _verify_legacy(self, ak_id, ak, time_sign):
        from common.utils.crypto import get_aes_crypto
        if not getattr(settings, 'SECURITY_SERVICE_SIGNATURE_ALLOW_LEGACY', False):
            return False
        aes = get_aes_crypto(str(ak.secret).replace('-', ''), mode='ECB')
        timestamp = aes.decrypt(time_sign)
        if not timestamp or not timestamp.isdigit():
            return False
        if abs(int(time.time()) - int(timestamp)) > self.window_seconds:
            return False
        nonce_key = f'jms-service-signature:{ak_id}:{time_sign}'
        return cache.add(nonce_key, True, timeout=self.window_seconds + 1)

    def has_permission(self, request, view):
        from authentication.models import AccessKey
        signature = request.META.get('HTTP_X_JMS_SVC', '')
        if not signature or not (signature.startswith('SignV2 ') or signature.startswith('Sign ')):
            return False
        is_v2 = signature.startswith('SignV2 ')
        data = signature[7:].strip() if is_v2 else signature[5:].strip()
        if not data or ':' not in data:
            return False
        ak_id = data.split(':', 1)[0]
        if not ak_id:
            return False
        ak = AccessKey.objects.filter(id=ak_id).first()
        if not ak or not ak.is_active:
            return False
        if not ak.user or not ak.user.is_active or not ak.user.is_service_account:
            return False
        try:
            if is_v2:
                return self._verify_v2(request, ak, data)
            return self._verify_legacy(ak_id, ak, data.split(':', 1)[1])
        except Exception:
            return False

    def has_object_permission(self, request, view, obj):
        return False


class IsValidLicense(permissions.BasePermission):

    def has_permission(self, request, view):
        # Yetka: lisans-kapılı API'ler (parola rotasyonu/change_secret, hesap kontrolü,
        # raporlar, custom RBAC rolleri, multi-org) açık kaynakta serbest.
        # Bunların hiçbiri kapalı EE connector binary'si gerektirmez.
        return True


class IsValidLicenseForWriteAction(permissions.BasePermission):
    """Allow read for all, require valid license for write operations"""

    def has_permission(self, request, view):
        # Yetka: yazma işlemleri de açık kaynakta serbest (multi-org, RBAC role binding)
        return True


class IsOwnerOrAdminWritable(IsValidUser):
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return super().has_permission(request, view)
        if request.method != 'GET' and obj.creator != request.user:
            return False
        return super().has_permission(request, view)
