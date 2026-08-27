"""Brightness is measured, never corrected.

An earlier version of this module graded every render onto brightness targets.
The numbers were excellent and the pictures were wrong: lifting a warm, lamp-lit
room pushed it orange (Lab b* 25.6 -> 40.0 on page-19). These tests exist partly
to keep that from coming back.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS / "scripts"))

import color_grade as cg  # noqa: E402


def has_pillow() -> bool:
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    return True


def page(*, base: int, spread: int = 60):
    """A stand-in page: a gradient, so it has real shadows and highlights."""
    from PIL import Image

    image = Image.new("RGB", (64, 48))
    pixels = image.load()
    for y in range(48):
        for x in range(64):
            value = max(0, min(255, base - spread + (x * 2 * spread) // 64))
            pixels[x, y] = (value, value, value)
    return image


@unittest.skipUnless(has_pillow(), "Pillow not installed")
class MeasurementTests(unittest.TestCase):
    def test_it_reports_the_shape_of_the_page(self) -> None:
        measured = cg.analyze(page(base=128))
        for key in ("meanLuma", "p05", "median", "p95", "shadowPercent", "saturation"):
            self.assertIn(key, measured)

    def test_percentiles_are_ordered(self) -> None:
        measured = cg.analyze(page(base=128))
        self.assertLessEqual(measured["p05"], measured["median"])
        self.assertLessEqual(measured["median"], measured["p95"])

    def test_a_dark_page_reports_a_large_shadow_share(self) -> None:
        self.assertGreater(cg.analyze(page(base=40))["shadowPercent"], 50)

    def test_a_bright_page_reports_almost_no_shadow(self) -> None:
        self.assertLess(cg.analyze(page(base=200))["shadowPercent"], 1)


@unittest.skipUnless(has_pillow(), "Pillow not installed")
class VerdictTests(unittest.TestCase):
    def test_a_bright_page_passes(self) -> None:
        verdict = cg.brightness_verdict(cg.analyze(page(base=170)))
        self.assertTrue(verdict["bright_enough"], verdict["reasons"])

    def test_a_heavy_page_is_flagged_with_a_reason(self) -> None:
        verdict = cg.brightness_verdict(cg.analyze(page(base=45)))
        self.assertFalse(verdict["bright_enough"])
        self.assertTrue(verdict["reasons"])

    def test_crushed_shadows_are_named_specifically(self) -> None:
        verdict = cg.brightness_verdict(cg.analyze(page(base=55)))
        self.assertTrue(
            any("crushed" in reason or "shadow" in reason for reason in verdict["reasons"]),
            verdict["reasons"],
        )


class NoEditingTests(unittest.TestCase):
    """The module must not grow a corrector again.

    Every version of the grade changed the model's colour — including one with
    the chroma restore switched off, because raising L raises Lab chroma on its
    own. Brightness is fixed in the prompt, at generation.
    """

    def test_the_module_exposes_no_way_to_alter_a_render(self) -> None:
        for name in ("grade", "tone_lut", "solve_gamma", "preserve_white_balance"):
            self.assertFalse(
                hasattr(cg, name), f"{name} would edit the art; brightness is a prompt fix"
            )


if __name__ == "__main__":
    unittest.main()
