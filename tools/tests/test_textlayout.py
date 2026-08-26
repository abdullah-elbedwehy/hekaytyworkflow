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


def measure(text: str, size: float) -> float:
    """Stand-in font metric: every glyph is half an em wide.

    Keeps the geometry tests independent of which .ttf happens to be bundled.
    """
    return len(text) * size * 0.5


class CaptionLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.zone = tl.safe_zone_rect(1000.0, 700.0)

    def test_caption_fits_inside_the_band(self) -> None:
        layout = tl.layout_caption("البنت راحت السوق مع جدتها", self.zone, measure)
        self.assertTrue(layout.lines)
        for line in layout.lines:
            self.assertGreaterEqual(line.x, self.zone.x)
            self.assertLessEqual(
                line.x + measure(line.shaped, layout.font_size),
                self.zone.x + self.zone.width,
            )
            self.assertGreater(line.baseline, self.zone.y)
            self.assertLess(line.baseline, self.zone.top)

    def test_lines_are_right_aligned(self) -> None:
        layout = tl.layout_caption(
            "كلمة تانية وكمان كلمة تالتة ورابعة وخامسة وسادسة وسابعة",
            self.zone,
            measure,
        )
        self.assertGreater(len(layout.lines), 1)
        rights = {
            round(line.x + measure(line.shaped, layout.font_size), 3)
            for line in layout.lines
        }
        self.assertEqual(1, len(rights), "every line should share a right edge")

    def test_lines_run_top_to_bottom(self) -> None:
        layout = tl.layout_caption(
            "واحد اتنين تلاتة أربعة خمسة ستة سبعة تمانية تسعة عشرة",
            self.zone,
            measure,
        )
        baselines = [line.baseline for line in layout.lines]
        self.assertEqual(baselines, sorted(baselines, reverse=True))

    def test_longer_text_gets_a_smaller_size(self) -> None:
        short = tl.layout_caption("قال بابا", self.zone, measure)
        long = tl.layout_caption(
            "قال بابا لسارة تعالي نشوف القمر وهو بيطلع من ورا البيوت "
            "وناخد معانا الكلب الصغير عشان يلعب في الجنينة",
            self.zone,
            measure,
        )
        self.assertGreater(short.font_size, long.font_size)

    def test_logical_text_is_preserved_for_actual_text(self) -> None:
        source = "البنت راحت السوق"
        layout = tl.layout_caption(source, self.zone, measure)
        self.assertEqual(source, layout.logical_text)
        for line in layout.lines:
            self.assertNotEqual(line.logical, line.shaped)

    def test_empty_caption_is_rejected(self) -> None:
        with self.assertRaises(tl.TextLayoutError):
            tl.layout_caption("   ", self.zone, measure)

    def test_caption_that_cannot_fit_raises_actionable(self) -> None:
        with self.assertRaises(tl.TextLayoutError) as ctx:
            tl.layout_caption("كلمة " * 400, self.zone, measure)
        self.assertIn("Shorten the page text", str(ctx.exception))


class WrapTests(unittest.TestCase):
    def test_wraps_on_width(self) -> None:
        lines = tl.wrap_words(["واحد", "اتنين", "تلاتة"], measure, 10.0, 60.0)
        self.assertIsNotNone(lines)
        assert lines is not None
        self.assertGreater(len(lines), 1)

    def test_word_too_wide_signals_a_retry(self) -> None:
        self.assertIsNone(tl.wrap_words(["كلمةطويلةجدا"], measure, 40.0, 20.0))


class SafeZoneTests(unittest.TestCase):
    def test_rect_sits_inside_the_page(self) -> None:
        zone = tl.safe_zone_rect(1000.0, 800.0)
        self.assertGreaterEqual(zone.x, 0)
        self.assertGreaterEqual(zone.y, 0)
        self.assertLessEqual(zone.x + zone.width, 1000.0)
        self.assertLessEqual(zone.top, 800.0)

    def test_rect_is_a_bottom_band(self) -> None:
        zone = tl.safe_zone_rect(1000.0, 800.0)
        # band top stays in the lower half of the page
        self.assertLess(zone.top, 800.0 * 0.5)

    def test_rect_rejects_nonpositive_page(self) -> None:
        with self.assertRaises(tl.TextLayoutError):
            tl.safe_zone_rect(0, 800.0)

    def test_norm_topleft_is_fractional_and_consistent(self) -> None:
        norm = tl.safe_zone_norm_topleft()
        for key in ("x", "y", "width", "height"):
            self.assertGreaterEqual(norm[key], 0.0)
            self.assertLessEqual(norm[key], 1.0)
        self.assertLessEqual(norm["y"] + norm["height"], 1.0)
        # same horizontal inset as the absolute rect
        self.assertAlmostEqual(norm["x"], tl.SAFE_ZONE["marginX"])

    def test_prompt_clause_forbids_text(self) -> None:
        clause = tl.safe_zone_prompt_clause()
        self.assertIn("NO text", clause)
        self.assertRegex(clause, r"\d+%")


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


if __name__ == "__main__":
    unittest.main()
