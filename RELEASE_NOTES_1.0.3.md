# Yetka 1.0.3

## Updater reliability

- Waits up to two minutes for the web service to become healthy after restart.
- Restores the stable installation environment path after the target installer
  finishes instead of retaining its temporary preflight file.
- Restores the previous release marker when application rollback is required.
