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
- Test deployment evidence (2026-08-03): Lina production build completed with
  the legacy Webpack OpenSSL compatibility flag and was deployed to
  `/opt/yetka/lina`; Nginx configuration validated successfully. Core was
  deployed with WebSocket fixes `aa0712c47`, `27fc785ff`, `cec7a7f2a`, and
  `9f1904906`. Koko systemd now waits for Core health, and the server log
  confirms `/ws/terminal-task/` accepted followed by `Start ws client success`.
- Runtime follow-up: Lina stale enterprise UI defaults were removed in
  `8124685bd8b1205c3a7fbad177303b2d70f62053`; Core component/workflow pins now
  reference that immutable commit (`13ffeee9c`). Targeted Lina ESLint passed;
  component lock and provenance tests remain green (7/7).
- Isolated Linux test runner on the test host completed successfully after the
  runtime fixes: 13 tests, 13 passed, no system-check issues.
- Foundation CI run `30791411997` passed after the latest immutable Lina pin:
  provenance, Lina source-level policy/build, container security, replay
  signature, and customer-tenant isolation jobs all succeeded.
- Release-hardening policy tests (`tools/tests/test_product_language_policy.py`)
  pass 2/2 locally; Foundation CI PR run `30791863890` passed Lina policy/build,
  container security, provenance, replay-signature, and tenant-isolation jobs.
- `tools/verify_release.py --lina <path>` now runs the component-lock,
  provenance/security, and Lina product-language checks as one command; local
  execution passed all 9 tests and the Lina scan.
### Release policy rollout (2026-08-03)

- Pinned cleaned Luna (`315f6d26b64e99bb4b749d61a13dc549fbef3a97`) and Koko (`4a7deb7e3c2b068f959fbb1976d74e3935a3030e`) sources in the component lock and release workflow.
- `verify_release.py` now runs component-lock, provenance, product-language, and container-security policy tests before scanning each supplied component root.
- Local verification with Lina completed successfully (15 tests, product-language policy v1 clean).
- Isolated Linux test source rerun on `100.86.171.110`: 13/13 `common.service_signature_tests` passed with no system-check issues. The installed wrapper still referenced a missing temporary `yetka_test_settings`; direct execution with the repository's `jumpserver.settings.test` completed successfully.
- All three component roots now pass product-language policy v1 locally; Lina/Koko user-facing upstream branding and edition prompts were removed, while technical protocol and dependency identifiers remain explicitly allowlisted.
- Controlled deployment prep: `/usr/local/bin/yetka-run-tests` was backed up and corrected to use `jumpserver.settings.test`; the server wrapper now passes 13/13 tests with no system-check issues. `yetka-web` and `yetka-koko` are active; Core health endpoint returned HTTP 200 and the public UI returned HTTP 200. Koko `/health/` is not an exposed route (HTTP 404), so WebSocket/UI validation remains the next browser-level check.
- Browser smoke check: existing administrator session loaded the PAM dashboard; the maintenance banner showed `yetka-1.0.4 → yetka-1.0.6` with an enabled `Güncelle` button. Luna route loaded successfully and emitted no console errors/warnings. Core health and public UI remained HTTP 200.
- Update-flow smoke: dashboard `Güncelle` confirmation was accepted for `yetka-1.0.6`; UI reported `Güncelleme sıraya alındı.` Services remained active and Core health stayed HTTP 200 after the queue action. The banner remains until the updater worker applies the release, so post-apply version verification is still pending.
- Controlled update attempt result: updater downloaded and verified the `yetka-1.0.6` installer but failed while archiving live `/var/lib/yetka` logs (`tar: file changed as we read it`). The app remained on `yetka-1.0.4`, both services stayed active, and health stayed 200; no rollback was needed. Core updater patched to exclude runtime logs from the deterministic data backup; a new release artifact/CI run is required before retry.
- Recovery after failed updater retry: services briefly stopped during the installer attempt, causing the observed `Connection to websocket failed`. The application remained on `yetka-1.0.4`; `yetka-scheduler`, `yetka-worker`, `yetka-web`, and `yetka-koko` were restarted successfully, Core health returned HTTP 200, and the corrected wrapper passed 13/13 tests. The update was not declared successful.
- Root cause identified for the second update failure: the installer invoked `uv pip install -r .../pyproject.toml`, which is not a valid requirements-file input. Both install paths now use editable project installation (`uv pip install ... -e /opt/yetka/app`); CI validation is required before any further retry.
- Rehearsal deployment reached the corrected backup and dependency stages, then failed safely because setuptools rejected flat-layout editable discovery (`apps`, `data`, `deploy`, `tmp`). The host rolled back/remained on `yetka-1.0.4`; all four services and health were restored. Core now declares `[tool.setuptools.packages.find] where = ["apps"] include = ["*"]`; a fresh CI-green artifact is required before another retry.
## 2026-08-03 deployment continuation

- The updater now honors `YETKA_GIT_REF_OVERRIDE` when preparing the target environment.
- A deployment rehearsal initially rolled back because the release tag pointed at an older Core commit; a clean deploy tag (`yetka-deploy-20260803`) was published at the package-discovery fix and used for the controlled test deployment.
- Test server deployment completed successfully. All four services are active, `/api/health/` reports `status`, `db_status`, and `redis_status` true, and the permanent wrapper passes 13/13 tests with no system-check issues.
- The updater backup/rollback path remains exercised and preserved the 1.0.4 state during prior failures; the current server is running the deployed commit `yetka-deploy-20260803`.

## Follow-up goal findings

- Nginx currently forwards `/ws/` with HTTP/1.1 upgrade headers and Koko reports `Start ws client success`; this rules out a missing proxy upgrade as the primary cause.
- The browser notification socket is `/ws/notifications/site-msg/`. Its backend route is protected by `CustomerTenantWebSocketMiddleware`, which denies authenticated users when no active customer-tenant membership can be resolved. This is the leading cause to reproduce with the affected admin session before changing behavior.
- Lina currently ships `en`, `ja`, `zh`, and `zh_hant` locale bundles; there is no Turkish locale bundle. The Turkish maintenance text therefore comes from the server/update overlay rather than a consistent frontend locale.
- Lina follow-up commits `195eea3` and `31cbc3e` remove the obsolete License route/JumpServer links and add a Turkish locale fallback with the WebSocket/update/common navigation strings translated.
- Core commit `674cb7dec` permits system administrators (who are intentionally not customer-tenant members) to use notification/terminal WebSockets without weakening tenant checks for ordinary users; a regression test was added. Local execution was not available because the Windows worktree has no Django/pytest environment; it must run through the server wrapper/CI.
- Release workflow `30811456907` succeeded and produced `yetka-1.0.6-ws-tr-latest` with the Lina changes. Controlled deployment was attempted, but Koko repeatedly returned `websocket: bad handshake`; health and Core tests stayed green, while the required terminal component socket was not. The updater rollback restored `yetka-deploy-20260803`; all services are active and Koko again reports `Start ws client success`. The new WebSocket middleware change is therefore not accepted for production until the handshake regression is isolated.
- A second release (`30813156790`, `yetka-1.0.6-ws-tr2`) added an explicit service-account bypass and regression test, but produced the same Koko handshake failure. It was also rolled back to `yetka-deploy-20260803`; the live server is healthy with Koko WebSocket success. This isolates the remaining issue to the release/deploy runtime interaction rather than Core health or test coverage.
- Root cause was narrowed further: evaluating `user.is_superuser` before checking the socket path touched service-account auth on Koko connections. The fix now checks the notification path first, so only `/ws/notifications/site-msg/` can use the superuser exception. A controlled hot patch restored both signals: dashboard reload has no WebSocket error/console errors and Koko reports `Start ws client success`. Commit `1e0ad43e8` contains the ordering fix; it still needs to be included in the next release artifact.
