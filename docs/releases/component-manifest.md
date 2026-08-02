# Yetka component manifest

Runtime support boundaries are declared in `supported-components.json`. The
application must not infer support from an upstream or JumpServer component
name: entries marked `unavailable` are intentionally shown as unavailable in
product surfaces until a Yetka-supported build and test matrix exists.

Yetka releases use two provenance records:

- `components.lock.yml` pins every external build input to an immutable Git
  commit and records its repository, product version, license and expected
  artifact name.
- `components.release.json` is generated after packaging. It records the core
  release commit and the SHA-256 digest of every component artifact.

The lock file is JSON-compatible YAML so the release gate can validate it with
the Python standard library before project dependencies are installed.

## Updating a component

1. Review the component repository diff and upstream license notices.
2. Run that component's tests and build on the candidate commit.
3. Replace the commit and version in `components.lock.yml`.
4. Update the matching immutable commit environment value in
   `.github/workflows/release-installer.yml`.
5. Run `python tools/validate_components_lock.py` and the provenance tests.
6. Submit the lock change with the component test and review evidence.

Moving branch names, tags and `latest` references are not accepted as release
inputs. A tag may be retained as descriptive version metadata, but checkout and
verification always use the full commit SHA.

## Release gate

The release job verifies that checked-out Lina, Luna and Koko commits exactly
match the lock. After packaging it scans archive paths for forbidden xpack/EE
or undeclared enterprise component content, then generates
`components.release.json`. The release manifest is uploaded beside the
artifacts and checksum files.

The path scanner is an initial provenance boundary. Container filesystem and
SBOM-based forbidden-content checks remain mandatory before container releases
can be considered production-ready.

## Rollback

Rollback uses a previous release tag and its matching
`components.release.json`. Do not combine a core artifact from one release with
component archives from another release, even when API versions appear
compatible.
