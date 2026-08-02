import base64
import hashlib
import hmac
import re
from email.utils import parsedate_to_datetime
from datetime import timezone as datetime_timezone

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework import authentication
from rest_framework import exceptions

from httpsig import HeaderVerifier, utils

"""
Reusing failure exceptions serves several purposes:

    1. Lack of useful information regarding the failure inhibits attackers
    from learning about valid keyIDs or other forms of information leakage.
    Using the same actual object for any failure makes preventing such
    leakage through mistakenly-distinct error messages less likely.

    2. In an API scenario, the object is created once and raised many times
    rather than generated on every failure, which could lead to higher loads
    or memory usage in high-volume attack scenarios.

"""
FAILED = exceptions.AuthenticationFailed('Invalid signature.')
IP_NOT_ALLOW = exceptions.AuthenticationFailed('Ip is not in access ip list.')


class SignatureAuthentication(authentication.BaseAuthentication):
    """
    DRF authentication class for HTTP Signature support.

    You must subclass this class in your own project and implement the
    `fetch_user_data(self, keyId, algorithm)` method, returning a tuple of
    the User object and a bytes object containing the user's secret. Note
    that key_id and algorithm are DIRTY as they are supplied by the client
    and so must be verified in your subclass!

    You may set the following class properties in your subclass to configure
    authentication for your particular use case:

    :param www_authenticate_realm:  Default: "api"
    :param required_headers:        Default: ["(request-target)", "date"]
    """
    source = ''
    www_authenticate_realm = "api"
    required_headers = ["(request-target)", "date"]

    def get_required_headers(self, request, fields):
        return self.required_headers

    def validate_verified_request(self, request, fields, key_id, user):
        """Apply authentication-profile checks after the HTTP HMAC verifies."""
        return None

    def fetch_user_data(self, key_id, algorithm=None):
        """Returns a tuple (User, secret) or (None, None)."""
        raise NotImplementedError()

    def is_ip_allow(self, key_id, request):
        raise NotImplementedError()

    def after_authenticate_update_date(self, user):
        pass

    def authenticate_header(self, request):
        """
        DRF sends this for unauthenticated responses if we're the primary
        authenticator.
        """
        h = " ".join(self.required_headers)
        return 'Signature realm="%s",headers="%s"' % (
            self.www_authenticate_realm, h)

    def authenticate(self, request):
        """
        Perform the actual authentication.

        Note that the exception raised is always the same. This is so that we
        don't leak information about in/valid keyIds and other such useful
        things.
        """
        auth_header = authentication.get_authorization_header(request)
        if not auth_header or len(auth_header) == 0:
            return None

        method, fields = utils.parse_authorization_header(auth_header)

        # Ignore foreign Authorization headers.
        if method.lower() != 'signature':
            return None

        if self.source and request.META.get('HTTP_X_SOURCE') != self.source:
            return None

        # Verify basic header structure.
        if len(fields) == 0:
            raise FAILED

        # Ensure all required fields were included.
        if len({"keyid", "algorithm", "signature"} - set(fields.keys())) > 0:
            raise FAILED

        key_id = fields["keyid"]
        # Fetch the secret associated with the keyid
        user, secret = self.fetch_user_data(
            key_id,
            algorithm=fields["algorithm"]
        )

        if not (user and secret):
            raise FAILED

        if not self.is_ip_allow(key_id, request):
            raise IP_NOT_ALLOW

        # Gather all request headers and translate them as stated in the Django docs:
        # https://docs.djangoproject.com/en/1.6/ref/request-response/#django.http.HttpRequest.META
        headers = {}
        for key in request.META.keys():
            if key.startswith("HTTP_") or \
                    key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
                header = key[5:].lower().replace('_', '-')
                headers[header] = request.META[key]

        try:
            required_headers = self.get_required_headers(request, fields)
            hs = HeaderVerifier(
                headers,
                secret,
                required_headers=required_headers,
                method=request.method.lower(),
                path=request.get_full_path()
            )
            if not hs.verify():
                raise FAILED
            self.validate_verified_request(request, fields, key_id, user)
        except exceptions.AuthenticationFailed:
            raise
        except Exception:
            raise FAILED

        self.after_authenticate_update_date(user)
        return user, fields["keyid"]


class ReplayResistantServiceSignatureMixin:
    """Strict HTTP-signature profile for machine-to-machine integrations."""

    legacy_required_headers = ["(request-target)", "date"]
    strict_required_headers = [
        "(request-target)", "date", "digest", "x-jms-nonce",
        "x-jms-org", "x-yetka-tenant",
    ]
    nonce_pattern = re.compile(r'^[A-Za-z0-9._~-]{16,128}$')

    @staticmethod
    def _signed_headers(fields):
        return {
            value.lower() for value in fields.get('headers', 'date').split()
        }

    def _is_strict(self, fields):
        return set(self.strict_required_headers).issubset(
            self._signed_headers(fields)
        )

    def get_required_headers(self, request, fields):
        if fields.get('algorithm', '').lower() != 'hmac-sha256':
            raise FAILED
        if self._is_strict(fields):
            return self.strict_required_headers
        if getattr(settings, 'SECURITY_SERVICE_SIGNATURE_ALLOW_LEGACY', False):
            return self.legacy_required_headers
        raise FAILED

    @staticmethod
    def _window_seconds():
        value = int(getattr(
            settings, 'SECURITY_SERVICE_SIGNATURE_WINDOW_SECONDS', 30
        ))
        if value < 1 or value > 300:
            raise FAILED
        return value

    def validate_verified_request(self, request, fields, key_id, user):
        if not self._is_strict(fields):
            return None

        window = self._window_seconds()
        try:
            signed_at = parsedate_to_datetime(request.META['HTTP_DATE'])
            if signed_at.tzinfo is None:
                signed_at = signed_at.replace(tzinfo=datetime_timezone.utc)
            age = abs((timezone.now() - signed_at).total_seconds())
        except (KeyError, TypeError, ValueError, OverflowError):
            raise FAILED
        if age > window:
            raise FAILED

        digest = request.META.get('HTTP_DIGEST', '')
        algorithm, separator, supplied_digest = digest.partition('=')
        if not separator or algorithm.lower() != 'sha-256':
            raise FAILED
        body = getattr(request, 'body', b'') or b''
        if not isinstance(body, bytes):
            body = str(body).encode()
        expected_digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
        if not hmac.compare_digest(expected_digest, supplied_digest):
            raise FAILED

        nonce = request.META.get('HTTP_X_JMS_NONCE', '')
        org_id = request.META.get('HTTP_X_JMS_ORG', '')
        tenant_id = request.META.get('HTTP_X_YETKA_TENANT', '')
        if not self.nonce_pattern.fullmatch(nonce) or not org_id or not tenant_id:
            raise FAILED
        if not hmac.compare_digest(str(user.org_id), org_id):
            raise FAILED

        request_tenant = getattr(request, 'customer_tenant', None)
        if request_tenant is not None and not hmac.compare_digest(
                str(request_tenant.id), tenant_id):
            raise FAILED

        from tenants.models import TenantOrganization
        if not TenantOrganization.objects.filter(
                tenant_id=tenant_id, organization_id=org_id).exists():
            raise FAILED

        nonce_material = f'{key_id}\0{tenant_id}\0{nonce}'.encode()
        nonce_hash = hashlib.sha256(nonce_material).hexdigest()
        nonce_key = f'jms-service-http-signature:v2:{nonce_hash}'
        if not cache.add(nonce_key, True, timeout=window + 1):
            raise FAILED
        return None
