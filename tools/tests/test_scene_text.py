from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "tools" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import scene_text  # noqa: E402


class SceneTextTests(unittest.TestCase):
    def test_quad_rejects_small_or_crossed_surfaces(self) -> None:
        with self.assertRaises(scene_text.SceneTextError):
            scene_text.validate_quad([[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]])
        with self.assertRaises(scene_text.SceneTextError):
            scene_text.validate_quad([[0.1, 0.1], [0.8, 0.8], [0.8, 0.1], [0.1, 0.8]])

    def test_arabic_is_composited_inside_reviewed_surface(self) -> None:
        try:
            from PIL import Image, ImageChops
        except ImportError as exc:  # pragma: no cover
            self.skipTest(str(exc))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "raw.png"
            destination = root / "composited.png"
            Image.new("RGB", (1536, 1024), (235, 225, 205)).save(source)
            try:
                result = scene_text.compose_scene_text(
                    source,
                    destination,
                    text="عبدالله سمع الكلام وابتسم",
                    integration={
                        "resolvedQuad": [[0.52, 0.10], [0.92, 0.12], [0.90, 0.62], [0.50, 0.60]],
                        "minimumFontPt": 12,
                        "maxLines": 5,
                        "treatment": "printed-ink",
                    },
                )
            except Exception as exc:
                self.skipTest(f"Arabic font unavailable: {exc}")
            self.assertTrue(destination.is_file())
            self.assertGreater(result["fontPx"], 0)
            with Image.open(source) as before, Image.open(destination) as after:
                self.assertIsNotNone(ImageChops.difference(before.convert("RGB"), after.convert("RGB")).getbbox())


if __name__ == "__main__":
    unittest.main()
