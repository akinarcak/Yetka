import json
from pathlib import Path
from unittest import TestCase

from tools.validate_components_lock import load_lock


class ComponentMatrixTests(TestCase):
    def test_supported_manifest_matches_buildable_lock(self):
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads((root / 'supported-components.json').read_text(encoding='utf-8'))
        lock = load_lock(root / 'components.lock.yml')
        components = manifest['components']
        self.assertEqual(
            {name for name, item in components.items() if item['status'] == 'supported'},
            {'core', 'lina', 'luna', 'koko'},
        )
        self.assertEqual(
            {name for name, item in components.items() if item['status'] == 'unavailable'},
            {'lion', 'chen', 'magnus', 'razor', 'nec'},
        )
        self.assertEqual(set(lock['components']), {'lina', 'luna', 'koko'})
        for name in ('lina', 'luna', 'koko'):
            self.assertEqual(components[name]['status'], 'supported')
            self.assertEqual(len(lock['components'][name]['commit']), 40)

    def test_unavailable_components_have_explanation(self):
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads((root / 'supported-components.json').read_text(encoding='utf-8'))
        for name in ('lion', 'chen', 'magnus', 'razor', 'nec'):
            with self.subTest(component=name):
                self.assertEqual(manifest['components'][name]['status'], 'unavailable')
                self.assertTrue(manifest['components'][name].get('reason'))
