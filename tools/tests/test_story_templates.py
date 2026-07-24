from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIPELINE_PATH = ROOT / "tools" / "scripts" / "story_pipeline.py"
SPEC = importlib.util.spec_from_file_location("story_pipeline", PIPELINE_PATH)
assert SPEC and SPEC.loader
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


class StoryTemplateCatalogTests(unittest.TestCase):
    def test_catalog_contains_15_complete_safe_templates(self) -> None:
        catalog = pipeline.load_story_templates_catalog()
        templates = catalog["templates"]
        self.assertEqual(15, len(templates))
        self.assertIn(catalog.get("defaultTemplateId"), templates)

        for template_id, template in templates.items():
            self.assertEqual(20, template["pageCount"], template_id)
            self.assertEqual(
                pipeline.build_pdf_asset_ids(20),
                [page["id"] for page in template["pages"]],
            )
            image_prompt_source = json.dumps(
                {
                    "guests": template.get("guestCharacters"),
                    "pages": template.get("pages"),
                },
                ensure_ascii=False,
            )
            self.assertEqual(
                [],
                pipeline.find_franchise_name_hits(image_prompt_source),
                template_id,
            )

    def test_list_and_show_commands(self) -> None:
        listed = pipeline.command_list_templates(argparse.Namespace(category=None))
        self.assertEqual(15, listed["count"])
        template_id = listed["templates"][0]["templateId"]
        shown = pipeline.command_show_template(
            argparse.Namespace(template=template_id)
        )
        self.assertEqual(template_id, shown["template"]["templateId"])
        self.assertEqual(20, len(shown["template"]["pages"]))
        category = listed["templates"][0]["category"]
        filtered = pipeline.command_list_templates(
            argparse.Namespace(category=category.upper())
        )
        self.assertGreaterEqual(filtered["count"], 1)
        self.assertTrue(
            all(item["category"] == category for item in filtered["templates"])
        )
        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_list_templates(
                argparse.Namespace(category="not-a-real-category")
            )

    def test_list_themes_command(self) -> None:
        listed = pipeline.command_list_themes(argparse.Namespace())
        self.assertGreaterEqual(listed["count"], 1)
        self.assertIn(
            listed.get("defaultThemeId"),
            {t["themeId"] for t in listed["themes"]},
        )
        theme_ids = {t["themeId"] for t in listed["themes"]}
        self.assertIn("storybook", theme_ids)
        self.assertIn("wonder-trail", theme_ids)

    def test_every_template_passes_its_source_language_profile(self) -> None:
        catalog = pipeline.load_story_templates_catalog()
        theme = pipeline.get_theme("storybook")
        brief = {
            "targetAge": 5,
            "languageProfileId": "age-3-5",
            "language": "natural Egyptian Arabic",
            "themeId": "storybook",
            "visualStyle": theme["visualStyle"],
            "personas": [
                {
                    "id": "persona-01",
                    "displayName": "أحمد",
                    "role": "hero",
                    "fixedOutfit": "جاكيت أخضر، تيشرت أبيض، وبنطلون كحلي",
                }
            ],
            "avoid": [],
            "personalization": {},
        }
        for template_id, template in catalog["templates"].items():
            with self.subTest(template=template_id):
                story, _selection, missing_outfits = pipeline.build_story_from_template(
                    template=template,
                    catalog=catalog,
                    brief=brief,
                    book={},
                    note=None,
                )
                report = pipeline.review_story_quality(story)
                self.assertEqual([], missing_outfits)
                self.assertEqual([], report["errors"], report)
                self.assertEqual([], report["warnings"], report)


class StoryTemplateWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name).resolve()
        personas = self.project / "personas"
        personas.mkdir()
        # init only discovers paths/extensions; image validation happens before generation.
        (personas / "ahmed.png").write_bytes(b"test fixture")
        pipeline.command_init(argparse.Namespace(project=self.project, pages=12))
        brief_path = self.project / "input" / "brief.json"
        brief = pipeline.read_json(brief_path)
        brief["personas"][0]["displayName"] = "أحمد"
        brief["personas"][0]["fixedOutfit"] = (
            "جاكيت أخضر، تيشرت أبيض، بنطلون كحلي، حذاء رياضي"
        )
        pipeline.atomic_json(brief_path, brief)
        catalog = pipeline.load_story_templates_catalog()
        self.template_id = catalog["defaultTemplateId"]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_apply_template_writes_personalized_ready_story_and_note(self) -> None:
        note = "خلي البوصلة هدية من جدته."
        result = pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.template_id,
                note=note,
                force=False,
            )
        )
        self.assertTrue(result["pageCountChanged"])
        self.assertEqual(20, result["pageCount"])
        self.assertFalse(result["readyToLock"])

        story = pipeline.read_json(self.project / "input" / "story.json")
        book = pipeline.load_book(self.project)
        self.assertIn("أحمد", story["title"])
        self.assertNotIn("{{hero}}", json.dumps(story, ensure_ascii=False))
        self.assertEqual(note, story["customizationNote"])
        self.assertEqual(20, len(story["pages"]))
        self.assertEqual("story_template_selected", book["status"])
        self.assertIsNone(book["storyPath"])
        self.assertEqual(20, book["settings"]["pdfPageCount"])
        self.assertEqual(21, len(book["assets"]))  # character sheet + 20 PDF pages
        status = pipeline.command_status(argparse.Namespace(project=self.project))
        self.assertEqual(
            self.template_id, status["templateSelection"]["templateId"]
        )

        persona_ids = {persona["id"] for persona in story["personas"]}
        guest_ids = {guest["id"] for guest in story["guestCharacters"]}
        for page in story["pages"]:
            self.assertTrue(set(page["participants"]) <= persona_ids)
            self.assertTrue(set(page["guests"]) <= guest_ids)

        requirements = (self.project / "input" / "requirements.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"- id: `{self.template_id}`", requirements)
        self.assertIn(note, requirements)
        self.assertIn("- pageCount: 20", requirements)

    def test_note_can_change_before_lock_but_not_after(self) -> None:
        pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.template_id,
                note=None,
                force=False,
            )
        )
        changed = pipeline.command_set_template_note(
            argparse.Namespace(project=self.project, note="ضيف قطة برتقالية في النهاية.")
        )
        self.assertIn("قطة برتقالية", changed["customizationNote"])

        consent = pipeline.command_confirm_consent(
            argparse.Namespace(
                project=self.project,
                statement="I own the persona image and consent to its use.",
            )
        )
        self.assertIn("complete-template-customization", consent["nextAction"])
        themed = pipeline.command_apply_theme(
            argparse.Namespace(project=self.project, theme="storybook")
        )
        self.assertIn("complete-template-customization", themed["nextAction"])

        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_lock_story(
                argparse.Namespace(project=self.project, story=None)
            )
        completed = pipeline.command_complete_template_customization(
            argparse.Namespace(project=self.project)
        )
        self.assertIn("قطة برتقالية", completed["customizationNote"])
        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_complete_template_customization(
                argparse.Namespace(project=self.project)
            )

        pipeline.command_lock_story(
            argparse.Namespace(project=self.project, story=None)
        )
        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_set_template_note(
                argparse.Namespace(project=self.project, note="ملاحظة متأخرة")
            )

    def test_template_page_count_is_fixed_and_completion_needs_note(self) -> None:
        pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.template_id,
                note=None,
                force=False,
            )
        )
        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_set_pages(
                argparse.Namespace(project=self.project, pages=12)
            )
        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_complete_template_customization(
                argparse.Namespace(project=self.project)
            )

    def test_template_lock_requires_fixed_outfit(self) -> None:
        brief_path = self.project / "input" / "brief.json"
        brief = pipeline.read_json(brief_path)
        brief["personas"][0]["fixedOutfit"] = None
        pipeline.atomic_json(brief_path, brief)
        pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.template_id,
                note=None,
                force=False,
            )
        )
        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_lock_story(
                argparse.Namespace(project=self.project, story=None)
            )

    def test_existing_story_requires_force_and_prompts_block_replacement(self) -> None:
        catalog = pipeline.load_story_templates_catalog()
        template_ids = list(catalog["templates"])
        second_template_id = next(
            template_id
            for template_id in template_ids
            if template_id != self.template_id
        )
        pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.template_id,
                note=None,
                force=False,
            )
        )
        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_apply_template(
                argparse.Namespace(
                    project=self.project,
                    template=self.template_id,
                    note=None,
                    force=False,
                )
            )

        brief_path = self.project / "input" / "brief.json"
        brief = pipeline.read_json(brief_path)
        brief["mustShow"].append("طلب مستخدم لازم يفضل")
        brief["avoid"].append("منع مستخدم لازم يفضل")
        pipeline.atomic_json(brief_path, brief)
        pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=second_template_id,
                note="تخصيص آمن قبل البرومبتات",
                force=True,
            )
        )
        brief = pipeline.read_json(brief_path)
        first = catalog["templates"][self.template_id]
        second = catalog["templates"][second_template_id]
        self.assertIn("طلب مستخدم لازم يفضل", brief["mustShow"])
        self.assertIn("منع مستخدم لازم يفضل", brief["avoid"])
        self.assertTrue(set(second["mustShow"]) <= set(brief["mustShow"]))
        self.assertTrue(set(second["avoid"]) <= set(brief["avoid"]))
        self.assertFalse(
            (set(first["mustShow"]) - set(second["mustShow"]))
            & set(brief["mustShow"])
        )
        self.assertFalse(
            (set(first["avoid"]) - set(second["avoid"])) & set(brief["avoid"])
        )
        requirements = (self.project / "input" / "requirements.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(1, requirements.count("<!-- hekayati-story-template:start -->"))
        prompt = self.project / "input" / "prompts" / "cover.v01.json"
        prompt.write_text("{}\n", encoding="utf-8")
        story_path = self.project / "input" / "story.json"
        before = story_path.read_bytes()
        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_apply_template(
                argparse.Namespace(
                    project=self.project,
                    template=self.template_id,
                    note=None,
                    force=True,
                )
            )
        self.assertEqual(before, story_path.read_bytes())

    def test_template_note_length_is_bounded(self) -> None:
        pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.template_id,
                note=None,
                force=False,
            )
        )
        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_set_template_note(
                argparse.Namespace(project=self.project, note="ا" * 4001)
            )

    def test_template_gate_cannot_be_removed_from_story_or_external_copy(self) -> None:
        pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.template_id,
                note="غيّر تفصيلة في الحل.",
                force=False,
            )
        )
        story_path = self.project / "input" / "story.json"
        story = pipeline.read_json(story_path)
        story["templateSelection"]["requiresRevision"] = False
        pipeline.atomic_json(story_path, story)
        with self.assertRaisesRegex(pipeline.WorkflowError, "state drift"):
            pipeline.command_lock_story(
                argparse.Namespace(project=self.project, story=None)
            )

        canonical = copy.deepcopy(story)
        canonical.pop("templateSelection")
        external = self.project / "external-story.json"
        pipeline.atomic_json(external, canonical)
        with self.assertRaisesRegex(pipeline.WorkflowError, "state drift"):
            pipeline.command_lock_story(
                argparse.Namespace(project=self.project, story=external)
            )

    def test_prelock_mutators_refuse_to_canonize_drifted_template_state(self) -> None:
        pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.template_id,
                note=None,
                force=False,
            )
        )
        story_path = self.project / "input" / "story.json"
        brief_path = self.project / "input" / "brief.json"
        book_path = self.project / "output" / "book.json"
        story = pipeline.read_json(story_path)
        story["templateSelection"]["requiresRevision"] = True
        pipeline.atomic_json(story_path, story)
        before = {
            path: path.read_bytes() for path in (story_path, brief_path, book_path)
        }

        calls = [
            lambda: pipeline.command_apply_theme(
                argparse.Namespace(project=self.project, theme="wonder-trail")
            ),
            lambda: pipeline.command_confirm_consent(
                argparse.Namespace(
                    project=self.project,
                    statement="I own the persona image and consent to its use.",
                )
            ),
            lambda: pipeline.command_set_personalization(
                argparse.Namespace(
                    project=self.project,
                    json=json.dumps(
                        {
                            "traits": [
                                {"personaId": "persona-01", "textAr": "بيحب الرسم"}
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    file=None,
                    replace=False,
                )
            ),
        ]
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaisesRegex(pipeline.WorkflowError, "state drift"):
                    call()
                for path, payload in before.items():
                    self.assertEqual(payload, path.read_bytes())

    def test_template_state_cannot_drop_the_same_gate_field_everywhere(self) -> None:
        pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.template_id,
                note=None,
                force=False,
            )
        )
        paths = (
            self.project / "input" / "story.json",
            self.project / "input" / "brief.json",
            self.project / "output" / "book.json",
        )
        for path in paths:
            payload = pipeline.read_json(path)
            payload["templateSelection"].pop("customizedAt")
            pipeline.atomic_json(path, payload)
        with self.assertRaisesRegex(pipeline.WorkflowError, "missing customizedAt"):
            pipeline.command_apply_theme(
                argparse.Namespace(project=self.project, theme="storybook")
            )

    def test_story_persona_needs_a_client_image_source(self) -> None:
        pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.template_id,
                note=None,
                force=False,
            )
        )
        story_path = self.project / "input" / "story.json"
        story = pipeline.read_json(story_path)
        story["personas"].append(
            {
                "id": "persona-99",
                "displayName": "شخصية مزيفة",
                "role": "companion",
                "fixedOutfit": "تيشرت أحمر وبنطلون أسود",
            }
        )
        story["pages"][1]["participants"].append("persona-99")
        pipeline.atomic_json(story_path, story)
        with self.assertRaisesRegex(pipeline.WorkflowError, "without client image"):
            pipeline.command_lock_story(
                argparse.Namespace(project=self.project, story=None)
            )

    def test_age_six_adaptation_is_exact_durable_and_synced(self) -> None:
        brief_path = self.project / "input" / "brief.json"
        brief = pipeline.read_json(brief_path)
        brief["targetAge"] = 6
        brief["languageProfileId"] = "age-6-8"
        pipeline.atomic_json(brief_path, brief)
        applied = pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.template_id,
                note=None,
                force=False,
            )
        )
        self.assertTrue(applied["requiresAgeAdaptation"])
        book = pipeline.load_book(self.project)
        self.assertEqual("age-6-8", book["settings"]["languageProfileId"])
        with self.assertRaisesRegex(pipeline.WorkflowError, "not complete"):
            pipeline.command_complete_template_customization(
                argparse.Namespace(project=self.project)
            )

        story_path = self.project / "input" / "story.json"
        story = pipeline.read_json(story_path)
        original_text = {
            page["id"]: page["text"]
            for page in story["pages"]
            if page["id"].startswith("page-")
        }
        age_six_clause = (
            "وده خلّى الفريق يفهم الخطوة الجاية ويكمل خطته بهدوء سوا."
        )
        for page in story["pages"]:
            if (
                page["id"].startswith("page-")
                and pipeline._arabic_word_count(page["text"]) < 14
            ):
                page["text"] = page["text"].rstrip(". ") + ". " + age_six_clause
        pipeline.atomic_json(story_path, story)
        completed = pipeline.command_complete_template_customization(
            argparse.Namespace(project=self.project)
        )
        self.assertIsNotNone(completed["ageAdaptedAt"])

        pipeline.command_set_template_note(
            argparse.Namespace(project=self.project, note="راجع نهاية الرحلة.")
        )
        story = pipeline.read_json(story_path)
        for page in story["pages"]:
            if page["id"] in original_text:
                page["text"] = original_text[page["id"]]
        pipeline.atomic_json(story_path, story)
        with self.assertRaisesRegex(pipeline.WorkflowError, "not complete"):
            pipeline.command_complete_template_customization(
                argparse.Namespace(project=self.project)
            )

        story = pipeline.read_json(story_path)
        for page in story["pages"]:
            if (
                page["id"].startswith("page-")
                and pipeline._arabic_word_count(page["text"]) < 14
            ):
                page["text"] = page["text"].rstrip(". ") + ". " + age_six_clause
        pipeline.atomic_json(story_path, story)
        pipeline.command_complete_template_customization(
            argparse.Namespace(project=self.project)
        )
        locked = pipeline.command_lock_story(
            argparse.Namespace(project=self.project, story=None)
        )
        self.assertEqual("age-6-8", locked["storyQuality"]["languageProfileId"])

    def test_age_target_drift_blocks_completion(self) -> None:
        brief_path = self.project / "input" / "brief.json"
        brief = pipeline.read_json(brief_path)
        brief["targetAge"] = 6
        brief["languageProfileId"] = "age-6-8"
        pipeline.atomic_json(brief_path, brief)
        pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.template_id,
                note=None,
                force=False,
            )
        )
        story_path = self.project / "input" / "story.json"
        story = pipeline.read_json(story_path)
        story["targetAge"] = 5
        story["languageProfileId"] = "age-3-5"
        pipeline.atomic_json(story_path, story)
        with self.assertRaisesRegex(pipeline.WorkflowError, "target drift"):
            pipeline.command_complete_template_customization(
                argparse.Namespace(project=self.project)
            )


if __name__ == "__main__":
    unittest.main()
