from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import handoff_fixture  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "story_pipeline", ROOT / "tools" / "scripts" / "story_pipeline.py"
)
assert SPEC and SPEC.loader
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)

doctrine = pipeline.doctrine
manual_dispatch = pipeline.manual_dispatch


class DoctrineFileTests(unittest.TestCase):
    def test_doctrine_and_handoff_document_both_exist(self) -> None:
        self.assertTrue(doctrine.DOCTRINE_PATH.is_file())
        self.assertTrue(doctrine.HANDOFF_PATH.is_file())
        text = doctrine.HANDOFF_PATH.read_text(encoding="utf-8")
        self.assertIn("Source of Truth", text)

    def test_doctrine_validates_on_load(self) -> None:
        payload = doctrine.load_doctrine(refresh=True)
        self.assertEqual(1, payload["schemaVersion"])
        self.assertEqual("hekayati-22", payload["bookStructure"]["id"])

    def test_broken_doctrine_is_rejected_not_silently_used(self) -> None:
        broken = copy.deepcopy(doctrine.load_doctrine())
        broken["bookStructure"]["pdfPageCount"] = 99
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doctrine.json"
            path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
            original = doctrine.DOCTRINE_PATH
            try:
                doctrine.DOCTRINE_PATH = path
                with self.assertRaises(doctrine.DoctrineError):
                    doctrine.load_doctrine(refresh=True)
            finally:
                doctrine.DOCTRINE_PATH = original
                doctrine.load_doctrine(refresh=True)


class BookStructureTests(unittest.TestCase):
    def test_pipeline_default_follows_the_doctrine(self) -> None:
        self.assertEqual(doctrine.doctrine_pdf_page_count(), pipeline.DEFAULT_PDF_PAGES)
        self.assertEqual(24, pipeline.DEFAULT_PDF_PAGES)

    def test_slots_name_every_structural_page(self) -> None:
        slots = doctrine.structure_slots(24)
        self.assertEqual("page-01", slots["dedication"])
        self.assertEqual("page-22", slots["otherStories"])
        self.assertEqual(20, slots["storyPageCount"])
        self.assertEqual("page-02", slots["storyPages"][0])
        self.assertEqual("page-21", slots["storyPages"][-1])

    def test_dedication_uses_the_fixed_template_with_the_child_name(self) -> None:
        text = doctrine.dedication_text("سما")
        self.assertIn("لـ سما 💛", text)
        self.assertIn("بحبك، بابا وماما", text)
        self.assertNotIn("{{hero}}", text)

    def test_back_cover_carries_the_five_mandatory_icons(self) -> None:
        icons = doctrine.back_cover_icons()
        self.assertEqual(5, len(icons))
        self.assertEqual(
            ["🎮", "🎨", "⭐", "📖", "🎁"], [icon["emoji"] for icon in icons]
        )


class DoctrineTextScanTests(unittest.TestCase):
    def test_metaphor_for_inner_feeling_is_blocking(self) -> None:
        for text in (
            "حس إن حد سرق مكانه",
            "قلبه بقى أكبر",
            "التقيلة في صدره خفت",
            "الحب مش زي الحلوى",
        ):
            with self.subTest(text=text):
                hits = doctrine.scan_text(text)
                self.assertTrue(hits, text)
                self.assertEqual("high", hits[0]["severity"])

    def test_diacritics_and_hamza_cannot_smuggle_a_banned_phrase(self) -> None:
        self.assertTrue(doctrine.scan_text("قلبُه بقي أكبر"))
        self.assertTrue(doctrine.scan_text("التقيله فى صدرها خفت"))

    def test_direct_feeling_and_concrete_action_pass(self) -> None:
        self.assertEqual([], doctrine.scan_text("حد أخد مكانه وحب بابا وماما منه"))
        self.assertEqual([], doctrine.scan_text("ماما حضنته وقالتله أنا بحبك اوي اوي"))

    def test_unearned_reward_and_food_sharing_are_blocking(self) -> None:
        self.assertTrue(doctrine.scan_text("عشان إنت أخوها الكبير"))
        self.assertTrue(doctrine.scan_text("كل من ساندوتش صاحبه"))

    def test_abstract_concept_cannot_be_the_grammatical_actor(self) -> None:
        self.assertTrue(doctrine.scan_text("الخوف مشي من أوضته"))


class DoctrineStoryGateTests(unittest.TestCase):
    def test_the_shared_fixture_passes_every_doctrine_rule(self) -> None:
        story = handoff_fixture.build_handoff_story()
        self.assertEqual([], doctrine.doctrine_errors(story, story["pages"]))

    def test_wrong_length_is_blocking(self) -> None:
        story = handoff_fixture.build_handoff_story()
        story["pages"] = story["pages"][:-1]
        story["pageCount"] = len(story["pages"])
        codes = {
            issue["code"] for issue in doctrine.doctrine_errors(story, story["pages"])
        }
        self.assertIn("wrong-book-length", codes)

    def test_rewritten_dedication_is_blocking(self) -> None:
        story = handoff_fixture.build_handoff_story()
        handoff_fixture.page_by_id(story, "page-01")["text"] = "إهداء من عندي"
        codes = {
            issue["code"] for issue in doctrine.doctrine_errors(story, story["pages"])
        }
        self.assertIn("dedication-text-drift", codes)

    def test_rewritten_back_cover_marketing_copy_is_blocking(self) -> None:
        story = handoff_fixture.build_handoff_story()
        handoff_fixture.page_by_id(story, "back-cover")["text"] = "اشتري الكتاب"
        codes = {
            issue["code"] for issue in doctrine.doctrine_errors(story, story["pages"])
        }
        self.assertIn("back-cover-text-drift", codes)

    def test_story_type_must_be_declared_and_must_match_the_goal(self) -> None:
        story = handoff_fixture.build_handoff_story()
        del story["storyType"]
        codes = {
            issue["code"] for issue in doctrine.doctrine_errors(story, story["pages"])
        }
        self.assertIn("missing-story-type", codes)

        story = handoff_fixture.build_handoff_story(storyType="C")
        codes = {
            issue["code"] for issue in doctrine.doctrine_errors(story, story["pages"])
        }
        self.assertIn("story-type-goal-mismatch", codes)

    def test_type_b_refuses_a_magical_companion(self) -> None:
        story = handoff_fixture.build_handoff_story()
        story["guestCharacters"] = [
            {"id": "guest-01", "displayName": "رفيق سحري", "appearanceNotes": "x" * 130}
        ]
        codes = {
            issue["code"] for issue in doctrine.doctrine_errors(story, story["pages"])
        }
        self.assertIn("forbidden-magical-companion", codes)

    def test_type_a_needs_a_companion_and_a_relapse_beat(self) -> None:
        story = handoff_fixture.build_handoff_story(storyType="A")
        story["narrativeArc"] = {
            key: value
            for key, value in story["narrativeArc"].items()
            if key != "setback"
        }
        codes = {
            issue["code"] for issue in doctrine.doctrine_errors(story, story["pages"])
        }
        self.assertIn("missing-magical-companion", codes)
        self.assertIn("missing-relapse-beat", codes)

    def test_side_friends_must_share_the_hero_gender(self) -> None:
        story = handoff_fixture.build_handoff_story()
        story["personas"][0]["gender"] = "boy"
        story["personas"].append(
            {
                "id": "persona-02",
                "displayName": "سما",
                "role": "friend",
                "gender": "girl",
                "fixedOutfit": "فستان أصفر",
            }
        )
        codes = {
            issue["code"] for issue in doctrine.doctrine_errors(story, story["pages"])
        }
        self.assertIn("mixed-gender-friend-group", codes)

    def test_banned_metaphor_on_a_page_blocks_review_story(self) -> None:
        story = handoff_fixture.build_handoff_story()
        handoff_fixture.page_by_id(story, "page-05")["text"] = (
            "أحمد حس إن حد سرق مكانه في الفصل."
        )
        report = pipeline.review_story_quality(story)
        self.assertEqual("revise", report["decision"])
        self.assertIn(
            "doctrine-literal-metaphor",
            {issue["code"] for issue in report["errors"]},
        )

    def test_fixed_pages_are_exempt_from_the_age_word_budget(self) -> None:
        story = handoff_fixture.build_handoff_story()
        report = pipeline.review_story_quality(story)
        stats = {row["pageId"]: row for row in report["stats"]["pageStats"]}
        self.assertTrue(stats["page-01"]["fixedByDoctrine"])
        self.assertTrue(stats["page-22"]["fixedByDoctrine"])
        self.assertEqual("pass", report["decision"])

    def test_handoff_dialect_replacements_are_enforced(self) -> None:
        story = handoff_fixture.build_handoff_story()
        handoff_fixture.page_by_id(story, "page-05")["text"] = (
            "أحمد راح لـ أمه وقالها إنه خايف."
        )
        report = pipeline.review_story_quality(story)
        terms = {issue.get("term") for issue in report["errors"]}
        self.assertIn("أمه", terms)


class StructureExpansionTests(unittest.TestCase):
    def _legacy_story(self, story_pages: int = 18) -> dict:
        pages = [{"id": "cover", "text": "غلاف", "locationId": "home"}]
        pages.extend(
            {"id": f"page-{index:02d}", "text": f"صفحة {index}", "locationId": "home"}
            for index in range(1, story_pages + 1)
        )
        pages.append({"id": "back-cover", "text": "خلفي", "locationId": "home"})
        return {
            "pages": pages,
            "narrativeArc": {"setup": ["page-01"], "resolution": ["back-cover"]},
        }

    def test_expansion_renumbers_pages_and_the_arc_together(self) -> None:
        story, report = doctrine.expand_to_handoff_structure(
            self._legacy_story(), hero_name="سما"
        )
        ids = [page["id"] for page in story["pages"]]
        self.assertEqual(24, len(ids))
        self.assertEqual("page-01", ids[1])
        self.assertEqual("back-cover", ids[-1])
        self.assertEqual(["page-02"], story["narrativeArc"]["setup"])
        self.assertEqual(["back-cover"], story["narrativeArc"]["resolution"])

    def test_missing_story_pages_become_declared_holes_not_filler(self) -> None:
        story, report = doctrine.expand_to_handoff_structure(
            self._legacy_story(), hero_name="سما"
        )
        self.assertEqual(["page-20", "page-21"], report["gapPages"])
        self.assertTrue(report["requiresStructureExpansion"])
        for page_id in report["gapPages"]:
            page = next(p for p in story["pages"] if p["id"] == page_id)
            self.assertEqual("", page["text"])
            self.assertTrue(page[doctrine.GAP_PAGE_MARKER])
        self.assertEqual(2, len(doctrine.gap_page_errors(story["pages"])))

    def test_a_full_length_source_needs_no_holes(self) -> None:
        _story, report = doctrine.expand_to_handoff_structure(
            self._legacy_story(20), hero_name="سما"
        )
        self.assertEqual([], report["gapPages"])
        self.assertFalse(report["requiresStructureExpansion"])


class ManualDispatchTests(unittest.TestCase):
    PROMPT = {
        "assetId": "page-05",
        "narrativeBeat": "أحمد بيجرب التقنية لأول مرة",
        "primaryRequest": "أحمد واقف قدام الفصل وبيعد على صوابعه",
        "inputImages": [
            {"role": "persona-identity", "personaId": "persona-01", "path": "/abs/ahmed.png"},
            {"role": "character-sheet", "path": "/abs/sheet.png"},
        ],
        "participants": [
            {"id": "persona-01", "displayName": "أحمد", "role": "hero", "onPage": True}
        ],
        "fixedOutfits": {"persona-01": "تيشرت أخضر وبنطلون جينز"},
        "actionAndEmotion": {
            "persona-01": {"action": "واقف وبيعد على صوابعه", "emotion": "متوتر شوية"}
        },
        "scene": {
            "place": "فناء المدرسة",
            "timeOfDay": "شمس الصبح",
            "lighting": "ضوء دافي من الشمال",
            "propsInFrame": ["كورة إسفنج زرقا"],
        },
        "composition": {"shotScale": "medium", "viewpoint": "eye-level"},
        "style": {"medium": "premium storybook illustration", "finish": "soft painterly"},
        "palette": "teal, sand, warm gold",
        "avoid": ["extra people"],
    }

    def test_instruction_is_self_contained(self) -> None:
        block = manual_dispatch.render_manual_instruction(
            self.PROMPT, asset_id="page-05", page_text="أحمد عد لتلاتة."
        )
        self.assertIn(doctrine.reference_sheet_clause(), block)
        self.assertIn("landscape 16:9", block)
        self.assertIn("/abs/sheet.png", block)
        self.assertIn(doctrine.print_safe_clause("ar"), block)
        self.assertIn("ولّد **page-05** بس", block)
        self.assertIn("ممنوع توليد أكتر من صفحة في نفس الرد", block)

    def test_page_text_is_marked_as_context_not_art(self) -> None:
        block = manual_dispatch.render_manual_instruction(
            self.PROMPT, asset_id="page-05", page_text="أحمد عد لتلاتة."
        )
        self.assertIn("متكتبوش في الصورة", block)
        self.assertIn("ممنوع أي كتابة في الصورة", block)

    def test_a_batch_file_never_exceeds_two_pages(self) -> None:
        blocks = [
            {"assetId": f"page-{index:02d}", "instruction": "x"} for index in range(1, 4)
        ]
        with self.assertRaises(manual_dispatch.ManualDispatchError):
            manual_dispatch.render_batch_file(blocks)
        self.assertIn("page-01", manual_dispatch.render_batch_file(blocks[:2]))

    def test_character_sheet_instruction_lists_the_four_angles(self) -> None:
        block = manual_dispatch.render_character_sheet_instruction(self.PROMPT)
        for angle in doctrine.character_sheet_angles():
            self.assertIn(angle, block)


class DoctrineCommandTests(unittest.TestCase):
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

    def test_init_records_the_structure_and_builds_a_client_vault(self) -> None:
        book = pipeline.load_book(self.project)
        self.assertEqual("hekayati-22", book["settings"]["bookStructure"])
        self.assertEqual(24, book["settings"]["pdfPageCount"])
        self.assertTrue((self.project / ".obsidian" / "app.json").is_file())
        self.assertTrue((self.project / "Home.md").is_file())

    def test_show_doctrine_returns_the_rulebook(self) -> None:
        result = pipeline.command_show_doctrine(argparse.Namespace(section=None))
        self.assertIn("bookStructure", result["sections"])
        self.assertEqual({"A", "B", "C"}, set(result["storyTypes"]))

    def test_set_story_type_refuses_a_goal_mismatch(self) -> None:
        pipeline.command_set_story_goal(
            argparse.Namespace(
                project=self.project, mode="educational", goal="يعد لتلاتة"
            )
        )
        with self.assertRaisesRegex(pipeline.WorkflowError, "entertainment"):
            pipeline.command_set_story_type(
                argparse.Namespace(project=self.project, type="C")
            )
        result = pipeline.command_set_story_type(
            argparse.Namespace(project=self.project, type="B")
        )
        self.assertEqual("B", result["storyType"])

    def test_apply_fixed_pages_writes_the_doctrine_copy(self) -> None:
        story = handoff_fixture.build_handoff_story()
        handoff_fixture.page_by_id(story, "page-01")["text"] = "إهداء عشوائي"
        handoff_fixture.page_by_id(story, "back-cover")["text"] = "كلام تسويقي تاني"
        pipeline.atomic_json(self.project / "input" / "story.json", story)

        result = pipeline.command_apply_fixed_pages(
            argparse.Namespace(project=self.project)
        )
        self.assertEqual(["page-01", "page-22", "back-cover"], result["updatedPages"])
        fixed = pipeline.read_json(self.project / "input" / "story.json")
        self.assertEqual(
            doctrine.dedication_text("أحمد"),
            handoff_fixture.page_by_id(fixed, "page-01")["text"],
        )
        self.assertEqual([], doctrine.doctrine_errors(fixed, fixed["pages"]))

    def test_check_doctrine_reports_pass_and_revise(self) -> None:
        story = handoff_fixture.build_handoff_story()
        story_path = self.project / "input" / "story.json"
        pipeline.atomic_json(story_path, story)
        self.assertEqual(
            "pass",
            pipeline.command_check_doctrine(
                argparse.Namespace(project=self.project, story=None)
            )["decision"],
        )

        handoff_fixture.page_by_id(story, "page-05")["text"] = "قلبه بقى أكبر."
        pipeline.atomic_json(story_path, story)
        result = pipeline.command_check_doctrine(
            argparse.Namespace(project=self.project, story=None)
        )
        self.assertEqual("revise", result["decision"])
        self.assertIn("MP-heart-grew", {issue["ruleId"] for issue in result["errors"]})


if __name__ == "__main__":
    unittest.main()


class PrintSafePromptTests(unittest.TestCase):
    """handoff §9 — the colour clause is mandatory in every image prompt."""

    BASE = {
        "assetId": "page-05",
        "useCase": "illustration-story",
        "narrativeBeat": "أحمد بيجرب التقنية",
        "primaryRequest": "أحمد واقف قدام الفصل",
        "participants": [
            {"id": "persona-01", "displayName": "أحمد", "role": "hero", "onPage": True}
        ],
        "scene": {"place": "فناء المدرسة", "timeOfDay": "الصبح"},
        "style": {"medium": "premium storybook illustration", "finish": "soft painterly"},
        "composition": {"orientation": "landscape"},
        "palette": "teal, sand, warm gold",
    }

    def test_clause_is_compiled_into_the_prompt(self) -> None:
        compiled = pipeline.build_compiled_prompt(
            dict(self.BASE), orientation="landscape"
        )
        self.assertIn("Print-safe palette", compiled)
        self.assertIn("#2C3E50", compiled)
        self.assertIn("#000000", compiled)

    def test_clause_survives_the_length_shedding_pass(self) -> None:
        payload = dict(self.BASE)
        payload["avoid"] = ["حاجة " * 200]
        payload["scene"] = dict(payload["scene"], backdropDetails="تفاصيل " * 400)
        compiled = pipeline.build_compiled_prompt(payload, orientation="landscape")
        self.assertIn("Print-safe palette", compiled)
