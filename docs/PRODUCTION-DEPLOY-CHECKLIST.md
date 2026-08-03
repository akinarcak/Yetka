# Yetka production deploy checklist

## Release

- Tag: `yetka-1.0.6-final-ws`
- Verify installer checksums and image/source locks before rollout.
- Take PostgreSQL and Redis backups.
- Confirm free disk space and maintenance window.

## Pre-flight

- `systemctl is-active yetka-web yetka-worker yetka-scheduler yetka-koko`
- `curl -fsS http://127.0.0.1:8080/api/health/`
- Run `/usr/local/bin/yetka-run-tests` and require all tests to pass.
- Confirm `/opt/yetka/koko/server.crt` and `server.key` exist with key mode `0600`.

## Smoke test

- Login, switch Turkish language, open dashboard and verify notification WebSocket.
- Open Luna terminal and verify the terminal UI WebSocket.
- With a non-production test asset, create a session and verify connect/disconnect.
- Check Koko logs for `Start ws client success` and absence of current certificate errors.

## Rollback

- Restore the previous installer environment file and rerun the installer.
- If a source checkout is dirty, preserve it with `git stash push -m pre-rollback` before updating.
- Re-run health, service, and smoke checks after rollback.

## Known limitation

The shared test server currently has no registered asset, so a real asset session must be supplied before declaring end-to-end terminal connectivity complete.
