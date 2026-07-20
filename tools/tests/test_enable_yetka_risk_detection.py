import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "enable_yetka_risk_detection.py"
SPEC = importlib.util.spec_from_file_location("enable_yetka_risk_detection", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class YetkaUiPatchTests(TestCase):
    def test_turkish_element_locale_patch_is_idempotent(self):
        with TemporaryDirectory() as directory:
            asset_dir = Path(directory)
            (asset_dir / "RiskDetect.fixture.js").write_text(
                MODULE.LICENSE_GATED_RENDER,
                encoding="utf-8",
            )
            bundle = asset_dir / "index.fixture.js"
            bundle.write_text(
                ",".join(
                    (
                        MODULE.LICENSE_STORE_GATE,
                        MODULE.ELEMENT_LOCALE_MAP,
                        MODULE.ELEMENT_LOCALE_LOOKUP,
                    )
                ),
                encoding="utf-8",
            )

            with patch.object(MODULE, "ASSET_DIR", asset_dir):
                MODULE.main()
                first = bundle.read_text(encoding="utf-8")
                MODULE.main()
                second = bundle.read_text(encoding="utf-8")

            self.assertEqual(first, second)
            self.assertEqual(first.count("tr:YTl"), 2)
            self.assertIn("emptyText:`Veri yok`", first)
            self.assertIn("total:`Toplam {total}`", first)
            self.assertIn("en:Uu", first)

    def test_visible_turkish_labels_are_valid(self):
        translations = json.loads(
            (ROOT / "apps" / "i18n" / "lina" / "tr.json").read_text(encoding="utf-8")
        )

        self.assertEqual(translations["Today"], "Bugün")
        self.assertEqual(translations["MenuPermissions"], "POLİTİKALAR")
        self.assertEqual(translations["MenuMore"], "DİĞERLERİ")


if __name__ == "__main__":
    main()
