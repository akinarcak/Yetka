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

## Test asset

The shared test server carries a disposable asset, `yetka-smoke-localhost`
(127.0.0.1:22, CareOnCloud workspace, account `test`), created solely for
connectivity smoke tests. Yetka's own connectivity automation reports `ok`
against it. Delete it before the workspace is used for anything real:

```
Host.objects.get(name="yetka-smoke-localhost").delete()
```

## Known limitation

A browser-driven Luna terminal session still needs an operator login; the
automated checks above cover the connection path up to that point but do not
replace a human opening a session in the UI.
