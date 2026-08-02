# Yetka fork governance

Yetka changes are maintained as small, reviewable commits on top of the
community base. Every external component is pinned by immutable commit in
`components.lock.yml`; floating branches, downloaded binaries, and unreviewed
enterprise artefacts are prohibited.

Before updating a component, record its source commit, license/NOTICE diff,
build command, test evidence, SBOM delta, and rollback commit. A release may
only combine components from the same lock revision. Changes that alter tenant
boundaries, SSH trust, recording retention, or release verification require a
security review and a corresponding negative test.
