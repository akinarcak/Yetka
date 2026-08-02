"""Offline fixture backup/restore smoke test for the MSP foundation gate."""

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory


def run_smoke_test():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = sqlite3.connect(root / 'source.sqlite3')
        source.executescript(
            'CREATE TABLE tenants (id TEXT PRIMARY KEY, name TEXT);'
            'CREATE TABLE tenant_organizations (tenant_id TEXT, organization_id TEXT);'
            "INSERT INTO tenants VALUES ('tenant-a', 'Fixture tenant');"
            "INSERT INTO tenant_organizations VALUES ('tenant-a', 'org-a');"
        )
        source.commit()
        backup = sqlite3.connect(root / 'backup.sqlite3')
        source.backup(backup)
        backup.close()
        source.close()

        restored = sqlite3.connect(root / 'backup.sqlite3')
        assert restored.execute('SELECT id, name FROM tenants').fetchall() == [
            ('tenant-a', 'Fixture tenant')
        ]
        assert restored.execute(
            'SELECT tenant_id, organization_id FROM tenant_organizations'
        ).fetchall() == [('tenant-a', 'org-a')]
        restored.close()


if __name__ == '__main__':
    run_smoke_test()
    print('offline backup/restore smoke test passed')
