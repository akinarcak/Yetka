# Yetka MSP Foundation 1 — completion report

Date: 2026-08-03, revised 2026-08-04

This report records the current evidence for each foundation Definition of
Done item. `complete` means the implementation and its scoped verification are
present. `partial` means a required production/release rehearsal is still
missing; it is not silently treated as complete.

The 2026-08-04 revision replaces the previous closing section, which asked for
a release rehearsal that had by then been superseded by real publishing
releases, and which claimed W6 was partial while the summary table above it
already said complete. It also records what the rehearsal-only evidence could
not detect. Open items are listed under "Acceptance status".

## Summary

| Workstream | Status | Evidence |
| --- | --- | --- |
| W1 tenant API isolation | complete | Core tenant/cloud-sync tests; CI `30765091779`; isolated Linux W1/W2 evidence in handoff |
| W2 worker/download/WebSocket isolation | complete | Core tenant task/session/WebSocket tests; isolated source `/var/tmp/yetka-test-source-w2`; CI `30765091779` |
| W3 recording fail-closed | complete | `docs/security/recording-fail-closed.md`; isolated source `/var/tmp/yetka-test-source-w3`, 12/12; CI `30765359991` |
| W4 replay-resistant service signatures | complete | Commits `bd20fd889`, `f261b2883`, `81f6ed243`; Linux 13/13; CI `30766199402`; services active |
| W5 runtime component manifest | complete | Commits `520337c85`, `8979b21a1`; Lina `7330bfc1748863391ad66d84dc970e5f56e2769d`; CI `30766559526` |
| W6 release gates | complete | Real publishing releases ws21 `30931942246` and ws22 `30933410923`, deployed and verified; see "What the rehearsal could not see" for the defect the earlier rehearsal-only evidence could not detect |
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

Status: complete. The gates listed below were first validated by a
non-publishing rehearsal and are now exercised by real publishing releases.
Read "What the rehearsal could not see" before treating the rehearsal evidence
as equivalent.

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

### What the rehearsal could not see (2026-08-04)

A rehearsal tag is skipped by the release-attachment guard, so no GitHub Release
is created and no tag is published. Every gate above therefore ran, but nothing
ever checked the one property that only exists on the real path: that the
published tag points at the commit the assets were built from.

It did not. `gh release create` was called without `--target`, so GitHub created
each tag on the default branch. All work since ws7 lived on
`foundation/enterprise-badge-pin-final` while `main` had not moved, so every tag
from ws7 through ws20 resolved to `1a8762e3`, the pre-ws7 `main` head. The
assets were built from the branch: the ws20 manifest records core `32276c8ca`,
whose `pyproject.toml` carries the `[tool.setuptools]` stanza, while the tagged
commit's does not. Because `install-baremetal.sh` checked out the tag, a full
updater run deployed pre-ws7 core and failed the editable install with
"multiple top-level packages". That is the rollback recorded for ws13 and again
for ws17, and it is why `HANDOFF_CLAUDE.md` and this report appeared to
contradict each other: the packaging stanza was correct and load-bearing all
along, but absent from the commit the installer actually used.

Fixed in `0ffe88ffd` and `750c33b90`: the tag is created on the built commit and
the workflow fails when an existing tag disagrees with it; the core commit and
the component archives are both resolved from `components.release.json`, which
now ships inside the installer archive and is therefore covered by `SHA256SUMS`
and the cosign signature. `tools/tests/test_release_provenance.py` guards both.

The lesson is narrower than "run a real release": a gate that validates a
process without producing its real output cannot verify the output's
properties. The rehearsal proved the pipeline runs. It could not prove the
pipeline publishes the right thing.

### Real publishing evidence

`yetka-1.0.6-final-ws21` (`0ffe88ffd`) is the first tag since ws6 to point at
real code. `yetka-1.0.6-final-ws22` (`750c33b90`) adds the component fix and is
what was deployed. Runs `30931942246` and `30933410923` passed every gate above
and published their assets.

ws22 was applied to the test host and verified: deployed core commit matches the
tag and the manifest, `/var/lib/yetka/release-version` reads
`yetka-1.0.6-final-ws22`, all five services active, `/api/health/` returns
`status`, `db_status` and `redis_status` true, Koko logs `Start ws client
success`, and `/usr/local/bin/yetka-run-tests` passes 13/13. The component pins
followed the manifest without `/etc/yetka-install.env` being edited.

## W7 — report and handoff

This report is the W7 artifact. Handoff notes are updated with W4 and W5
design/evidence records. Production/test-server application code was not
deployed by W5–W7; changes were verified in CI and local isolated/build
environments.

## Acceptance status (2026-08-04)

The previous edition of this section asked for one disposable
`workflow_dispatch` release to be recorded before the goal could close. That
item is satisfied several times over by ws21 and ws22, which published real
releases through every gate and were deployed and verified on the test host.
It should not, however, be read as the goal closing quietly: running the real
path is what exposed the tag-provenance defect described under W6, and that
defect had been shipping since ws7.

### Open

- `ansible` 9.13.0 carries `PYSEC-2026-1119` (5.5 medium, plaintext secrets in
  verbose output). Fixed in 12.2.0, but the upgrade is blocked by the
  URL-pinned `ansible-core` 2.16.19 in `[tool.uv.sources]`.
- `paramiko` 3.5.1 carries `PYSEC-2026-2858` (3.4 low, SHA-1 permitted in
  `rsakey.py`), fixed after 4.0.0. Dependabot proposes 5.0.0, a two-major
  jump in the SSH library, which wants regression coverage before it lands.
- Five dependencies are outside `pip-audit`'s reach entirely, because URL pins
  cannot be resolved to a version: `ansible-core`, `ansible-runner`,
  `django-cas-ng`, `django-radius`, `redis`. Three are third-party forks of
  authentication and Redis libraries. This is an audit blind spot, not a clean
  result.
- Browser-level verification — the notification panel's rendered Markdown and
  `document.documentElement.lang` — still needs an authenticated operator
  session. The static `index.html` cannot stand in for it, because the SPA sets
  the language at runtime.
- `yetka-1.0.6-final-ws17`, `-ws19` and `-ws20` still resolve to `1a8762e3`.
  They were deliberately left as a historical record; the workflow guard now
  fails rather than rebuilding against them.

### Security control history

The weekly `security-maintenance` workflow reported failure on every run from
2026-07-20 to 2026-08-04 without once reporting a finding: `trivy-action`
failed at job setup or while downloading its binary, the scan step was skipped,
and the job went red anyway. A control emitting no signal was indistinguishable
from one reporting vulnerabilities. Fixed in `#32` by scanning with the
digest-pinned image the release workflow already uses; `filesystem-scan` now
passes against real targets.

Its schedule also only ever ran on the default branch, which held pre-ws7 code
until 2026-08-04, so the dependency audit had been reading a `pyproject.toml`
and `uv.lock` that no release had used since ws6.

`PYSEC-2026-1325` (`ecdsa`, 7.4 high) is ignored with the reachability analysis
recorded beside the flag in `#34`: upstream considers side-channel attacks out
of scope and plans no fix, and the vulnerable signing path is not reachable
here. The exception lapses if anything begins signing with `python-ecdsa`.
