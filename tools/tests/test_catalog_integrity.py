"""Catalog invariants that silently break the workflow when violated.

These are cheap checks for expensive failures: a theme whose fingerprint does
not appear in its own style.medium makes validate-prompts reject every prompt
for that theme, which only shows up after a family has already picked it.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS / "scripts"))

import story_pipeline as pipeline  # noqa: E402


def load(*parts: str) -> dict:
    return json.loads((TOOLS / "references" / Path(*parts)).read_text(encoding="utf-8"))


class ThemeCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.themes = load("themes", "catalog.json")["themes"]

    def test_fingerprint_appears_in_style_medium(self) -> None:
        """validate-prompts requires the fingerprint inside style.medium."""
        for theme_id, theme in self.themes.items():
            with self.subTest(theme=theme_id):
                self.assertIn(
                    theme["fingerprint"].lower(),
                    theme["style"]["medium"].lower(),
                    f"{theme_id}: fingerprint is not a substring of style.medium, "
                    "so every prompt using this theme would fail validation",
                )

    def test_every_theme_has_required_fields(self) -> None:
        required = (
            "themeId",
            "label",
            "labelAr",
            "fingerprint",
            "visualStyle",
            "style",
            "textBlendHint",
            "compiledPromptStyleBlock",
        )
        for theme_id, theme in self.themes.items():
            with self.subTest(theme=theme_id):
                for key in required:
                    self.assertTrue(theme.get(key), f"{theme_id} missing {key}")
                self.assertEqual(theme["themeId"], theme_id)

    def test_style_ref_dirs_exist(self) -> None:
        for theme_id, theme in self.themes.items():
            ref_dir = theme.get("styleRefDir")
            if not ref_dir:
                continue
            with self.subTest(theme=theme_id):
                path = TOOLS / "references" / "themes" / ref_dir
                self.assertTrue(path.is_dir(), f"{theme_id}: missing {path}")
                self.assertTrue(
                    list(path.glob(theme.get("styleRefGlob") or "ref-*.png")),
                    f"{theme_id}: styleRefGlob matches no files in {path}",
                )


class GuestCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guests = load("guests", "catalog.json")["guests"]

    def test_descriptions_are_long_enough(self) -> None:
        for key, guest in self.guests.items():
            with self.subTest(guest=key):
                self.assertGreaterEqual(
                    len(guest["appearanceNotes"]),
                    pipeline.MIN_GUEST_DESCRIPTION_CHARS,
                    f"{key}: too thin to keep the model off the franchise design",
                )

    def test_no_franchise_names_leak_into_the_library(self) -> None:
        """The stand-ins must not name what they stand in for."""
        for key, guest in self.guests.items():
            with self.subTest(guest=key):
                for field in ("displayName", "appearanceNotes"):
                    self.assertEqual(
                        pipeline.find_franchise_name_hits(guest[field]),
                        [],
                        f"{key}.{field} contains a franchise name",
                    )


class ArabicDetectionTests(unittest.TestCase):
    def test_catches_arabic_franchise_names(self) -> None:
        for text in (
            "سبايدر مان بيتسلق الحيطة",
            "سبايدرمان",
            "الرجل العنكبوت",
            "إلسا بتعمل تلج",
            "السا بتعمل تلج",
            "وإلسا معاهم",
            "ميكى ماوس",
            "باتمان",
        ):
            with self.subTest(text=text):
                self.assertTrue(pipeline.find_franchise_name_hits(text), text)

    def test_does_not_flag_ordinary_arabic(self) -> None:
        """Folded names sit inside common words; boundaries must protect them."""
        for text in (
            "الساحة كانت مليانة",
            "الساعة خمسة",
            "الساحر الطيب",
            "شارع السلام",
            "بابا قال أنا جعان",
            "سارة وياسمين في الحديقة",
            "الشريك بتاعه",
            "الساحل الشمالي",
        ):
            with self.subTest(text=text):
                self.assertEqual(pipeline.find_franchise_name_hits(text), [], text)


class OrientationTests(unittest.TestCase):
    def test_page_ids_are_two_covers_plus_interior(self) -> None:
        ids = pipeline.build_pdf_asset_ids(24)
        self.assertEqual(len(ids), 24)
        self.assertEqual(ids[0], "cover")
        self.assertEqual(ids[-1], "back-cover")
        self.assertEqual(ids[1], "page-01")
        self.assertEqual(ids[-2], "page-22")

    def test_covers_generate_after_the_interior(self) -> None:
        book = {"settings": {"pdfPageCount": 24}}
        order = pipeline.generation_order(book)
        self.assertEqual(order[-2:], ["cover", "back-cover"])
        self.assertEqual(order[0], "page-01")


if __name__ == "__main__":
    unittest.main()
