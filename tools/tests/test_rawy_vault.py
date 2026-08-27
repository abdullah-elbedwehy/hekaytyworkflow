from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "tools" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "rawy_story_pipeline", SCRIPTS / "story_pipeline.py"
)
assert SPEC and SPEC.loader
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)
rawy = pipeline.rawy_vault


def minimal_book(project: Path) -> dict:
    return {
        "schemaVersion": "2.0",
        "project": str(project),
        "createdAt": "2026-08-01T10:00:00+00:00",
        "updatedAt": "2026-08-02T10:00:00+00:00",
        "storyPath": None,
        "storyGoal": None,
        "storyReview": {
            "status": "not_prepared",
            "path": "input/story-review.md",
            "revision": 0,
        },
        "assets": [
            {"id": "character-sheet", "status": "planned", "includeInPdf": False},
            {"id": "cover", "status": "planned", "includeInPdf": True},
            {"id": "page-01", "status": "planned", "includeInPdf": True},
            {"id": "back-cover", "status": "planned", "includeInPdf": True},
        ],
        "pdf": {
            "draft": {"status": "planned", "path": None},
            "final": {"status": "planned", "path": None},
        },
        "review": {"status": "not_started", "pass": 0},
        "nextAction": "Capture the story goal.",
    }


class RawyVaultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        patcher = mock.patch.object(rawy, "repo_root", return_value=self.repo)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_configuration_is_rtl_core_only_and_has_empty_state(self) -> None:
        result = rawy.sync_rawy()
        vault = self.repo / "Rawy"
        app = json.loads((vault / ".obsidian/app.json").read_text(encoding="utf-8"))
        core = json.loads(
            (vault / ".obsidian/core-plugins.json").read_text(encoding="utf-8")
        )
        self.assertFalse(app["rightToLeft"])
        self.assertEqual("preview", app["defaultViewMode"])
        self.assertEqual("visible", app["propertiesInDocument"])
        self.assertTrue(core["bases"])
        self.assertEqual(
            [],
            json.loads(
                (vault / ".obsidian/community-plugins.json").read_text(
                    encoding="utf-8"
                )
            ),
        )
        self.assertFalse((vault / ".obsidian/plugins").exists())
        self.assertFalse((vault / "_Scripts").exists())
        self.assertFalse((vault / "_Stats.md").exists())
        for entry in app["userIgnoreFilters"]:
            self.assertTrue(
                entry.startswith("/") and entry.endswith("/"),
                f"ignore filter must be a regex Obsidian understands: {entry}",
            )
            re.compile(entry[1:-1])
        self.assertEqual(0, result["clients"])

    def test_new_client_duplicate_protection_and_field_preservation(self) -> None:
        result = rawy.create_client(
            name="عميل تجريبي",
            phone="01000000000",
            request="كتاب مغامرة",
            created="2026-08-03",
            slug="sample",
        )
        project = Path(result["client"])
        note = project / "Client.md"
        values, body = rawy.read_frontmatter(note)
        values.update(
            {
                "deadline": "2026-09-01",
                "payment": "deposit",
                "priority": "high",
                "blocker": "مراجعة العيلة",
            }
        )
        body = body.replace(
            "## ملاحظات / Notes\n\n",
            "## ملاحظات / Notes\n\nملاحظة خاصة لا تتغير.\n",
        )
        note.write_text(rawy.render_frontmatter(values) + body, encoding="utf-8")
        (project / "output").mkdir()
        (project / "output/book.json").write_text(
            json.dumps(minimal_book(project), ensure_ascii=False), encoding="utf-8"
        )

        rawy.sync_rawy(project)
        rawy.sync_rawy(project)
        after, after_body = rawy.read_frontmatter(note)
        self.assertEqual("01000000000", after["phone"])
        self.assertEqual("كتاب مغامرة", after["request"])
        self.assertEqual("2026-09-01", after["deadline"])
        self.assertEqual("deposit", after["payment"])
        self.assertEqual("high", after["priority"])
        self.assertEqual("مراجعة العيلة", after["blocker"])
        self.assertNotIn("generate-asset", str(after["next_action"]))
        self.assertIn("2026-09-01", after_body)
        self.assertIn("عربون / Deposit", after_body)
        self.assertIn("مراجعة العيلة", after_body)
        self.assertIn("[[Dashboard|🏠 راوي / Dashboard]]", after_body)
        self.assertNotIn("INPUT[", after_body)
        self.assertNotIn("BUTTON[", after_body)
        self.assertIn("ملاحظة خاصة لا تتغير.", after_body)
        self.assertEqual(1, after_body.count("## ملاحظات / Notes"))
        with self.assertRaises(rawy.RawyError):
            rawy.create_client(
                name="Duplicate", phone="1", request="Duplicate", slug="sample"
            )

    def test_path_policy_allows_only_direct_client_children(self) -> None:
        client = self.repo / "Rawy" / "Clients" / "one"
        self.assertTrue(rawy.is_rawy_client(client))
        self.assertFalse(rawy.is_rawy_client(client / "nested"))
        self.assertFalse(rawy.is_rawy_client(self.repo / "private"))

    def _make_migration_source(self, name: str) -> Path:
        source = self.base / name
        (source / "output").mkdir(parents=True)
        (source / "personas").mkdir()
        book = minimal_book(source)
        book["absoluteNote"] = f"source={source}"
        (source / "output/book.json").write_text(
            json.dumps(book, ensure_ascii=False), encoding="utf-8"
        )
        (source / "notes.md").write_text(
            f"Old folder: {source}\n", encoding="utf-8"
        )
        (source / "personas/face.png").write_bytes(b"unchanged-binary")
        return source

    def test_migration_rewrites_text_and_preserves_binary_and_progress(self) -> None:
        source = self._make_migration_source("external")
        before_hash = rawy._sha256(source / "personas/face.png")
        result = rawy.migrate_client(source, "client-one")
        target = Path(result["target"])
        self.assertFalse(source.exists())
        self.assertTrue(target.is_dir())
        self.assertEqual(before_hash, rawy._sha256(target / "personas/face.png"))
        self.assertNotIn(str(source), (target / "notes.md").read_text(encoding="utf-8"))
        self.assertEqual(2, len(result["rewritten"]))
        self.assertTrue((target / "Client.md").is_file())

    def test_migration_rolls_back_after_validation_failure(self) -> None:
        source = self._make_migration_source("rollback-source")
        original_manifest = rawy._binary_manifest

        def changed_manifest(path: Path) -> dict[str, str]:
            values = original_manifest(path)
            if path.name == "rollback-target":
                values["personas/face.png"] = "changed"
            return values

        with mock.patch.object(rawy, "_binary_manifest", side_effect=changed_manifest):
            with self.assertRaisesRegex(rawy.RawyError, "checksums changed"):
                rawy.migrate_client(source, "rollback-target")
        self.assertTrue(source.is_dir())
        self.assertFalse((self.repo / "Rawy/Clients/rollback-target").exists())
        self.assertIn(str(source), (source / "notes.md").read_text(encoding="utf-8"))


class GalleryAndArchiveTests(unittest.TestCase):
    """Two clicks the operator does constantly: see the art, put a job away."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        patcher = mock.patch.object(rawy, "repo_root", return_value=self.repo)
        patcher.start()
        self.addCleanup(patcher.stop)
        rawy.create_client(
            name="سما", phone="01000000000", request="كتاب", slug="sama"
        )
        self.project = self.repo / "Rawy" / "Clients" / "sama"

    def _with_images(self, *asset_ids: str) -> None:
        from PIL import Image

        book = minimal_book(self.project)
        assets = []
        for index, asset_id in enumerate(asset_ids, start=1):
            relative = f"output/images/raw/{asset_id}.v01.png"
            path = self.project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (8, 6), (120, 140, 160)).save(path)
            assets.append(
                {
                    "id": asset_id,
                    "status": "generated",
                    "includeInPdf": True,
                    "pdfOrder": index,
                    "imagePath": relative,
                }
            )
        book["assets"] = assets
        (self.project / "output").mkdir(parents=True, exist_ok=True)
        (self.project / "output" / "book.json").write_text(
            json.dumps(book, ensure_ascii=False), encoding="utf-8"
        )

    def test_a_client_with_no_images_still_gets_a_gallery(self) -> None:
        result = rawy.sync_client(self.project)
        gallery = Path(result["gallery"])
        self.assertTrue(gallery.is_file())
        self.assertEqual(0, result["images"])
        self.assertIn("مفيش صور", gallery.read_text(encoding="utf-8"))

    def test_the_gallery_embeds_every_image_in_book_order(self) -> None:
        """page-10 after page-2: alphabetical order would read as a shuffled book."""
        self._with_images("page-10", "cover", "page-02", "back-cover", "character-sheet")
        result = rawy.sync_client(self.project)
        text = Path(result["gallery"]).read_text(encoding="utf-8")
        self.assertEqual(5, result["images"])
        sections = [
            text.index("الشيتات المرجعية"),
            text.index("الأغلفة"),
            text.index("الصفحات"),
        ]
        self.assertEqual(sorted(sections), sections, "sections are out of order")
        # Inside a section, numeric page order — not alphabetical.
        self.assertLess(text.index("page-02 ·"), text.index("page-10 ·"))
        self.assertLess(text.index("cover ·"), text.index("back-cover ·"))
        self.assertIn("![[Clients/sama/output/images/raw/cover.v01.png]]", text)

    def test_the_client_note_links_straight_to_the_gallery(self) -> None:
        rawy.sync_client(self.project)
        note = (self.project / "Client.md").read_text(encoding="utf-8")
        self.assertIn("[!rawy-actions]", note)
        self.assertIn("[[Clients/sama/Gallery|", note)

    def test_every_image_gets_a_comment_box(self) -> None:
        self._with_images("cover", "page-02")
        result = rawy.sync_client(self.project)
        text = Path(result["gallery"]).read_text(encoding="utf-8")
        for asset_id in ("cover", "page-02"):
            self.assertIn(f"<!-- rawy-image-note:{asset_id}:start -->", text)
            self.assertIn(f"<!-- rawy-image-note:{asset_id}:end -->", text)

    def test_a_note_survives_regenerating_the_gallery(self) -> None:
        """Losing a reviewer's objection on sync is worse than no box at all."""
        self._with_images("cover", "page-02")
        gallery = Path(rawy.sync_client(self.project)["gallery"])
        text = gallery.read_text(encoding="utf-8")
        text = text.replace(
            "> <!-- rawy-image-note:page-02:start -->\n> \n",
            "> <!-- rawy-image-note:page-02:start -->\n> الطيارة غامقة أوي\n",
            1,
        )
        gallery.write_text(text, encoding="utf-8")

        result = rawy.sync_client(self.project)
        after = Path(result["gallery"]).read_text(encoding="utf-8")
        self.assertIn("الطيارة غامقة أوي", after)
        self.assertEqual(["page-02"], result["imageNotes"])

    def test_reading_notes_strips_the_callout_markup(self) -> None:
        self._with_images("cover")
        gallery = Path(rawy.sync_client(self.project)["gallery"])
        text = gallery.read_text(encoding="utf-8").replace(
            "> <!-- rawy-image-note:cover:start -->\n> \n",
            "> <!-- rawy-image-note:cover:start -->\n> سطر أول\n> سطر تاني\n",
            1,
        )
        gallery.write_text(text, encoding="utf-8")
        notes = rawy.read_image_notes(self.project)
        self.assertEqual("سطر أول\nسطر تاني", notes["cover"])

    def test_an_empty_box_is_not_reported_as_a_note(self) -> None:
        self._with_images("cover")
        result = rawy.sync_client(self.project)
        self.assertEqual([], result["imageNotes"])
        self.assertEqual({}, rawy.read_image_notes(self.project))

    def test_a_flagged_image_is_called_out_at_the_top(self) -> None:
        """Scrolling 24 images to find the one you objected to is the failure mode."""
        self._with_images("cover", "page-02")
        gallery = Path(rawy.sync_client(self.project)["gallery"])
        text = gallery.read_text(encoding="utf-8").replace(
            "> <!-- rawy-image-note:page-02:start -->\n> \n",
            "> <!-- rawy-image-note:page-02:start -->\n> غامقة\n",
            1,
        )
        gallery.write_text(text, encoding="utf-8")
        rawy.sync_client(self.project)
        after = gallery.read_text(encoding="utf-8")
        self.assertIn("عليها ملاحظات", after)
        # Written-in boxes render expanded; empty ones stay folded away.
        self.assertIn("[!rawy-note]+", after)
        self.assertIn("[!rawy-note]-", after)
        note = (self.project / "Client.md").read_text(encoding="utf-8")
        self.assertIn("1 noted", note)

    def test_archiving_hides_a_client_without_moving_anything(self) -> None:
        self._with_images("cover")
        rawy.set_archived(self.project, archived=True)
        values, _ = rawy.read_frontmatter(self.project / "Client.md")
        self.assertTrue(values["archived"])
        self.assertTrue(values["archived_at"])
        self.assertTrue(self.project.is_dir(), "archiving must not move the folder")
        self.assertTrue((self.project / "output" / "book.json").is_file())

    def test_an_archived_client_stops_asking_for_attention(self) -> None:
        self._with_images("cover")
        note = self.project / "Client.md"
        values, body = rawy.read_frontmatter(note)
        values["blocker"] = "مستني رد العميل"
        rawy._write(note, rawy.render_frontmatter(values) + body)
        rawy.sync_client(self.project)
        self.assertTrue(rawy.read_frontmatter(note)[0]["needs_attention"])

        rawy.set_archived(self.project, archived=True)
        self.assertFalse(rawy.read_frontmatter(note)[0]["needs_attention"])

    def test_restoring_brings_the_client_back(self) -> None:
        rawy.set_archived(self.project, archived=True)
        result = rawy.set_archived(self.project, archived=False)
        self.assertFalse(result["archived"])
        values, _ = rawy.read_frontmatter(self.project / "Client.md")
        self.assertFalse(values["archived"])
        self.assertNotIn("archived_at", values)

    def test_archiving_twice_is_not_reported_as_a_change(self) -> None:
        rawy.set_archived(self.project, archived=True)
        self.assertFalse(rawy.set_archived(self.project, archived=True)["changed"])

    def test_the_archive_note_lists_what_the_active_views_hide(self) -> None:
        rawy.sync_rawy()
        empty = (self.repo / "Rawy" / "Archive.md").read_text(encoding="utf-8")
        self.assertIn("مفيش عملاء مؤرشفين", empty)

        rawy.set_archived(self.project, archived=True)
        rawy.sync_rawy()
        listed = (self.repo / "Rawy" / "Archive.md").read_text(encoding="utf-8")
        self.assertIn("[[Clients/sama/Client|سما]]", listed)
        self.assertEqual(1, len(rawy.archived_clients()))

    def test_archiving_a_folder_outside_clients_is_refused(self) -> None:
        stray = self.base / "elsewhere"
        stray.mkdir()
        with self.assertRaises(rawy.RawyError):
            rawy.set_archived(stray, archived=True)


class RawyTrackedShellTests(unittest.TestCase):
    def test_dashboard_and_bases_do_not_expose_phone(self) -> None:
        dashboard = (ROOT / "Rawy/Dashboard.md").read_text(encoding="utf-8")
        base = (ROOT / "Rawy/Clients.base").read_text(encoding="utf-8")
        self.assertNotIn("phone", dashboard.lower())
        self.assertNotIn("phone", base.lower())
        for view in ("Needs attention", "All"):
            self.assertRegex(base, rf'(?m)^\s+name:\s+"?{view}"?$')
            self.assertIn(f"![[Clients.base#{view}]]", dashboard)

    def test_opening_clients_lands_on_a_view_that_lists_clients(self) -> None:
        """Obsidian opens the first view. "Needs attention" is empty when nothing
        is blocked, which is the normal state — landing there reads as a broken
        vault with no clients in it."""
        base = (ROOT / "Rawy/Clients.base").read_text(encoding="utf-8")
        names = re.findall(r'(?m)^\s+name:\s+"?([^"\n]+)"?$', base)
        self.assertTrue(names, "no views declared")
        self.assertNotEqual(
            "Needs attention", names[0], "Clients opens on an empty view"
        )

    def test_archived_clients_are_filtered_out_of_the_active_views(self) -> None:
        base = (ROOT / "Rawy/Clients.base").read_text(encoding="utf-8")
        self.assertEqual(2, base.count("archived != true"))
        self.assertIn("archived == true", base)

    def test_dashboard_actions_need_no_community_plugin(self) -> None:
        dashboard = (ROOT / "Rawy/Dashboard.md").read_text(encoding="utf-8")
        self.assertNotIn("BUTTON[", dashboard)
        self.assertNotIn("INPUT[", dashboard)
        self.assertNotIn("```meta-bind", dashboard)
        # Every action is a link core Obsidian can follow on its own.
        self.assertIn("[[Clients.base|", dashboard)
        self.assertIn("obsidian://new?vault=Rawy&file=", dashboard)
        self.assertEqual(
            [],
            json.loads(
                (ROOT / "Rawy/.obsidian/community-plugins.json").read_text(
                    encoding="utf-8"
                )
            ),
        )
        self.assertFalse((ROOT / "Rawy/.obsidian/plugins").exists())

    def test_cursor_dark_css_and_activation_are_tracked(self) -> None:
        css = (ROOT / "Rawy/.obsidian/snippets/rawy.css").read_text(encoding="utf-8")
        appearance = json.loads(
            (ROOT / "Rawy/.obsidian/appearance.json").read_text(encoding="utf-8")
        )
        self.assertIn("#141414", css.lower())
        self.assertIn("#82a4c9", css.lower())
        self.assertNotIn(".workspace-split.mod-left-split", css)
        self.assertNotIn('[data-type="file-explorer"]', css)
        self.assertIn(".rawy-client", css)
        self.assertIn("direction: rtl", css)
        self.assertIn('.callout[data-callout="rawy-actions"] a', css)
        self.assertEqual("#82a4c9", appearance["accentColor"])
        self.assertIn("rawy", appearance["enabledCssSnippets"])

    def test_privacy_paths_are_git_ignored(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/Rawy/Clients/", ignore)
        # Archive.md is generated at the vault root, outside Clients/, and lists
        # real client names — it must be ignored explicitly or it ships in a commit.
        self.assertIn("/Rawy/Archive.md", ignore)

    def test_local_dispatcher_dry_run_needs_no_home_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            output = root / "page.png"
            jobs = root / "jobs.json"
            jobs.write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "id": "page-01",
                                "prompt": "A child-safe storybook scene",
                                "output": str(output),
                                "references": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = pipeline.subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "codex_imagegen_dispatch.py"),
                    "--jobs",
                    str(jobs),
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn(".cursor/skills", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
