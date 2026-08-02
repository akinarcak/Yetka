# Customer tenant isolation

`CustomerTenant` is the MSP customer boundary. It is deliberately separate from
JumpServer's organization and license concepts. A user may select a tenant only
through an active `CustomerTenantMembership`; superuser status does not create an
implicit membership.

## Request contract

- Clients send `X-YETKA-TENANT: <uuid>` for tenant-scoped API requests.
- The backend resolves the header against the authenticated user's active
  memberships. A user with several memberships must select one explicitly.
- The selected `X-JMS-ORG` organization must have a `TenantOrganization` link to
  the same tenant. A mismatch is rejected before the view executes.
- Health and tenant-discovery endpoints are not tenant-scoped. An authenticated
  tenant list contains memberships for that user only.
- Context is held in a Python `ContextVar` and reset in `finally` semantics after
  every request. Background work must receive a serialized tenant UUID and open
  its own tenant context; inheriting process-local request state is forbidden.

## Ownership matrix

| Resource family | Tenant ownership source | Migration rule | Delete rule |
| --- | --- | --- | --- |
| Organization | `TenantOrganization.tenant` | Every non-internal organization must map exactly once | Protected |
| Assets, accounts, nodes | Organization mapping, then direct tenant FK | Backfill from `org_id`; reject missing/ambiguous rows | Protected |
| Automations and executions | Direct tenant FK copied from parent automation | Backfill parent first; verify child equality | Protected |
| Sessions, recordings, commands, FTP/SFTP logs | Immutable tenant FK captured at session creation | Backfill through session asset organization | Retained with audit data |
| Cloud Sync accounts, tasks, discovered objects | Direct tenant FK | Backfill from current organization; quarantine unresolved objects | Protected |
| Reports, downloads, generated files | Direct tenant FK plus tenant-bound storage key | Regenerate where provenance cannot be proven | Delete with parent/report policy |
| Users | Membership, not ownership | No user-level tenant FK | Membership may be revoked |
| Global configuration and component manifests | Global allowlist | Never copied into a customer tenant | Global administrator only |

## Referential-integrity migration plan

1. Deploy the tenant, membership, and organization-link tables without changing
   existing resource queries. Create tenants and explicit user memberships.
2. Map each non-internal organization. A preflight command must stop on unmapped
   or multiply claimed organizations; it must never guess from names.
3. Add nullable tenant FKs to owned parent tables and backfill in bounded,
   restartable batches from `TenantOrganization`. Record unresolved rows in a
   quarantine report.
4. Verify parent/child equality, orphan counts, and per-tenant row totals. Add
   composite uniqueness and FK constraints, then make the tenant columns
   non-null.
5. Replace implicit organization-manager filtering with explicit
   `.for_tenant(tenant)` query paths. Enable API, job, download, and WebSocket
   isolation gates only after their negative tests pass.
6. Capture tenant IDs immutably on new audit/session/recording records and remove
   fallback-to-root behavior from tenant-owned paths.

Rollback before step 4 disables the tenant middleware and leaves additive tables
and nullable columns intact. After non-null constraints are enabled, rollback
requires restoring the pre-migration database snapshot; tenant identifiers must
not be discarded because they are audit provenance.
