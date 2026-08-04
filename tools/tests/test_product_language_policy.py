import json
import tempfile
import unittest
from pathlib import Path

from tools.validate_product_language import load_policy, violations


class ProductLanguagePolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy(Path("tools/forbidden-content-policy.json"))

    def test_product_term_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "About.vue").write_text("Enterprise edition", encoding="utf-8")
            self.assertEqual(len(violations(root, self.policy)), 1)

    def test_upstream_technical_line_is_allowlisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "runtime.js").write_text("import x from '@/utils/jms/index'", encoding="utf-8")
            self.assertEqual(violations(root, self.policy), [])


if __name__ == "__main__":
    unittest.main()
