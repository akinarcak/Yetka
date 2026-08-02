# Yetka 1.0.2

## Administrator update action

- Adds a **Güncellemeleri al** button to the maintenance warning for system
  administrators on bare-metal installations.
- Requires an explicit browser confirmation and a CSRF-protected request.
- Queues only the latest release already returned by the server-side maintenance
  check; arbitrary versions and commands are rejected.
- Keeps root privileges outside the web process. A root-owned systemd path unit
  validates the queued version and invokes the existing updater.
- Preserves checksum verification, database and data backups, rollback, exclusive
  locking and post-update health checks.
- Correctly recognizes `yetka-*` release tags and reads the installed Yetka
  release marker instead of comparing against the upstream application version.

Container and HA deployments continue to show the verified host command because
their rollout must be coordinated by the host or CI system.
