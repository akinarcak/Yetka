import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from .component_manifest import component_status, load_supported_components


class SupportedComponentManifestTests(TestCase):
    def test_required_components_have_explicit_status(self):
        components = load_supported_components()
        for name in ('koko', 'lion', 'chen', 'magnus', 'razor', 'nec'):
            self.assertIn(components[name]['status'], ('supported', 'unavailable'))

    def test_unknown_component_is_unavailable(self):
        self.assertEqual(component_status('future-component')['status'], 'unavailable')

    def test_manifest_loader_accepts_override_for_build_checks(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'manifest.json'
            path.write_text(json.dumps({'components': {'demo': {'status': 'supported'}}}))
            self.assertEqual(load_supported_components(path)['demo']['status'], 'supported')
