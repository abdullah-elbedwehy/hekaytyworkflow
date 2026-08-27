from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "scripts" / "textlayout.py"
SPEC = importlib.util.spec_from_file_location("textlayout", MODULE_PATH)
assert SPEC and SPEC.loader
tl = importlib.util.module_from_spec(SPEC)
# Register before exec: the frozen dataclass with `from __future__ import
# annotations` resolves its field types via sys.modules[__name__] at class-build
# time. A normal import registers it automatically; a bare module_from_spec load
# must do it explicitly, or class creation raises regardless of test order.
sys.modules["textlayout"] = tl
SPEC.loader.exec_module(tl)


class FontResolutionTests(unittest.TestCase):
    def test_settings_font_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            font = Path(tmp) / "Cairo-Regular.ttf"
            font.write_bytes(b"\x00\x01")
            resolved = tl.resolve_arabic_font({"textFont": str(font)})
            self.assertEqual(font.resolve(), resolved)

    def test_env_used_when_no_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            font = Path(tmp) / "Amiri-Regular.ttf"
            font.write_bytes(b"\x00\x01")
            prev = os.environ.get(tl.FONT_ENV_VAR)
            os.environ[tl.FONT_ENV_VAR] = str(font)
            try:
                self.assertEqual(font.resolve(), tl.resolve_arabic_font(None))
            finally:
                if prev is None:
                    os.environ.pop(tl.FONT_ENV_VAR, None)
                else:
                    os.environ[tl.FONT_ENV_VAR] = prev

    def test_missing_font_raises_actionable(self) -> None:
        prev = os.environ.get(tl.FONT_ENV_VAR)
        os.environ.pop(tl.FONT_ENV_VAR, None)
        try:
            # Only raises when nothing is bundled; skip if a repo font exists.
            if tl.BUNDLED_FONT_DIR.is_dir() and any(tl.BUNDLED_FONT_DIR.glob("*.ttf")):
                self.skipTest("a bundled font is present")
            with self.assertRaises(tl.TextLayoutError):
                tl.resolve_arabic_font({"textFont": "  "})
        finally:
            if prev is not None:
                os.environ[tl.FONT_ENV_VAR] = prev


class ShapeArabicTests(unittest.TestCase):
    def test_empty_is_empty(self) -> None:
        self.assertEqual("", tl.shape_arabic(""))

    def test_shaping_reorders_when_deps_present(self) -> None:
        try:
            import arabic_reshaper  # noqa: F401
            from bidi.algorithm import get_display  # noqa: F401
        except ImportError:
            self.skipTest("arabic-reshaper / python-bidi not installed")
        src = "مرحبا"
        out = tl.shape_arabic(src)
        self.assertTrue(out)
        # reshaping + bidi produce presentation-form glyphs in visual order, so
        # the output differs from the logical-order source string
        self.assertNotEqual(src, out)


class NoCaptionOverlayTests(unittest.TestCase):
    """The caption band is gone: story text is composed inside the art."""

    def test_overlay_helpers_are_removed(self) -> None:
        for name in (
            "SAFE_ZONE",
            "safe_zone_rect",
            "safe_zone_norm_topleft",
            "safe_zone_prompt_clause",
            "layout_caption",
            "wrap_words",
        ):
            self.assertFalse(hasattr(tl, name), f"{name} should no longer exist")


if __name__ == "__main__":
    unittest.main()
