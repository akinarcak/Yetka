# Yetka MSP Foundation 1 — completion report

Date: 2026-08-03

This report records the current evidence for each foundation Definition of
Done item. `complete` means the implementation and its scoped verification are
present. `partial` means a required production/release rehearsal is still
missing; it is not silently treated as complete.

## Summary

| Workstream | Status | Evidence |
| --- | --- | --- |
| W1 tenant API isolation | complete | Core tenant/cloud-sync tests; CI `30765091779`; isolated Linux W1/W2 evidence in handoff |
| W2 worker/download/WebSocket isolation | complete | Core tenant task/session/WebSocket tests; isolated source `/var/tmp/yetka-test-source-w2`; CI `30765091779` |
| W3 recording fail-closed | complete | `docs/security/recording-fail-closed.md`; isolated source `/var/tmp/yetka-test-source-w3`, 12/12; CI `30765359991` |
| W4 replay-resistant service signatures | complete | Commits `bd20fd889`, `f261b2883`, `81f6ed243`; Linux 13/13; CI `30766199402`; services active |
| W5 runtime component manifest | complete | Commits `520337c85`, `8979b21a1`; Lina `7330bfc1748863391ad66d84dc970e5f56e2769d`; CI `30766559526` |
| W6 release gates | complete | Final non-publishing rehearsal `30769740681` passed all release gates; artifact upload succeeded and GitHub Release attachment was skipped for the rehearsal tag |
| W7 completion report | complete | This file, committed with W6/W7 delivery |

## W1–W4 evidence

The detailed test counts, isolated Linux source paths, service checks, design
decisions and rollback boundaries are maintained in
`YETKA-HANDOFF-CONTEXT.md`. The authoritative recent W4 CI run is
`30766199402`; its dedicated replay-resistant signature step propagates the
test exit code instead of relying on a later command in the same shell.

## W5 — runtime supported-components manifest

Status: complete for the scoped implementation and CI verification.

- `supported-components.json` is the runtime status authority.
- `components.lock.yml` remains the immutable external build-input authority;
  the lock and manifest matrix tests require supported `core/lina/luna/koko`
  and unavailable `lion/chen/magnus/razor/nec` entries with explanations.
- `apps/common/component_manifest.py` resolves the manifest beside `apps` in
  both source and container layouts.
- `/api/v1/components/` exposes the manifest. Lina Component Log consumes it,
  labels unavailable/unknown components, and disables tail-log actions for
  them. No fake endpoint or connector was added.
- Core matrix/provenance tests passed locally (`9/9` in the final gate set).
- CI `30766559526` passed provenance, container, manifest and manifest-aware
  Lina build steps.

## W6 — release gates

Status: complete for the non-publishing tagged-release rehearsal; production
publishing remains intentionally untested.

The release workflow now gates upload behind:

1. immutable component lock/provenance tests;
2. pinned Trivy source and release-container scans;
3. pinned Gitleaks secret scan;
4. archive forbidden-content scan for xpack/EE/enterprise paths and names;
5. GPL metadata plus LICENSE/COPYING archive validation;
6. Lina/Luna/Koko build and tests;
7. CycloneDX SBOM generation;
8. Cosign checksum signing and verification;
9. `success()` conditions on GitHub release and artifact upload.

Positive and negative gate tests are in
`tools/tests/test_release_provenance.py` and passed locally (`7/7` for the
provenance suite). Foundation CI `30767127629` also passed provenance,
container and Lina jobs after the scan fix.
The release workflow was run against `yetka-rehearsal-20260803-7` in
`30769740681`. Source/container scans, Gitleaks, component provenance, all
three component builds, packaging, license validation, SBOM generation, Cosign
signing/verification, and artifact upload passed. The release attachment step
was skipped by the rehearsal-tag guard, so no GitHub Release was created.

Earlier rehearsal `30766940681` correctly failed closed on private-key fixtures;
that led to the vulnerability-only container scan, parser-safe rehearsal-tag
guard, direct-script import fix, and explicit Lina/Luna license packaging.

## W7 — report and handoff

This report is the W7 artifact. Handoff notes are updated with W4 and W5
design/evidence records. Production/test-server application code was not
deployed by W5–W7; changes were verified in CI and local isolated/build
environments.

## Remaining acceptance item

Run one disposable, non-production `workflow_dispatch` release with
`publish_release=false` (or an equivalent isolated release rehearsal) and
record its run URL and artifact scan/signature results. Until that happens,
the overall MSP Foundation goal should remain open because W6 is explicitly
partial.
