# ADR 0001: Customer tenants and workspaces

Status: accepted

## Decision

Yetka uses two related concepts rather than exposing the upstream product's
organization vocabulary as its MSP boundary:

- **Customer tenant** is the hard isolation, ownership, billing, policy, and
  operational boundary. All tenant-owned records and asynchronous work carry a
  verified tenant identifier.
- **Workspace** is an optional subdivision inside one customer tenant. The
  existing `orgs.Organization` table remains the storage implementation during
  migration, but product UI and new public Yetka APIs call it a workspace.

One tenant may contain multiple workspaces. A workspace belongs to exactly one
tenant. Cross-tenant workspace movement is a controlled migration operation,
not a normal update.

## Why not merge them now

The existing organization key participates in assets, permissions, sessions,
automations, audits, and task context. Reusing it as the customer security
boundary would preserve implicit root/global behavior and make it difficult to
prove isolation. Replacing it in one destructive migration would create an
unacceptably large rollback and referential-integrity risk.

Keeping the boundary explicit permits incremental FK backfills and negative
tests while existing workspace behavior remains available inside a tenant.

## Product and attribution language

New UI, API descriptions, operator messages, and Yetka documentation use
`Yetka`, `customer tenant`, and `workspace`. The name `JumpServer` is retained
only where required for GPL attribution, copyright/NOTICE, fork governance,
upstream source references, compatibility notes, and upstream security/release
tracking. It is not a product feature, plan, license state, or customer-facing
edition that Yetka will continue.

## Migration and rollback

Renaming begins at the API/UI presentation layer; database table and Python
module renames are deferred until tenant FKs and cross-tenant tests cover all
owned resources. This keeps migrations additive. Rollback restores presentation
labels without removing tenant ownership data.
