# Yetka AI follow-up audit

Date: 2026-08-03

## Scope

This is the productization follow-up after MSP Foundation W5-W7. It separates
required GPL/upstream attribution from product-facing names and unsupported
enterprise surfaces.

## Findings

| Area | Classification | Action/evidence |
| --- | --- | --- |
| Core Python package/module names (`jumpserver`, `JMS*`) | Required compatibility/upstream identity | Not renamed in this short audit; renaming would be a migration, not a branding edit. |
| Core LICENSE/NOTICE and README attribution | Required GPL attribution | Preserved; no removal of legal notices. |
| Core issue templates | Product-facing stale choices | Removed Community/Enterprise/Enterprise Trial choices; only Yetka open-source distribution remains (`e91444e88`). |
| Lina/Luna/Koko README product descriptions | Product-facing stale wording | Replaced direct product claims with Yetka/Upstream wording (`3b44926`, `ea04993`, `be59f37`). |
| xpack/EE code and endpoints | Unsupported surface | Existing fail-closed behavior and forbidden-content release scan retained; no endpoint or connector invented. |
| Third-party URLs, dependency names and build metadata | Upstream/build provenance | Kept for reproducibility and attribution; requires a separate repository migration before renaming. |

## Verification

- `validate_components_lock.py --lock components.lock.yml`: passed.
- `tools.tests.test_release_provenance`: 7/7 passed, including positive and
  negative forbidden-content/license/provenance checks.
- Lina full ESLint was re-run; it reports the pre-existing baseline of 6 errors
  and 209 warnings, with no changed README code involved. The authoritative
  pinned Lina build remains green in Foundation CI.
- Final release rehearsal `30769740681`: all source/container scans, Gitleaks,
  component builds, packaging, license gate, SBOM, Cosign and artifact upload
  passed; no GitHub Release was created.
- Component documentation commits were pushed independently:
  Lina `3b44926`, Luna `ea04993`, Koko `be59f37`.

## Next backlog

1. Audit runtime-visible About/help/maintenance translations for stale
   enterprise or upstream labels, with UI tests for each changed string.
2. Decide whether a future major release should rename internal `JMS`/`jumpserver`
   identifiers; do not perform that migration as a cosmetic change.
3. Add a generated allowlist distinguishing GPL attribution/build provenance
   from forbidden product-facing xpack/EE text, and enforce it in CI.
4. Run the existing isolated Linux suite after the documentation/UI changes;
   do not deploy to the customer/test server until it is green.

## Follow-up implementation evidence

- Lina removed the obsolete `/settings/license` route and dead license-page
  link (`a0d69c4`, `c53c82e`).
- CareOnCloud logo rendering now uses a cache-busted asset with explicit white,
  borderless styling (`2e6161c`).
- Enterprise badges were removed from account automation and ACL cards
  (`1ad57d8`); the cleaned Lina commit is pinned by Core PR #28.
- Foundation CI `30771066232` passed provenance, container, replay/signature,
  tenant-isolation and pinned Lina build checks.
