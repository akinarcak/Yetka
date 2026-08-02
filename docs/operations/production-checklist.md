# Yetka MSP production checklist

This checklist is a release/operations gate, not a substitute for the CI
workflow. Do not deploy until every item is evidenced.

- [ ] Use an immutable core/component commit and verify `components.release.json`.
- [ ] Verify the SBOM, SHA-256 manifest, Cosign signature, and signature bundle.
- [ ] Run the foundation CI container, tenant-isolation, SSH, recording,
      Cloud Sync, and component-manifest suites successfully.
- [ ] Set a unique strong `SECRET_KEY` and one-time `BOOTSTRAP_TOKEN`; revoke
      the bootstrap token after registration.
- [ ] Configure an absolute pinned SSH known-hosts file. Keep legacy crypto
      disabled unless a documented exception and rollback window exist.
- [ ] Run the database backup and restore drill before first customer onboarding.
- [ ] Create and review the tenant-to-organization ownership matrix; test a
      cross-tenant API, download, job, and WebSocket request.
- [ ] Confirm replay storage upload failures are visible and local evidence is
      retained; never treat a partial recording as successfully archived.
- [ ] Confirm unsupported components are displayed as unavailable and are not
      enabled by copying upstream/enterprise files.
- [ ] Record rollback commit, migration backup, operator, and approval in the
      change record.
