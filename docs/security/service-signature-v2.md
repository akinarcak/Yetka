# Service signature v2 threat model and migration

Yetka has two machine-to-machine signature paths: the internal
`X-JMS-SVC` permission and the `Authorization: Signature` authentication used
by integration applications (`X-Source: jms-pam`). Both legacy profiles were
vulnerable to replay because a valid signature did not bind every security-
relevant part of the request.

The legacy `X-JMS-SVC: Sign <key>:<encrypted timestamp>` format proves only
knowledge of the access-key secret inside a short clock window. It does not
bind the authorization to the HTTP method, path, query, body, or customer
tenant. A captured request can therefore be replayed with altered content
unless every caller and endpoint adds independent validation.

V2 uses `SignV2` with access-key ID, timestamp, caller-generated nonce,
customer-tenant ID (or `-` for an explicitly tenantless request), algorithm,
and an HMAC-SHA256. The HMAC canonical form is method, full path and query,
SHA-256 body digest, timestamp, nonce, and tenant ID separated by newlines.
Verification uses constant-time comparison, a 30-second clock window, and an
atomic cache `add` to consume each key/nonce pair once. Cache failure denies
the request.

Legacy verification is disabled by default. Operators may temporarily set
`SECURITY_SERVICE_SIGNATURE_ALLOW_LEGACY=True` while upgrading trusted
components, but should monitor and remove the flag after all callers emit V2.
Legacy mode retains the existing timestamp nonce protection but cannot provide
method/path/body/tenant binding and is not considered equivalent security.

## Integration-application HTTP Signature profile

The strict integration profile requires these signed headers:

`(request-target) date digest x-jms-nonce x-jms-org x-yetka-tenant`

- `date` must be within `SECURITY_SERVICE_SIGNATURE_WINDOW_SECONDS` (30 by
  default; values outside 1-300 seconds fail closed).
- `digest` is `SHA-256=<base64 SHA-256 of the exact HTTP body>` and is checked
  with `hmac.compare_digest`.
- `x-jms-nonce` is a caller-generated 16-128 character request ID. The
  key/tenant/nonce tuple is atomically consumed in the shared Django cache.
- `x-jms-org` must match the integration application's organization and
  `x-yetka-tenant` must own that organization. If middleware has already bound
  a tenant, it must also match the signed tenant.
- The pinned `pyhttpsig` HMAC verifier uses a constant-time byte comparison
  for the HTTP signature itself.

Legacy integration signatures containing only `(request-target)` and `date`
are rejected by default. During a bounded caller migration, operators may set
`SECURITY_SERVICE_SIGNATURE_ALLOW_LEGACY: true` in `config.yml`. Upgrade
callers to emit the six strict signed fields, monitor legacy use, then remove
the flag. Strict and legacy requests are distinguished by their signed-header
list; legacy mode never silently treats an incomplete strict request as V2.
