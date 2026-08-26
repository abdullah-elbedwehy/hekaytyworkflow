from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "story_pipeline", ROOT / "tools" / "scripts" / "story_pipeline.py"
)
assert SPEC and SPEC.loader
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)

vault = pipeline.obsidian_vault
doctrine = pipeline.doctrine


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ObsidianConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def test_config_is_rtl_and_needs_no_community_plugin(self) -> None:
        vault.write_obsidian_config(self.root)
        app = read_json(self.root / ".obsidian" / "app.json")
        self.assertTrue(app["rightToLeft"])
        self.assertEqual([], read_json(self.root / ".obsidian" / "community-plugins.json"))
        core = read_json(self.root / ".obsidian" / "core-plugins.json")
        self.assertTrue(core["global-search"])
        self.assertTrue(core["templates"])

    def test_ignore_filters_keep_heavy_folders_out_of_the_index(self) -> None:
        vault.write_obsidian_config(self.root, ignore_filters=["output/images/"])
        app = read_json(self.root / ".obsidian" / "app.json")
        self.assertIn("output/images/", app["userIgnoreFilters"])

    def test_config_is_idempotent(self) -> None:
        vault.write_obsidian_config(self.root)
        first = (self.root / ".obsidian" / "app.json").read_text(encoding="utf-8")
        vault.write_obsidian_config(self.root)
        self.assertEqual(first, (self.root / ".obsidian" / "app.json").read_text(encoding="utf-8"))


class StudioVaultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.result = vault.build_studio_vault(self.root)

    def test_every_expected_note_is_generated(self) -> None:
        notes = self.root / "vault"
        for relative in (
            "Home.md",
            "00-Doctrine/قواعد الـHandoff.md",
            "00-Doctrine/تصنيف القصص.md",
            "00-Doctrine/هيكل الكتاب.md",
            "00-Doctrine/ألوان آمنة للطباعة.md",
            "00-Doctrine/قواعد أداة الصور.md",
            "01-Checklists/جيت ما قبل البرومبتات.md",
            "01-Checklists/جيت ما قبل المطبعة.md",
            "03-Status/حالة المشروع.md",
            "04-Runbook/Manual Image Lane.md",
            "90-Templates/كتاب جديد.md",
        ):
            with self.subTest(note=relative):
                self.assertTrue((notes / relative).is_file(), relative)

    def test_generated_notes_are_stamped_and_warn_against_hand_edits(self) -> None:
        text = (self.root / "vault" / "00-Doctrine" / "هيكل الكتاب.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("generated: true", text)
        self.assertIn(doctrine.load_doctrine()["doctrineVersion"], text)
        self.assertIn("build-vault", text)

    def test_structure_note_renders_the_real_numbers(self) -> None:
        text = (self.root / "vault" / "00-Doctrine" / "هيكل الكتاب.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`page-01`", text)
        self.assertIn("`page-22`", text)
        self.assertIn("لـ [اسم الطفل] 💛", text)
        self.assertIn("🎮 ألعاب تفاعلية", text)

    def test_one_note_per_known_book_plus_a_tracker(self) -> None:
        books = self.root / "vault" / "02-Books"
        self.assertTrue((books / "_متابعة الكتب.md").is_file())
        for story in doctrine.load_doctrine()["projectStatus"]["stories"]:
            self.assertTrue((books / f"{story['titleAr']}.md").is_file())

    def test_rebuild_never_clobbers_a_hand_edited_book_note(self) -> None:
        note = self.root / "vault" / "02-Books" / "كريم وصقر النور.md"
        note.write_text("# ملاحظاتي أنا\n", encoding="utf-8")
        vault.build_studio_vault(self.root)
        self.assertEqual("# ملاحظاتي أنا\n", note.read_text(encoding="utf-8"))

    def test_bookmarks_point_at_files_that_exist(self) -> None:
        bookmarks = read_json(self.root / ".obsidian" / "bookmarks.json")
        self.assertTrue(bookmarks["items"])
        for item in bookmarks["items"]:
            if item["path"].startswith("vault/"):
                self.assertTrue((self.root / item["path"]).is_file(), item["path"])


class ClientVaultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()
        personas = self.project / "personas"
        personas.mkdir()
        (personas / "ahmed.png").write_bytes(b"test fixture")
        pipeline.command_init(
            argparse.Namespace(project=self.project, pages=pipeline.DEFAULT_PDF_PAGES)
        )

    def test_init_leaves_an_openable_vault(self) -> None:
        self.assertTrue((self.project / ".obsidian" / "app.json").is_file())
        self.assertTrue((self.project / ".obsidian" / "bookmarks.json").is_file())
        home = (self.project / "Home.md").read_text(encoding="utf-8")
        self.assertIn("[[story-review]]", home)
        self.assertIn("hekayati:", home)

    def test_home_shows_this_book_structure(self) -> None:
        home = (self.project / "Home.md").read_text(encoding="utf-8")
        self.assertIn("`page-01`", home)
        self.assertIn("`page-22`", home)

    def test_review_notes_are_created_once_and_never_overwritten(self) -> None:
        notes = self.project / "_مراجعتي.md"
        notes.write_text("# ملاحظاتي\n", encoding="utf-8")
        pipeline.command_init_vault(argparse.Namespace(project=self.project))
        self.assertEqual("# ملاحظاتي\n", notes.read_text(encoding="utf-8"))

    def test_manual_dispatch_directory_is_ready(self) -> None:
        self.assertTrue((self.project / "output" / "manual").is_dir())

    def test_init_vault_is_safe_on_a_folder_with_no_book(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bare = Path(tmp).resolve()
            result = pipeline.command_init_vault(argparse.Namespace(project=bare))
            self.assertTrue((bare / ".obsidian" / "app.json").is_file())
            self.assertIn("Home.md", result["home"])


if __name__ == "__main__":
    unittest.main()
