import ipaddress
from urllib.parse import urlsplit

from django.conf import settings
from rest_framework.exceptions import ValidationError


def validate_custom_endpoint(endpoint, allowed_endpoints=None):
    if not endpoint:
        return None
    allowed = set(
        allowed_endpoints
        if allowed_endpoints is not None
        else settings.CLOUD_SYNC_ALLOWED_ENDPOINTS
    )
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise ValidationError('Cloud endpoint is malformed') from exc
    if parsed.scheme != 'https' or not parsed.hostname:
        raise ValidationError('Cloud endpoint must use an absolute HTTPS URL')
    hostname = parsed.hostname.lower().rstrip('.')
    if hostname == 'localhost' or hostname.endswith(('.localhost', '.local')):
        raise ValidationError('Cloud endpoint must not use a local hostname')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValidationError('Cloud endpoint must not contain credentials, query, or fragment')
    if parsed.path not in ('', '/'):
        raise ValidationError('Cloud endpoint must be an origin without a path')
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ValidationError('Cloud endpoint must not use a private or local IP address')
    origin = f'https://{hostname}'
    if port and port != 443:
        origin += f':{port}'
    normalized_allowed = {item.rstrip('/').lower() for item in allowed}
    if origin not in normalized_allowed:
        raise ValidationError('Cloud endpoint is not present in the operator allowlist')
    return origin
