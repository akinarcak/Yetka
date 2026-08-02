"""Startup validation for security-sensitive Yetka configuration."""

import os

from django.core.exceptions import ImproperlyConfigured


WEAK_VALUES = frozenset({
    '', 'changeme', 'change-me', 'please-change-me', 'secret',
    'your-secret-key', 'your-bootstrap-token', 'development key',
})


def validate_production_config(*, debug, secret_key, bootstrap_token,
                               ssh_known_hosts_file,
                               ssh_allow_unpinned_host_keys=False):
    """Reject insecure production settings before Django starts serving."""
    if debug:
        return
    if str(secret_key or '').strip().lower() in WEAK_VALUES:
        raise ImproperlyConfigured('A non-default SECRET_KEY is required when DEBUG is false.')
    if str(bootstrap_token or '').strip().lower() in WEAK_VALUES:
        raise ImproperlyConfigured('A non-default BOOTSTRAP_TOKEN is required when DEBUG is false.')
    if ssh_allow_unpinned_host_keys:
        raise ImproperlyConfigured(
            'SSH_ALLOW_UNPINNED_HOST_KEYS cannot be enabled in production.'
        )
    if not os.path.isabs(str(ssh_known_hosts_file or '')):
        raise ImproperlyConfigured('SSH_KNOWN_HOSTS_FILE must be an absolute path.')
