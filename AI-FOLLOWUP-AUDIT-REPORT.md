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
- Final release `yetka-1.0.6-final-ws` was deployed after preserving/removing the server hot-patch dirtiness. Verification: all four services active, Koko `Version yetka-1.0.6-final-ws` with `Start ws client success`, Core health/db/Redis true, and permanent wrapper 13/13 with no system-check issues. Chrome dashboard reload has no WebSocket error or console errors; the Turkish UI is active. Terminal/Luna smoke was previously confirmed loaded in Turkish.
## Final polish continuation (2026-08-03)

- Bare-metal Koko had an old startup warning because `server.crt` was absent from its systemd working directory. A scoped self-signed certificate/key pair was generated on the test server (`/opt/yetka/koko`, key mode `0600`); Koko restarted successfully and current logs show `Start ws client success`.
- Removed the remaining user-visible JumpServer documentation URL from the API-key modal and changed Koko's service description/default certificate subject to Yetka/CareonCloud.
- Added `RELEASE-NOTES-yetka-1.0.6-final-ws.md` and `docs/PRODUCTION-DEPLOY-CHECKLIST.md`.
- Real terminal connectivity is still pending a registered test asset; the shared test workspace currently reports zero assets.
- The first ws3 updater attempt rolled back safely because the tracked empty `tmp/` directory triggered setuptools flat-layout discovery. The directory was removed in commit `3d9c47fbb`; ws4 was dispatched from that fix. The rollback left all services healthy and the database backup at `/var/backups/yetka/20260803T135933Z-yetka-1.0.6-final-ws-to-yetka-1.0.6-final-ws3`.
- Closure follow-up (2026-08-04): the disposable `yetka-smoke-localhost` asset and its related host/protocol/account records were removed through the Django ORM; deletion reported 5 objects and a subsequent lookup returned zero.
- The connected Chrome session did not expose a controllable Yetka dashboard tab within the browser-control timeout, so authenticated browser-level notification WebSocket and Luna UI checks remain unverified. Server-side health, Koko WebSocket startup, and automation smoke evidence remain valid.
- Browser follow-up (2026-08-04): the authenticated Chrome dashboard tab was claimed successfully; dashboard screenshot showed the PAM dashboard and Chrome logs returned no `error` or `warn` entries. Navigating the same session to `/luna/` loaded the Turkish Web Terminal page and Chrome logs again returned no `error` or `warn` entries. No asset remained after cleanup, so opening a real terminal session from the Luna tree was not possible; the real connectivity evidence remains the earlier Yetka automation smoke test before deletion.
- WebSocket regression follow-up (2026-08-04): nginx recorded `/ws/notifications/site-msg/` as HTTP 500 while Koko and Core health remained healthy. The middleware was reading the role-backed `user.is_superuser` property directly inside async code. Commit `cbc38a19c` moves that read into `database_sync_to_async`; the focused file was hot-patched on the test server and `yetka-web` restarted. After restart, `/api/health/` returned 200, the authenticated dashboard rendered without the WebSocket error toast, Chrome returned no error/warn logs, and the notification badge populated.
- Permanent release follow-up (2026-08-04): workflow `30906934689` completed successfully for tag `yetka-1.0.6-final-ws14` with all source/container security scans, component builds, SBOM, and Cosign verification green. The first ws13 deployment was safely rolled back because its tag resolved to stale commit `1a8762e`; ws14 was explicitly tagged at Core commit `63092153d` and deployed successfully. The test server now reports `Update complete: yetka-1.0.6-final-ws14`, all four services active, health 200, and Koko `Start ws client success`. Authenticated dashboard reload after ws14 returned no Chrome error/warn logs.
- Lina follow-up commit `7657ad7` replaces the remaining user-visible JumpServer release URL in the trust-domain alert with the Yetka documentation URL. It is pushed to `yetka-v4.10.16` but is not yet in a deployable final release artifact.
- Release workflow attempts ws7/ws8 were cancelled while building `core/Dockerfile` for the security scan; no final artifact containing the latest Core/Lina changes is available. Production deployment and real terminal smoke therefore remain open.

## Release ws11 and controlled deployment (2026-08-04)

### CI blocker: root cause

The container build was never stalling. It completes in roughly 85-100 seconds
in every run that was allowed to finish:

| Run | Build step | Duration |
| --- | --- | --- |
| 30816457145 | 13:08:12 -> 13:09:41 | 1m29s |
| 30818586486 | 13:35:23 -> 13:36:47 | 1m24s |
| 30821793826 | 14:15:50 -> 14:17:15 | 1m25s |
| 30886193715 (ws11) | 07:02:54 -> 07:04:34 | 1m40s |

Runs ws7/ws8 were cancelled by hand before that point: `30824410578` was
cancelled 2m01s in, at the exact second `30824682171` was created, and
`30824682171` was then cancelled after only 57 seconds. BuildKit prints nothing
while long `RUN` layers execute, so a normal build read as a hang.

Fix (`6107d4c52`), with both Trivy scans left intact: `--progress=plain` so the
log keeps advancing, `timeout-minutes: 20` on the step and `60` on the job so a
genuine hang fails visibly instead of holding a runner for the 6h default.

### Genuine CI failures found and fixed

- Run `30884443360` failed the Trivy **source** scan on three HIGH CVEs
  published after the 2026-08-03 runs: CVE-2026-69244 (aiohttp 3.14.1 ->
  3.14.3), CVE-2026-69247 (cryptography 48.0.1 -> 50.0.0) and CVE-2026-69249
  (-> 49.0.0). cryptography 50 required lifting pyopenssl, which capped it at
  `<49`; 26.4.0 accepts `>=49,<51`. Lock regenerated with uv 0.11.32 to match
  the Dockerfile's `UV_VERSION`, keeping revision 3 (`63d07e5c2`).
- Run `30884760338` failed `Build Lina` with "No tests found". See the Lina
  lineage section below.

### Lina lineage correction

The handoff asked for Lina `7657ad7`, but that commit is on `yetka-v4.10.16`, a
lineage **disjoint** from the shipping `foundation/source-ui` branch; they share
only the fork point `009ee6e`. Pinning it would have dropped 21 commits,
including the CareonCloud branding, the native maintenance/update control behind
the dashboard's Guncelle button, the tenant-aware cloud sync UI, and all four
Yetka unit specs. `c88d99a04` had already reverted this same swap once.

Of the four candidate branding commits, only the Turkish locale fallback was
still missing from the shipping branch; the rest were already superseded there:

- `b6ce843` removes the marketplace action, but `772cf23` had already pointed it
  at careoncloud.com, so no upstream link remains either way.
- `552f871` targets carry no upstream branding on this branch.
- `7657ad7` swapped the trust-domain alert URL but kept the Chinese upstream
  wording; this branch had already replaced that whole string with Turkish text
  and no URL, which is the stronger fix.

Lina is therefore pinned at `f6f272c` (`b108a4027` plus the cherry-picked
Turkish locale). Koko moved to `7117df1`, a linear descendant of `2c7f292`.

### Packaging

`[tool.setuptools] packages = []` is correct and load-bearing. Verified locally
that an editable install succeeds with `apps/`, `data/`, `deploy/` **and**
`tmp/` all present, and that none leak into site-packages; removing the stanza
reproduces `error: Multiple top-level packages discovered in a flat-layout`.
Guarded by `tools/tests/test_editable_packaging.py` and by a release-workflow
step that runs the updater's exact `uv pip install -e` under Python 3.14. That
step now creates `tmp/` and `data/` first, because a bare checkout lacks them
and a check without them does not represent the host the updater runs on.

### Runtime fix: missing service tmp directory

The test server was crash-looping with restart counter **4232**:
`FileNotFoundError: '/opt/yetka/app/tmp/gunicorn.pid'`. `3d9c47fbb` had removed
the tracked empty `tmp/` to stop setuptools discovering it, but nothing
recreates it, so every service died in `write_pid()`. Since discovery is now
disabled explicitly, `hands.py` creates `TMP_DIR` on demand (`c9298fd08`); in
the container image that path is a symlink to `/tmp/yetka`, which
`makedirs(exist_ok=True)` accepts.

### Stale host installer environment

The first two `apply` attempts rolled back safely at the editable-install step.
Root cause was not packaging: `/etc/yetka-install.env` carried
`YETKA_GIT_REF_OVERRIDE=yetka-1.0.6-final-ws6`, which silently outranks
`--version`, so the installer checked out `1a8762e` (ws6) — a commit predating
`packages = []`. The Lina/Luna/Koko URLs and checksums were also still pinned to
ws6, so even a successful install would have shipped old components. The file
was backed up to `/etc/yetka-install.env.bak-pre-ws11`, repointed at ws11, and
the `YETKA_GIT_REF_OVERRIDE` line removed so `--version` governs future deploys.

### Release ws11

- Workflow run: https://github.com/akinarcak/Yetka/actions/runs/30886193715 (success, 9m48s)
- Tag `yetka-1.0.6-final-ws11`, core commit `1c13712a22f1f3949baf2ffd0dc070418018234b`
  (contains the required `4cc286f2b`)
- Components: lina `f6f272c65509fa2be0f21d3883f192a8074519b8`, koko
  `7117df15a1c828929bf6da3a2c07270f4225cff5`, luna `315f6d26b64e99bb4b749d61a13dc549fbef3a97`

```
c0d061f9297db4f2e2fbfe28a9b8ae8ef51aaf780cc27fe62a4c2ddb99317b88  koko-yetka-1.0.6-final-ws11-linux-amd64.tar.gz
57caddd3d5175905659aa29b8b9f4b9b727b20fa8570756c20723d1257c5c658  lina-yetka-1.0.6-final-ws11.tar.gz
bfe4bc285e24e7c39aa8092e5c56f46cbd3411d378b4e6862b6d1d5a3e5ce8bc  luna-yetka-1.0.6-final-ws11.tar.gz
69edce3f3755dc75ad48c6ef43be9ab590126273c4ceafcee105cc5aa7d30be2  yetka-installer-yetka-1.0.6-final-ws11.tar.gz
```

### Deployment verification (100.86.171.110)

`yetka-update apply --env /etc/yetka-install.env --version yetka-1.0.6-final-ws11 --yes`
reported `Update complete: yetka-1.0.6-final-ws11`; backup retained at
`/var/backups/yetka/20260804T073653Z-yetka-1.0.6-final-ws-to-yetka-1.0.6-final-ws11`.

- Deployed core commit `1c13712`; four services `yetka-web`, `yetka-worker`,
  `yetka-scheduler`, `yetka-koko` all `active`.
- `/api/health/` returns `status`, `db_status`, `redis_status` all true; public
  UI 200; unauthenticated `/api/v1/users/users/` 401; unauthenticated
  notification WebSocket refused through nginx (404, no upgrade).
- Koko reports `Yetka Koko Version yetka-1.0.6-final-ws11` and `Start ws client
  success` (07:40:13) with no current certificate warning;
  `/opt/yetka/koko/server.crt` present and `server.key` mode `0600`.
- `/usr/local/bin/yetka-run-tests`: 13 tests, 13 passed, no system-check issues.
- Deployed Lina carries `careoncloud-logo.png`, confirming the correct lineage.

### Terminal smoke test

The workspace previously had zero assets. A disposable asset
`yetka-smoke-localhost` (127.0.0.1:22, CareOnCloud workspace, account `test`)
was registered. On the ws11 deployment its connectivity was reset to `unknown`
and re-verified through Yetka's own connectivity automation, which returned
`ok` at 07:49:09 UTC — a real SSH connection over the product's connection path.

### WebSocket scoping

`apps/tenants/middleware.py:129` still evaluates the socket path **before**
`user.is_superuser`. Python's `and` short-circuits, so the superuser exception
can only apply to `/ws/notifications/site-msg/` and is never reached for Koko's
terminal socket, which is the ordering the earlier regression required.
Koko's live `Start ws client success` confirms the service-account path.

### Branding scan

`tools/verify_release.py` against the pinned Lina (`f6f272c`) and Koko
(`7117df1`) roots: 15 tests pass and both report `product-language policy v1:
clean`. Scans for user-visible `JumpServer`, `FIT2CLOUD`, `kurumsal surum` and
upstream release URLs classify as follows.

Allowlisted, not user-visible:

- Go module import paths (`github.com/jumpserver/koko`) in Koko `pkg/`, `cmd/`,
  `go.mod`, `go.sum`, `Makefile`, `Dockerfile`, `.goreleaser.yaml`.
- Django module and container paths (`apps/jumpserver/...`,
  `/opt/jumpserver/data`, `DJANGO_SETTINGS_MODULE=jumpserver.settings`) in Core
  and in CI workflow files.
- Upstream CI leftovers (`fit2cloud/LLM-CodeReview-Action`) in Lina/Koko
  `.github/workflows`.
- `apps/templates/_header_bar.html` still links to `jumpserver.com/docs`, but it
  is dead: nothing extends `base.html`, and served templates extend
  `_without_nav_base.html`.
- Lina `About.vue` compares against the upstream corporation string only to
  suppress a non-matching value, so nothing upstream is rendered.
- Locale `msgid` entries and GPL attribution in `LICENSE`, `NOTICE`, `README`.

Both user-visible findings were resolved in ws12 (see below).

### Remaining limitations

- The browser-level dashboard notification WebSocket was not exercised: it needs
  an authenticated operator session and no Chrome browser is connected to this
  environment. Code ordering, the regression test and Koko's live socket are
  verified instead.
- A Luna terminal session in the UI likewise needs an operator login. The
  connection path is verified up to that point via the connectivity automation.
- Delete `yetka-smoke-localhost` before the workspace is used for anything real.

## ws12: removal of the last user-visible upstream surfaces (2026-08-04)

Both open branding items were closed.

### Enterprise-edition wording

The Turkish catalog rendered `This is enterprise edition applet` as
`Bu, kurumsal surum applet'idir`, reachable from
`terminal/api/applet/applet.py:74` when an enterprise-edition applet is uploaded
without a valid xpack licence. Rather than patching only the Turkish string and
leaving every other language advertising an edition Yetka does not sell, the
source message was changed to `This applet is not supported by this
installation`. The Turkish entry was updated to match
(`Bu applet bu kurulumda desteklenmiyor`).

The bare-metal deployment path never runs `compilemessages` and the `.mo` files
are tracked, so `apps/i18n/core/tr/LC_MESSAGES/django.mo` was regenerated:
2680 entries before and after, the new msgid present, and no remaining
`kurumsal surum` string.

Other locales keep an entry for the old msgid; since the msgid changed they no
longer match and those languages fall back to the neutral English source string,
which is the intended outcome.

### Third-party legal pages

`/user-agreement/` and `/privacy-policy/` served FIT2CLOUD ("Feizhiyun")
Community Edition legal text naming JumpServer, MeterSphere, DataEase and
others, with fit2cloud.com legal URLs and a Beijing postal contact. The routes,
the `UserAgreementView`/`PrivacyPolicyView` views and the six template files
were removed. No replacement terms were authored: publishing legal text is a
business decision, not a branding edit.

Nothing referenced the removed routes by name, so no `NoReverseMatch` is
possible; `grep` for `UserAgreementView`, `PrivacyPolicyView`, `user_agreement`
and `privacy_policy` across `apps/` returns nothing, and Lina never linked to
them.

`fit2cloud` now appears in 16 files rather than 21, and none of the remainder is
user-visible: locale `msgid` entries (the Turkish catalog already maps
`FIT2CLOUD` to `Yetka` and `JumpServer - An open-source PAM` to
`Yetka - Acik kaynak PAM`), the xpack settings module, build scripts and this
report.

### ws12 release and deployment

- Workflow run: https://github.com/akinarcak/Yetka/actions/runs/30902527128 (success)
- Foundation gates on the same commit:
  https://github.com/akinarcak/Yetka/actions/runs/30902529905 (success:
  provenance, container-build, lina-source). `container-build` runs the Django
  suites inside the built image, which is what validates the removal of the
  authentication views and URLs.
- Tag `yetka-1.0.6-final-ws12`, core commit
  `aeea9925fe5b97294012fac74c49b860c8d974ef`. Lina `f6f272c`, Koko `7117df1`
  and Luna `315f6d26b` are unchanged from ws11.

```
eee263a0acd2b3f9aa0b6437714e5e36c31f06c67f7e3af22a0bf38b3e4b40ea  koko-yetka-1.0.6-final-ws12-linux-amd64.tar.gz
42a0a069e6fd9aa936dbb9e56a562d2950778622055368d255a7c316bf71e334  lina-yetka-1.0.6-final-ws12.tar.gz
b21805de26c7394fde2662d8c7a949e667118ef032ffba13ea5dd205e53e8602  luna-yetka-1.0.6-final-ws12.tar.gz
c929554b15a8680dd1d495594f5c4b8bcc293ab4f44eb2663a86ff2ec37bd503  yetka-installer-yetka-1.0.6-final-ws12.tar.gz
```

The host environment was repointed at ws12 (backup
`/etc/yetka-install.env.bak-pre-ws12`) and the update applied on the first
attempt: `Update complete: yetka-1.0.6-final-ws12`, backup retained at
`/var/backups/yetka/20260804T110433Z-yetka-1.0.6-final-ws11-to-yetka-1.0.6-final-ws12`.

Verification on `100.86.171.110`:

- Deployed core commit `aeea992`; all four services active.
- `/api/health/` returns `status`, `db_status`, `redis_status` true; public UI 200;
  unauthenticated API 401.
- `/core/auth/user-agreement/` and `/core/auth/privacy-policy/` now return **404**,
  confirming the third-party legal pages are no longer served.
- Koko reports `Yetka Koko Version yetka-1.0.6-final-ws12` and `Start ws client
  success` (11:07:56); `server.key` mode `0600`.
- `/usr/local/bin/yetka-run-tests`: 13 tests, 13 passed, no system-check issues.
- Asset connectivity re-verified through Yetka's automation: `ok` at 11:15:33 UTC.

With this the branding scan has no open user-visible findings. The remaining
limitations are unchanged: the browser dashboard WebSocket and a Luna terminal
session still need an authenticated operator, and `yetka-smoke-localhost` should
be deleted before the workspace is used for anything real.
