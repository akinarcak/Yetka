"""Guard the editable-install packaging contract used by the release updater.

The updater installs Core with ``uv pip install --python <venv> -e <app>``
(see ``deploy/yetka-update.sh`` and ``deploy/install-baremetal.sh``). Core uses a
flat layout, so if setuptools is allowed to auto-discover packages it treats
top-level directories such as ``apps``/``data``/``deploy`` as packages and fails
metadata generation. That failure previously rolled back live deployments.

Discovery must therefore stay explicitly disabled.
"""

import tomllib
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]

# Top-level directories that setuptools' flat-layout fallback would otherwise
# claim as packages.
FLAT_LAYOUT_DECOYS = ("apps", "data", "deploy")


class EditablePackagingTests(TestCase):
    def setUp(self):
        self.pyproject = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )

    def test_package_discovery_is_explicitly_disabled(self):
        setuptools_table = self.pyproject.get("tool", {}).get("setuptools", {})
        self.assertIn(
            "packages",
            setuptools_table,
            "pyproject.toml must set [tool.setuptools] packages explicitly; "
            "omitting it re-enables flat-layout auto-discovery.",
        )
        self.assertEqual(
            setuptools_table["packages"],
            [],
            "Editable installation is used for dependency management only. "
            "Declaring packages here makes setuptools scan the flat layout.",
        )

    def test_broad_discovery_directives_are_not_reintroduced(self):
        setuptools_table = self.pyproject.get("tool", {}).get("setuptools", {})
        self.assertNotIn(
            "py-modules",
            setuptools_table,
            "py-modules would reintroduce top-level module discovery.",
        )
        packages = setuptools_table.get("packages")
        self.assertNotIsInstance(
            packages,
            dict,
            "A packages.find directive re-enables directory scanning; "
            "keep the explicit empty list instead.",
        )

    def test_flat_layout_directories_still_exist(self):
        # If these ever disappear the guard above is no longer load-bearing and
        # this test should be revisited rather than silently passing.
        present = [name for name in FLAT_LAYOUT_DECOYS if (ROOT / name).is_dir()]
        self.assertTrue(
            present,
            "Expected Core to keep its flat layout; packaging guard assumes it.",
        )
