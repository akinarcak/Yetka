# URL-pinned dependencies and the audit blind spot

Date: 2026-08-04

Five entries in `[tool.uv.sources]` were declared by URL rather than by version.
Two have since been resolved (`ansible-core`, `django-radius`) and
`ansible-runner` was re-based onto current upstream; three remain by URL.
`pip-audit` cannot resolve a URL requirement to a package version, so it skips
them and says so:

```
Name           Skip Reason
-------------- ---------------------------------------------------------------
ansible-core   URL requirements cannot be pinned to a specific package version
ansible-runner URL requirements cannot be pinned to a specific package version
django-cas-ng  URL requirements cannot be pinned to a specific package version
django-radius  URL requirements cannot be pinned to a specific package version
redis          URL requirements cannot be pinned to a specific package version
```

Three of the five are authentication or transport libraries in a privileged
access product. None of them has ever been audited.

This file records what each one actually is, measured rather than assumed, so
the next person does not have to derive it again.

## Summary

| Entry | Kind | Divergence from upstream | Genuinely fork-specific | Upstream today |
| --- | --- | --- | --- | --- |
| `ansible-core` | not a fork | none | none | resolved, see below |
| `ansible-runner` | fork | ahead 1, behind 0 of `2.4.3` | 1 commit | `2.4.3` |
| `redis` (redis-py) | fork | ahead 1, behind 0 of `v5.0.3` | 1 commit | well past `5.0.3` |
| `django-cas-ng` | fork | ahead 32, behind 0 of `v4.3.0` | 2 commits | `v5.1.1` |
| `django-radius` | fork | ahead 6, **behind 6** of `1.5.0` | none load-bearing | resolved, now `==1.5.1` |

The headline is smaller than it looks. `ansible-runner` and `django-cas-ng`
appear heavily diverged, but almost all of those commits are upstream's own
merged pull requests — the forks are snapshots taken after a release, not
rewritten libraries. Across all four, the genuinely local change amounts to
four commits.

## ansible-core — resolved

Not a fork at all. The URL pointed at
`files.pythonhosted.org/packages/9d/75/.../ansible_core-2.16.19.tar.gz`, which
is the official PyPI sdist for 2.16.19, confirmed against the PyPI API. It
carried no patch; the URL only cost visibility.

Converted to `ansible-core==2.16.19`. The relocked entry keeps
`sha256:5125f264...` unchanged, which is the proof that the artifact is
identical. One real difference: a registry source exposes wheels, so the build
installs the wheel rather than compiling the sdist.

## ansible-runner — resolved, still a fork

Pinned: `akinarcak/ansible-runner` tag `v2.4.3.1`.
Upstream: `ansible/ansible-runner`, at `2.4.3`.

Previously `jumpserver-dev/ansible-runner` `v2.4.0.2`, a snapshot of upstream's
post-2.4.0 line carrying one fork-specific commit, `8f9316545`
(`fix: disable env (#1)`).

**Answered (2026-08-06):** the commit is load-bearing and upstream has not
taken it. It edits `src/ansible_runner/config/runner.py`, where the bubblewrap
argument list is built, and does two things:

- unsets every environment variable whose name contains `KEY`, `PASSWORD`,
  `TOKEN`, `SECRET`, `PASSWD`, `REDIS_` or `DB_` before the sandbox starts, so
  `SECRET_KEY` and the database and Redis credentials in the web process's
  environment are not inherited by automation subprocesses;
- replaces the `/lib` and `/lib64` symlink bindings with read-only binds.

That path is live: `PlaybookRunner` defaults to `isolate = True` and, when
docker isolation is off, passes `process_isolation_executable='bwrap'`
(`apps/ops/ansible/runner.py`). Upstream `2.4.1`, `2.4.2` and `2.4.3` change
volume mounts, callback plugins and tty detection; none touches environment
handling or the sandbox arguments. Swapping the fork for `ansible-runner==2.4.3`
from PyPI would therefore drop a credential-isolation control.

**What was done instead:** the fork was re-based rather than removed. Upstream
`2.4.3` plus a cherry-pick of `8f9316545` — which applies cleanly, since
`config/runner.py` is untouched between `2.4.0` and `2.4.3` — is published as
`akinarcak/ansible-runner` `v2.4.3.1`. The fork is now ahead 1, behind 0 of
current upstream, which is the smallest divergence this entry can have while
the patch remains unmerged.

The audit blind spot is unchanged: pip-audit still skips this entry because it
is a URL requirement. `ops.ansible_engine_tests.RunnerForkTripwireTest` covers
what the audit cannot — it asserts the installed distribution is on the 2.4.3
line and that the env-sanitizing code is present, so a silent swap to plain
upstream fails the gate.

**To fully resolve:** propose `8f9316545` upstream. If it merges, this entry
becomes a version pin like `ansible-core` did.

## redis (redis-py)

Pinned: `jumpserver-dev/redis-py` tag `v5.0.3`.
Upstream: `redis/redis-py`, far past 5.0.3.

The cleanest case: ahead 1, behind 0, a single commit.

- `6eae8dddf` — `fix: connectionPool deadlock triggered by gc`

The patch is one line, in `ConnectionPool.reset()`:

```python
-        self._lock = threading.Lock()
+        self._lock = threading.RLock()
```

A non-reentrant lock deadlocks when garbage collection re-enters the pool while
the lock is held.

**Answered (2026-08-04):** upstream has taken the same fix, but not in the 5.x
line. Checking `redis/connection.py` at each tag:

| Version | Pool lock |
| --- | --- |
| `v5.0.3` – `v6.1.0` | `threading.Lock()` — unfixed |
| `v6.2.0` | `RLock`, except when client-side caching is enabled |
| `v7.0.0`, `v8.0.0` | `RLock` unconditionally |

`v6.2.0` carries the fix behind a condition upstream documented as temporary:

```python
if self.cache is None:
    self._lock = threading.RLock()
else:
    # TODO: To avoid breaking changes during the bug fix, we have to keep non-reentrant lock.
    # TODO: Remove this before next major version (7.0.0)
    self._lock = threading.Lock()
```

Client-side caching arrived in redis-py 5.1, so a project pinned at 5.0.3
cannot be using it and `v6.2.0` would be sufficient.

**What this costs:** dropping the fork is not a swap. It requires moving from
5.0.3 to at least 6.2.0 — a major version step in the Redis client of a
privileged access product, with `django-redis`, `channels-redis` and
`python-redis-lock` all sitting on top of it. The fork is a one-line patch; the
replacement is a migration. Worth doing, but not worth doing casually.

## django-cas-ng

Pinned: `ibuler/django-cas-ng` release `v4.3.2`.
Upstream: `django-cas-ng/django-cas-ng`, now at `v5.1.1`.

`v4.3.2` does not exist upstream — upstream goes `v4.3.0` then `v5.0.0`, so the
fork cut its own release. Against upstream `v4.3.0` it is ahead 32, behind 0,
and thirty of those are upstream pull requests (#310 through #330). The
fork-specific change is two commits, both narrow:

- `8190a86af` — `perf: Change session_key max length to 768 for utf8mb4 index limit`
- `79b52e1c8` — `perf: modify to 736, because uniq_together with user, user id maybe uuid 32 length`

They touch `django_cas_ng/models.py` and
`django_cas_ng/migrations/0002_auto_20201023_1400.py`: a MySQL utf8mb4 index
length problem, where `session_key` inside a `unique_together` exceeds the
index limit.

This is the fork with the largest gap to upstream — roughly two major versions
and three years, including whatever upstream has fixed in that time.

**To resolve:** the patch is a schema constraint, not library logic. Check
whether upstream `v5.1.1` already accommodates utf8mb4 index limits; if not,
consider carrying the column length as a migration in this project rather than
as a library fork, which would let the dependency track upstream normally.

## django-radius

Pinned: `ibuler/django-radius` tag `1.5.0`.
Upstream: `robgolding/django-radius`, also has a tag named `1.5.0`.

The two tags are different code:

```
fork     4c082470b034a318590c92e0f43467be92b0c885
upstream 124e7b94d8636fbdaef1a3b52ae61e8852a4775e
```

Ahead 6 and **behind 6** — the only entry that is behind upstream at all. The
six commits ahead are merges of upstream community pull requests (from
`kkirsche` and `hwehr`), not local work; no distinguishable fork-specific patch
was found.

The tag collision deserves attention on its own. `django-radius 1.5.0` means
different code depending on which repository it is fetched from, which defeats
version identity for a RADIUS authentication library.

### Three version identities (2026-08-04)

The tag collision is not the whole of it. Relocking against PyPI reported:

```
Updated django-radius v1.4.0 -> v1.5.1
```

The lock had been recording the fork as **1.4.0**. The URL says `1.5.0.zip`,
the git tag says `1.5.0`, and the package metadata in `setup.py` says `1.4.0` —
the fork changed that line but never bumped it to match its own tag. So the
installed RADIUS backend reported a version that matched neither the tag it was
fetched by nor the upstream release of the same name.

### Resolved: replaced with upstream `1.5.1`

The fork's changes to `radiusauth/backends/radius.py` are three, and none of
them is load-bearing here:

1. **Python 2 shims removed** (`from future import standard_library`,
   `past.builtins.basestring`). Cosmetic. `future==0.18.3` remains a declared
   dependency, so upstream's imports still resolve.

2. **`int(settings.RADIUS_PORT)`.** Redundant in this project. The default in
   `apps/jumpserver/conf.py` is the integer `1812`; `Config.convert_type()`
   coerces environment values to the type of the default; and the settings API
   validates it through `serializers.IntegerField`. The value is an integer on
   every path.

3. **`RADIUS_REMOTE_ROLES` gate.** This looked like the one that mattered,
   since it decides whether a RADIUS server's `Class` attribute may set
   `is_staff` and `is_superuser` — whether an external directory can mint
   Django superusers.

   It is unreachable. `apps/authentication/backends/radius/backends.py`
   defines `CreateUserMixin.get_django_user`, and the MRO
   (`RadiusBackend` -> `RadiusBaseBackend` -> `CreateUserMixin` -> ... ->
   `RADIUSBackend`) puts it ahead of the library's. That override creates the
   user from the username and e-mail suffix and never touches `is_staff` or
   `is_superuser`; it accepts them only as `*args, **kwargs` and discards
   them.

   So remote role elevation does not happen with the fork, and would not
   happen with upstream either. The gate, the setting and upstream's
   unconditional assignment are all in a method this project replaces.

   Confirmed by execution on 2026-08-05, and the conclusion holds for a second
   reason the reasoning above did not reach. `is_staff` is not a stored field
   on this project's `User` at all: `apps/users/models/user/_role.py` defines it
   as `self.is_authenticated and self.is_valid` with a setter that is a no-op,
   and `is_superuser` is derived from system role membership. Even a caller that
   did pass those arguments through could not make them stick. The
   characterization suite that established this could not run in CI for reasons
   unrelated to RADIUS; see `docs/testing/database-backed-tests.md`.

Replaced with `django-radius==1.5.1` from PyPI, the upstream author's latest
release. There was no "same version" to preserve — the fork's 1.5.0 was never
upstream's 1.5.0 — so moving to the maintained release rather than an older
point release is the smaller risk, not the larger one.

## Re-verifying this

Divergence figures come from the GitHub compare API, which accepts a
cross-repository head:

```
gh api repos/<upstream>/compare/<base-tag>...<fork-owner>:<fork-tag>
```

The audit skip list comes from the `python-audit` job of
`.github/workflows/security-maintenance.yml`.

## Related

- The dependency audit itself was restored on 2026-08-04; before that the
  filesystem scan had not run since 2026-07-20. See the security control
  history in `MSP-FOUNDATION-COMPLETION-REPORT.md`.
- `pip-audit` and Trivy read different advisory databases and both missed two
  high-severity findings that Dependabot alerts surfaced. Coverage differs by
  source; a single scanner is not a complete answer.
