import io
import json
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from tools.scan_release_artifacts import violations
from tools.validate_components_lock import load_lock, release_manifest


class ComponentLockTests(TestCase):
    def test_repository_lock_is_valid(self):
        lock = load_lock(Path(__file__).resolve().parents[2] / "components.lock.yml")
        self.assertEqual(set(lock["components"]), {"lina", "luna", "koko"})

    def test_mutable_component_ref_is_rejected(self):
        with TemporaryDirectory() as directory:
            lock_path = Path(directory) / "components.lock.yml"
            lock_path.write_text(json.dumps({
                "schema_version": 1,
                "components": {"lina": {
                    "repository": "https://github.com/akinarcak/Yetka-Lina.git",
                    "commit": "main",
                    "version": "main",
                    "license": "GPL-3.0-or-later",
                    "artifact": "lina-{release_tag}.tar.gz",
                }},
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "immutable SHA-1"):
                load_lock(lock_path)

    def test_workflow_component_refs_match_lock(self):
        root = Path(__file__).resolve().parents[2]
        lock = load_lock(root / "components.lock.yml")
        release_workflow = (root / ".github/workflows/release-installer.yml").read_text(encoding="utf-8")
        foundation_workflow = (root / ".github/workflows/foundation-gates.yml").read_text(encoding="utf-8")

        for component, metadata in lock["components"].items():
            with self.subTest(component=component):
                self.assertIn(metadata["commit"], release_workflow)
        self.assertIn(lock["components"]["lina"]["commit"], foundation_workflow)
        self.assertIn("anchore/sbom-action", release_workflow)
        self.assertIn("cosign sign-blob", release_workflow)
        self.assertIn("cosign verify-blob", release_workflow)
        self.assertIn("SHA256SUMS.sig", release_workflow)
        self.assertIn("aquasecurity/trivy-action", release_workflow)
        self.assertIn("gitleaks/gitleaks-action", release_workflow)

    def test_release_manifest_records_artifact_hashes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            lock = {"components": {"lina": {
                "repository": "https://github.com/akinarcak/Yetka-Lina.git",
                "commit": "0" * 40,
                "version": "yetka-v1",
                "license": "GPL-3.0-or-later",
                "artifact": "lina-{release_tag}.tar.gz",
            }}}
            artifact = root / "lina-yetka-1.0.0.tar.gz"
            artifact.write_bytes(b"artifact")
            manifest = release_manifest(lock, root, "yetka-1.0.0", "1" * 40)
            self.assertEqual(len(manifest["components"]["lina"]["sha256"]), 64)


class ForbiddenContentTests(TestCase):
    def make_archive(self, root: Path, name: str) -> Path:
        archive = root / "fixture.tar.gz"
        payload = b"fixture"
        with tarfile.open(archive, "w:gz") as package:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            package.addfile(info, io.BytesIO(payload))
        return archive

    def test_xpack_path_is_rejected(self):
        with TemporaryDirectory() as directory:
            archive = self.make_archive(Path(directory), "app/xpack/plugin.py")
            self.assertEqual(violations(archive), ["app/xpack/plugin.py"])

    def test_community_archive_is_accepted(self):
        with TemporaryDirectory() as directory:
            archive = self.make_archive(Path(directory), "app/community/plugin.py")
            self.assertEqual(violations(archive), [])
