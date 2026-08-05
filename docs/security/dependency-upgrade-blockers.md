# Dependency upgrade blockers

`#43` bundles 102 maintenance updates. Two of them break the same file at import
time, and one of those two is the only route to closing an open advisory. This
file records what each is, measured rather than assumed.

Both breakages are in `apps/common/utils/encode.py`. The container build fails
on the first, so the second has never appeared in CI output.

## itsdangerous 1.1.0 to 2.2.0

The build fails here:

```
File "apps/common/utils/encode.py", line 16
ImportError: cannot import name 'TimedJSONWebSignatureSerializer' from 'itsdangerous'
```

itsdangerous 2.0 removed `JSONWebSignatureSerializer` and
`TimedJSONWebSignatureSerializer`. `encode.py` imports both and uses them in
`Signer`, which is exported as the module-level `signer`.

This is not a code port. The 2.x serializers produce a different format and
cannot read tokens the 1.x JWS serializers wrote, so what matters is who reads
data that already exists:

| Call site | What it reads | Effect of a naive bump |
| --- | --- | --- |
| `apps/common/db/utils.py:159` | rows written before the `crypto` migration, reached only when `crypto.decrypt` returns nothing | those rows become permanently unreadable |
| `apps/terminal/migrations/0003_auto_20171230_0308.py` | values stored by an old release | migrating an old database stops working |
| `apps/users/models/user/_auth.py:302,314` | the LDAP login password cache | self-healing; entries are TTL-bounded |

Only the third is safe to break. The first is a fallback path for data at rest:
`decrypt()` tries `crypto.decrypt` first and calls `signer.unsign` only when
that yields nothing, which is precisely the case for legacy rows.

Upgrading therefore requires keeping a reader for the 1.x format, not just
swapping the import. JWS is a compact, well-specified structure and
reimplementing the read side in-repo is tractable, but it is a data-format
change and should be its own review, not one line inside a 102-package bundle.

## paramiko 3.5.1 to 5.0.0

paramiko 5.0.0 has no `DSSKey`. Measured directly:

```
$ python -c "import paramiko; print(hasattr(paramiko, 'DSSKey'), paramiko.__version__)"
False 5.0.0
```

`encode.py` references it three times, and the first is at module scope, so this
is an import-time failure like the one above rather than a runtime one:

- `_supported_paramiko_ssh_key_types` (line 73) lists `paramiko.DSSKey` in a
  tuple evaluated when the module loads.
- `ssh_key_gen` (line 128) calls `paramiko.DSSKey.generate(length)` for
  `type == 'dsa'`.
- `OldSSHTransport` in `apps/libs/ansible/modules_utils/remote_client.py` still
  advertises `ssh-dss` in `_preferred_pubkeys`.

Dropping DSA is the correct direction — it is why upstream removed it — but the
three sites have to go together, and the second changes an API this project
exposes: `ssh_key_gen` accepts `type='dsa'` and would have to start refusing it.

## Why these two are entangled

`Security maintenance` has failed on every run since 2026-08-04. It is failing
for a true reason:

```
Name     Version ID              Fix Versions
-------- ------- --------------- ------------
ansible  9.13.0  PYSEC-2026-1119 12.2.0
paramiko 3.5.1   PYSEC-2026-2858
```

`pip-audit` lists no fix version for the paramiko advisory, so there is no
smaller upgrade available. Closing it means moving to a paramiko that has
dropped DSA, which means doing the `encode.py` work above. The red gate and the
red pull request are the same problem seen from two directions.

The ansible entry is separate and is described in
`docs/security/url-pinned-dependencies.md`; it is blocked on the `ansible-core`
URL pin rather than on any code change.

## Recommendation

Split both packages out of the maintenance group. The remaining ~100 updates are
routine and should not wait behind two source changes, and neither of these two
should be reviewed as part of a bundle that size. A permanently red
`Security maintenance` is its own hazard — a gate nobody can act on is a gate
nobody reads.
