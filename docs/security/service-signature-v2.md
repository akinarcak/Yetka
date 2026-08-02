# Service signature v2 threat model and migration

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
