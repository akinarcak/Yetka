# Yetka MSP Foundation 1 — Completion Report

Status: **in progress** (not release-ready)

This report is an evidence index for the foundation work. It intentionally does
not claim completion until every Definition of Done item has a passing build and
runtime proof. No customer, production system, real secret, or real customer
data was used.

## Evidence completed in this iteration

| Area | Evidence |
| --- | --- |
| Component provenance | `components.lock.yml`, immutable commit validation, `tools/validate_components_lock.py` |
| Forbidden artefacts | `tools/scan_release_artifacts.py` and `tools/tests/test_release_provenance.py` reject xpack paths |
| Release integrity | `.github/workflows/release-installer.yml` generates CycloneDX SBOM, signs `SHA256SUMS` with Cosign, and verifies the signature before upload |
| Tenant context | `apps/tenants/middleware.py`, tenant-scoped session replay lookup, WebSocket tenant binding, Celery context validation |
| SSH security | `apps/common/ssh.py`, pinned known-host policy, legacy crypto opt-in defaults, policy tests and documentation |
| Production configuration | `apps/common/security_config.py` rejects weak production secrets and unpinned SSH configuration |
| Recording | Replay upload tasks fail closed and retain local data after an unsuccessful upload (`apps/terminal/tasks.py`) |
| Service signatures | `ServiceAccountSignaturePermission` consumes a timestamp nonce once and rejects replay (`apps/common/permissions.py`) |
| Supported components | `supported-components.json` explicitly marks unsupported external components unavailable |
| Operations/governance | `NOTICE`, `docs/operations/production-checklist.md`, `docs/governance/fork-governance.md`, and `docs/security/recording-fail-closed.md` |
| Migration plan | `docs/security/tenant-migration-plan.md` defines additive phases, acceptance evidence, and rollback |
| Lina overlay removal | Lina `bd27b4221be74b53006ea879f08a61622ea03357` renders unavailable pages without the legacy blur/mask overlay; the lock and workflows pin this commit |

## Verification already run

- `python -m unittest tools.tests.test_release_provenance -v` — 6 tests passed.
- Foundation CI workflow includes tenant, Cloud Sync, SSH, security-config,
  component-manifest, recording, replay-scope, and service-signature suites.
- Release workflow is pinned to the locked Lina/Luna/Koko commits and uploads
  hashes, SBOM, signature, and signature bundle.
- Run `30755497508` passed all three jobs (container, Lina source, provenance)
  after the test-suite isolation change. The earlier failure in `30755346653`
  remains historical evidence and is not treated as a release result.
- Run `30755688032` passed all three jobs after adding release vulnerability
  and secret-scan gates. The release workflow itself still requires a tag or
  manual dispatch to produce final scan/SBOM/signature artefact evidence.
- `tools.tests.test_backup_restore_smoke` passes locally and is now part of the
  foundation provenance job; it validates an offline SQLite fixture round trip
  including tenant ownership.
- Run `30755865774` passed container, Lina source, and provenance jobs with the
  offline backup/restore smoke gate included.
- Run `30756035540` passed container, Lina source, and provenance jobs using
  the overlay-free Lina commit pinned in the current lock.

## Open gates before declaring completion

1. Obtain a green CI run for the latest WebSocket, recording, signature, and
   manifest commits, including the container test image.
2. Add and run the complete core/Lina/Luna/Koko matrix, backup/restore,
   secret/license/container scans, and SFTP audit evidence.
3. Verify source-level Lina route/menu/permission behavior and remove any
   remaining DOM overlay or mask workaround in the Lina source repository.
4. Expose the supported-component manifest through the product surface and
   prove unavailable states in Lina UI tests.
5. Finish migration/rollback, fork governance, NOTICE, production checklist,
   SSH, recording, and tenant documentation review.
6. Re-audit the Definition of Done against release artefacts and only then
   change this report to `complete` and mark the goal achieved.

## Recent implementation commits

- `3663462d6` — WebSocket customer-tenant binding
- `85d48d36e` — Celery tenant context cleanup test
- `9e2ac7aa3` — signed and verified release checksums
- `aa6b1185b` — runtime supported-component manifest
- `af40efd3d` — fail-closed replay uploads
- `3750c082b` — replay-resistant service signatures
