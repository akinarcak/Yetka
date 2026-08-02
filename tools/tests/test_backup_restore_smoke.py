import unittest

from tools.backup_restore_smoke import run_smoke_test


class BackupRestoreSmokeTests(unittest.TestCase):
    def test_fixture_round_trip_preserves_tenant_ownership(self):
        run_smoke_test()
