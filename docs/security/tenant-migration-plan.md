# Customer tenant ownership migration plan

This plan is intentionally additive and must be executed against a verified
backup in a maintenance window. It does not authorize running migrations on a
customer or production database from this repository.

## Phases

1. **Inventory (read-only):** export organization, user, session, replay,
   Cloud Sync, and job counts; identify rows without an organization or with
   conflicting organization-to-tenant mappings.
2. **Bootstrap:** create `CustomerTenant` and `CustomerTenantMembership`
   records, then populate `TenantOrganization` for every approved workspace.
   Abort if a workspace maps to more than one tenant.
3. **Shadow validation:** run explicit tenant queryset checks and cross-tenant
   API/download/job/WebSocket negative tests without changing existing foreign
   keys. Compare counts and audit logs with the inventory.
4. **Enforcement:** enable tenant middleware and tenant-aware jobs for the
   selected cohort, then add non-null/FK constraints only after all orphan
   rows are resolved. Use small migrations so each step is reversible.
5. **Rollback:** restore the pre-migration backup, disable the feature flag,
   and revert the enforcement migration if validation or customer smoke tests
   fail. Preserve the migration report and audit trail.

## Acceptance evidence

- Every organization has exactly one approved tenant link.
- Every selected user has an explicit membership or is rejected.
- Cross-tenant session replay, Cloud Sync, Celery, download, and WebSocket
  requests return a denial/empty result.
- `makemigrations --check --dry-run tenants cloud_sync` is clean and the
  foundation container suite is green.
