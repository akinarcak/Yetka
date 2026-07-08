# Yetka 1.0.1 Security Maintenance Release

Release tag: `yetka-1.0.1`

## Security fixes

- Prevent LDAP search filter injection by escaping user-controlled filter values.
- Update `pyasn1` from 0.6.3 to 0.6.4 to address published parser vulnerabilities.
- Include the security hardening already present in the Yetka maintenance line:
  - parameterized MSSQL account automation;
  - sanitized automation runtime directory names;
  - safe flash-message redirects;
  - protected report export URLs;
  - reduced database error disclosure;
  - constant-time bootstrap token comparison;
  - hardened XML parsing.

## Remaining upstream advisories

The dependency audit still reports advisories without a compatible patch in this
maintenance line for `ecdsa` 0.19.2 and `paramiko` 3.5.1. It also reports an
`ansible` meta-package advisory whose patched release requires a major
`ansible-core` upgrade. These upgrades are deferred to the next compatibility
release and should not be treated as resolved by this release.

## Deployment

Back up the database and `/opt/yetka` before applying the update:

```bash
sudo yetka-update check --version yetka-1.0.1
sudo yetka-update apply --version yetka-1.0.1
```
