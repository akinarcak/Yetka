# SSH host-key policy

Yetka validates SSH host keys by default. Paramiko connections use
`RejectPolicy`, and command-line proxy connections use
`StrictHostKeyChecking=yes`; neither path trusts a key on first use.

The pinned file is configured by `SSH_KNOWN_HOSTS_FILE` and defaults to
`/etc/yetka/known_hosts`. Operators must provision that file through their
normal configuration-management process before enabling an SSH connector.
An absent file, an unknown host key, or a changed host key fails the
connection closed and must not be bypassed by retrying with a weaker policy.

`SSH_ALLOW_UNPINNED_HOST_KEYS` remains false by default and is reserved for a
separately audited development exception. It is not used by the production
connection paths. Legacy algorithms are also disabled by default;
`old_ssh_version` is an explicit per-asset compatibility choice and must be
reviewed before use.

## Rollback

If a planned host-key rotation causes an outage, restore the previously
validated `known_hosts` entry or deploy the new key during a maintenance
window. Do not enable first-use trust. The code change can be reverted as a
normal release rollback, but doing so reintroduces an unsafe default and is
not an acceptable operational workaround.

## Evidence

`common.ssh_tests` verifies pinned-file loading, missing-file fail-closed
behavior, explicit weaker-policy opt-in, and configured-path resolution.
The foundation CI runs these tests in the non-root, read-only container.
