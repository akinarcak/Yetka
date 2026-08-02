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
| SFTP audit | `common.sftp_audit_tests` mocks the client and verifies pinned SSH configuration occurs before SFTP connect |
| Production configuration | `apps/common/security_config.py` rejects weak production secrets and unpinned SSH configuration |
| Recording | Replay upload tasks fail closed and retain local data after an unsuccessful upload (`apps/terminal/tasks.py`) |
| Service signatures | `ServiceAccountSignaturePermission` consumes a timestamp nonce once and rejects replay (`apps/common/permissions.py`) |
| Supported components | `supported-components.json` explicitly marks unsupported external components unavailable |
| Supported components API | Authenticated `/api/v1/components/` exposes the runtime manifest without mutating status (`jumpserver.api.components_tests`) |
| Operations/governance | `NOTICE`, `docs/operations/production-checklist.md`, `docs/governance/fork-governance.md`, and `docs/security/recording-fail-closed.md` |
| Migration plan | `docs/security/tenant-migration-plan.md` defines additive phases, acceptance evidence, and rollback |
| Lina overlay removal | Lina `5b8685c01aafed3ffc2f2f0a6152a3aeb2c8c216` renders unavailable pages without the legacy blur/mask overlay or paid upgrade redirect and includes a regression test; the lock and workflows pin this commit |

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
- Run `30756175027` passed all three jobs with the Lina unavailable-page
  regression test included.
- Run `30756333731` passed all three jobs with the authenticated supported-
  components API test included.
- Run `30756478787` passed all three jobs with the product-neutral unavailable
  page and paid-upgrade redirect regression checks included.
- Run `30756669278` passed all three jobs with the mocked SFTP host-key audit
  suite included.
- Run `30756853370` passed all three jobs after adding the non-publishing
  release dry-run input and its provenance assertions.
- Run `30757561384` passed the non-publishing release dry-run end to end:
  pinned Trivy and Gitleaks scans passed, Lina/Luna/Koko builds passed, and
  SBOM/checksum/Cosign signature verification passed. The uploaded artefacts
  included `yetka-yetka-foundation-dryrun-9.sbom.cdx.json`, `SHA256SUMS`,
  `SHA256SUMS.sig`, `SHA256SUMS.sigstore.json`, and
  `components.release.json`; no GitHub release was published. The manifest
  records immutable component commits and SHA-256 hashes for all three
  component archives.
- The component matrix gate now asserts the four supported build targets,
  five explicitly unavailable components with reasons, and lock/manifest
  alignment (`tools.tests.test_component_matrix`). The offline restore smoke
  now exercises a `yetka-application-backup-v1` tar envelope containing a
  manifest and database payload, preserving tenant ownership on restore.
- Run `30758188916` passed all three foundation jobs after switching
  ansible-core 2.16.19 to its valid, hash-pinned PyPI source archive: the
  self-contained core image built and passed non-root/read-only checks plus
  tenant isolation tests, Lina source tests/build passed, and provenance,
  backup/restore, and component matrix tests passed.

## Open gates before declaring completion

1. Re-run and retain the complete core/Lina/Luna/Koko compatibility matrix,
   including
   the supported/unavailable component UI states and a restore drill against
   an application-format backup (the offline SQLite fixture is covered).
2. Re-audit the Definition of Done against release artefacts and only then
   change this report to `complete` and mark the goal achieved.

## Recent implementation commits

- `3663462d6` — WebSocket customer-tenant binding
- `85d48d36e` — Celery tenant context cleanup test
- `9e2ac7aa3` — signed and verified release checksums
- `aa6b1185b` — runtime supported-component manifest
- `af40efd3d` — fail-closed replay uploads
- `3750c082b` — replay-resistant service signatures
