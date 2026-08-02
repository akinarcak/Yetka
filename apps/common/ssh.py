"""Shared SSH host-key policy for Yetka connections.

Connections fail closed when a host key is not present in the configured
known-hosts file.  Callers must explicitly opt into any weaker policy; there
is no implicit first-use trust.
"""

import os
from pathlib import Path

import paramiko


DEFAULT_KNOWN_HOSTS_FILE = '/etc/yetka/known_hosts'


def known_hosts_file(path=None):
    if path:
        return os.fspath(path)
    try:
        from django.conf import settings
        configured = getattr(settings, 'SSH_KNOWN_HOSTS_FILE', '')
    except Exception:
        configured = ''
    return configured or os.environ.get('YETKA_SSH_KNOWN_HOSTS_FILE', DEFAULT_KNOWN_HOSTS_FILE)


def configure_ssh_client(client, known_hosts=None, allow_unpinned=False):
    """Apply Yetka's host-key policy to a Paramiko SSHClient.

    ``allow_unpinned`` is intentionally explicit and is reserved for a
    separately audited development/legacy configuration.  Production callers
    must use the default ``RejectPolicy``.
    """
    path = known_hosts_file(known_hosts)
    client.load_system_host_keys()
    if Path(path).is_file():
        client.load_host_keys(path)
    if allow_unpinned:
        client.set_missing_host_key_policy(paramiko.WarningPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    return client
