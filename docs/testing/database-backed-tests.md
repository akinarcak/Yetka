# Database-backed tests in the foundation gate

The gate runs 84 Django tests and reports them green. None of them touches a
database, and none of them could: creating the test database fails in the
container the gate uses, and the failure is invisible.

This file records the measurement and the cause, so the next person does not
have to derive it again.

## What the gate measures today

`foundation-gates.yml` invokes `django test` four times inside
`yetka/core:foundation-test`. On `main` at `d39e3ad6d` those four runs print:

```
Found 36 test(s).   Ran 36 tests   OK
Found 27 test(s).   Ran 27 tests   OK
Found 13 test(s).   Ran 13 tests   OK
Found  8 test(s).   Ran  8 tests   OK
```

and, four times over:

```
Skipping setup of unused database(s): default
```

Every test class in those suites derives from `SimpleTestCase`. Django therefore
computes an empty set of required aliases and skips `setup_databases` entirely.
The count comparison that catches a suite silently shrinking does not catch
this, because nothing shrank — the database was never in scope.

So the gate's assertion is narrower than it reads. It shows that this logic
holds without a database. It does not show that anything holds with one, and
the tenant isolation suite is inside that limit.

## Why adding a database-backed test fails

Add any plain `TestCase` and `setup_databases` runs for real. It dies while
applying `users.0001_initial`, and Django reports only this:

```
django.db.transaction.TransactionManagementError: An error occurred in the
current transaction. You can't execute queries until the end of the 'atomic'
block.
```

That is the secondary failure. It is raised `from self.rollback_exc`, which is
empty, so Python prints no cause and the traceback ends there. The primary
failure has already been swallowed.

There are two swallowing sites, and both had to be removed before the real one
was visible.

### 1. `assets_platform` queried before its table exists

While Django loads apps, `AccountAssetSerializer` in
`apps/accounts/serializers/account/account.py` builds a `LabeledChoiceField`
whose choices resolve through `AllTypes.get_choices()`
(`apps/assets/const/types.py:41`) into `CustomTypes.get_choices()`
(`apps/assets/const/custom.py:11`), which runs
`Platform.objects.filter(category='custom')`.

On a fresh database that table does not exist yet. The query raises
`OperationalError: no such table: assets_platform`, and `custom.py` catches it:

```python
try:
    platforms = list(cls.get_custom_platforms())
except Exception:
    return []
```

The bare `except Exception` is the problem, not the empty list. Returning no
custom types on a database that has none is correct. Discarding the exception is
not: on SQLite the statement has already marked the transaction broken, so when
this happens inside a migration's atomic block the block cannot be exited
cleanly. `schema_editor.__exit__` calls `check_constraints()`, that issues
`PRAGMA foreign_key_check`, and `validate_no_broken_transaction()` raises the
`TransactionManagementError` above — with no record of what actually went wrong.

Neutralising this query took the swallowed failures from ten to one and exposed
the next one.

### 2. The migration needs Redis

`users/migrations/0001_initial.py:34` is:

```python
admin.groups.add(default_group)
```

That m2m write fires `m2m_changed`, which reaches
`apps/audits/signal_handlers/operate_log.py:70` and then
`apps/audits/handler.py:91`, which reads the audit cache:

```
redis.exceptions.ConnectionError: Error 111 connecting to 127.0.0.1:6379.
Connection refused.
```

The gate's container is started with `DB_ENGINE=sqlite3` and no Redis. So the
initial migration for the `users` app cannot complete there, and no
database-backed test can run. Nothing about this is specific to any one suite;
it is the environment.

## Reproducing it

Locally, against the same image the gate builds, with a Redis sidecar to prove
the second cause:

```bash
docker network create yetka-probe-net
docker run -d --name yetka-probe-redis --network yetka-probe-net redis:8-bookworm
docker run --rm --network yetka-probe-net --read-only \
  --tmpfs /tmp:rw,exec,nosuid,size=256m \
  --mount type=volume,destination=/opt/jumpserver/data \
  --env DB_ENGINE=sqlite3 --env DB_NAME=/tmp/yetka-tests.sqlite3 \
  --env REDIS_HOST=yetka-probe-redis --env REDIS_PORT=6379 \
  --env SECRET_KEY=foundation-ci-not-for-production \
  --env BOOTSTRAP_TOKEN=foundation-ci-bootstrap-not-for-production \
  --env DJANGO_SETTINGS_MODULE=jumpserver.settings \
  --workdir /opt/jumpserver/apps --entrypoint /opt/py3/bin/python \
  yetka/core:foundation-test -m django test <label> --verbosity=2
```

With Redis reachable the test database is created and destroyed normally.
Without it, the run fails as described.

To see a swallowed primary failure at all, wrap the cursor before Django starts
— `CursorWrapper._execute` for failing SQL, `Atomic.__exit__` for exceptions
that never reach a statement. Note that `common/apps.py` decides whether to fire
`django_ready` by looking for `migrate` or `test` in `sys.argv`, so a probe
script has to set `sys.argv` accordingly or it will trip over Redis during
startup instead of reaching the migration.

## What this cost

The RADIUS characterization suite was written, could not be made to run, and was
reverted on 2026-08-04 with the cause unidentified. The reasoning at the time
was that something about those tests broke database creation. It was not: the
suite was the first database-backed test the gate had ever been asked to run,
and it exposed an environment that had never supported one.

Run with Redis available, the reverted suite completes: 13 tests, 10 pass, 3
fail. All three failures are defects in the tests.

| Test | Why it fails |
| --- | --- |
| `test_remote_roles_are_discarded_for_a_new_user` | asserts `is_staff` is false |
| `test_remote_roles_are_discarded_for_an_existing_user` | asserts `is_staff` is false |
| `test_class_decode_unicode_error_is_swallowed` | depends on a traceback frame the stub destroys |

The first two assert against Django's stock `User` semantics rather than this
project's. `apps/users/models/user/_role.py` defines `is_staff` as a derived
property — `return self.is_authenticated and self.is_valid` — with a setter that
is deliberately a no-op. It is true for every valid user and is not a privilege
anything can grant. The third depends on `_perform_radius_auth` finding the text
`cl.decode` in `traceback.format_exception(..., limit=2)`; the test re-raises a
captured exception from a stub, so that frame is no longer in the traceback.

The claim these tests were written to protect is unaffected, and is in fact
stronger than recorded — see `docs/security/url-pinned-dependencies.md`.

## What it would take

1. Give the gate a Redis service and point the test container at it. This is
   what unblocks database-backed tests; everything else is secondary.
2. Narrow `custom.py`'s `except Exception` so a missing table is handled and
   anything else is not. As written it hides the class of failure that is
   hardest to diagnose, which is what happened here.
3. Fix the three assertions above and restore the RADIUS suite.

Until (1), any test added to the gate must be a `SimpleTestCase`, and the gate
should not be read as covering database behaviour.
