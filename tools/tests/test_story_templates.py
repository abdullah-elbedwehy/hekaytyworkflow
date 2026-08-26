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
    def test_catalog_contains_15_original_entertainment_templates(self) -> None:
        catalog = pipeline.load_story_templates_catalog()
        templates = catalog["templates"]
        self.assertEqual(15, len(templates))
        self.assertEqual(
            "thread-guardian-lantern-city", catalog.get("defaultTemplateId")
        )
        self.assertEqual(
            {"entertainment": "thread-guardian-lantern-city"},
            catalog.get("defaultTemplateByIntent"),
        )
        self.assertEqual(
            {"entertainment"},
            {template["storyIntent"] for template in templates.values()},
        )

        for template_id, template in templates.items():
            provenance = (template.get("moral") or {}).get("provenance") or {}
            self.assertNotIn("sourceStoryId", provenance, template_id)
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
        listed = pipeline.command_list_templates(
            argparse.Namespace(
                category=None, intent=None, include_drafts=False
            )
        )
        self.assertEqual(15, listed["count"])
        template_id = listed["templates"][0]["templateId"]
        shown = pipeline.command_show_template(
            argparse.Namespace(template=template_id)
        )
        self.assertEqual(template_id, shown["template"]["templateId"])
        self.assertEqual(20, len(shown["template"]["pages"]))
        category = listed["templates"][0]["category"]
        filtered = pipeline.command_list_templates(
            argparse.Namespace(
                category=category.upper(), intent=None, include_drafts=False
            )
        )
        self.assertGreaterEqual(filtered["count"], 1)
        self.assertTrue(
            all(item["category"] == category for item in filtered["templates"])
        )
        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_list_templates(
                argparse.Namespace(
                    category="not-a-real-category",
                    intent=None,
                    include_drafts=False,
                )
            )

    def test_list_filters_goal_and_leaves_education_to_custom_stories(self) -> None:
        educational = pipeline.command_list_templates(
            argparse.Namespace(
                category=None,
                intent="educational",
                include_drafts=False,
            )
        )
        entertainment = pipeline.command_list_templates(
            argparse.Namespace(
                category=None,
                intent="entertainment",
                include_drafts=False,
            )
        )
        self.assertEqual(0, educational["count"])
        self.assertEqual(15, entertainment["count"])
        self.assertEqual([], educational["templates"])
        self.assertTrue(
            all(
                item["storyIntent"] == "entertainment"
                for item in entertainment["templates"]
            )
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
                # Each template is authored against its own age profile — grade it there,
                # not against a single hardcoded profile.
                brief["targetAge"] = template["ageRange"]["min"]
                brief["languageProfileId"] = template["languageProfileId"]
                story, _selection, missing_outfits = pipeline.build_story_from_template(
                    template=template,
                    catalog=catalog,
                    brief=brief,
                    book={},
                    note=None,
                )
                report = pipeline.review_story_quality(story)
                self.assertEqual([], missing_outfits)
                # Catalog templates were authored before handoff §7 fixed the
                # book at 20 story pages, so applying one opens the shortfall as
                # declared holes. Those are the only errors allowed here; a
                # template must be otherwise clean on its own age profile.
                gaps = [
                    issue
                    for issue in report["errors"]
                    if issue["code"] == "unwritten-story-page"
                ]
                self.assertEqual(
                    gaps, report["errors"], report
                )
                self.assertEqual(
                    sorted(issue["pageId"] for issue in gaps),
                    sorted(story["structureReport"]["gapPages"]),
                )
                self.assertEqual([], report["warnings"], report)


class StoryTemplateWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name).resolve()
        personas = self.project / "personas"
        personas.mkdir()
        # init only discovers paths/extensions; image validation happens before generation.
        (personas / "ahmed.png").write_bytes(b"test fixture")
        pipeline.command_init(
            argparse.Namespace(project=self.project, pages=12)
        )
        brief_path = self.project / "input" / "brief.json"
        brief = pipeline.read_json(brief_path)
        brief["personas"][0]["displayName"] = "أحمد"
        brief["personas"][0]["fixedOutfit"] = (
            "جاكيت أخضر، تيشرت أبيض، بنطلون كحلي، حذاء رياضي"
        )
        pipeline.atomic_json(brief_path, brief)
        pipeline.command_set_story_goal(
            argparse.Namespace(
                project=self.project,
                mode="entertainment",
                goal="يعيش مغامرة سحرية ويحل اللغز بنفسه",
            )
        )
        catalog = pipeline.load_story_templates_catalog()
        self.template_id = catalog["defaultTemplateId"]
        # All originals are authored against age-3-5 copy and allow age 6, so
        # the default safely exercises the mandatory cross-profile adaptation.
        self.template_id_age_6_8 = self.template_id

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def approve_story_review(self) -> None:
        pipeline.command_prepare_story_review(
            argparse.Namespace(project=self.project, force=False)
        )
        pipeline.command_approve_story_review(
            argparse.Namespace(
                project=self.project,
                statement="راجعت النص ووصف كل مشهد ووافقت عليهم.",
            )
        )

    def fill_structure_gaps(self) -> dict:
        """Author the story pages the handoff structure opened after apply.

        A catalog template is two story pages short of handoff §7, and the
        pipeline deliberately refuses to invent them. Every workflow test that
        walks past `apply-template` has to write them, exactly like the agent.
        """
        story_path = self.project / "input" / "story.json"
        story = pipeline.read_json(story_path)
        arc = story["narrativeArc"]
        owner_of = {
            page_id: stage
            for stage, page_ids in arc.items()
            if isinstance(page_ids, list)
            for page_id in page_ids
        }
        # Short single sentences so the same filler fits every age profile's
        # sentence cap, including age-1-2.
        wording = [
            "بعد كده وقفوا يراجعوا الخطوة اللي فاتت.",
            "وبعدين كملوا الجزء الأخير من الخطة سوا.",
            "وبكده رتبوا كل حاجة قبل ما يكملوا.",
        ]
        filled: list[str] = []
        for index, page in enumerate(story["pages"]):
            if not page.get(pipeline.doctrine.GAP_PAGE_MARKER):
                continue
            page_id = page["id"]
            previous = story["pages"][index - 1]
            stage = owner_of.get(previous["id"]) or "attempts"
            page.pop(pipeline.doctrine.GAP_PAGE_MARKER)
            page.update(
                {
                    "text": wording[len(filled) % len(wording)],
                    "beat": f"خطوة مكمّلة رقم {len(filled) + 1} بعد {stage}",
                    "participants": list(previous["participants"]),
                    "guests": list(previous.get("guests") or []),
                    "locationId": previous["locationId"],
                    "setting": previous["setting"],
                    "action": "الأبطال بيراجعوا خطتهم وبيكملوا الحركة",
                }
            )
            # Join the stage that already owns the page before it, so the arc
            # stays in canonical order instead of jumping backwards.
            arc.setdefault(stage, []).append(page_id)
            owner_of[page_id] = stage
            filled.append(page_id)
        pipeline.atomic_json(story_path, story)
        return {"filled": filled, "story": story}
    def lock_story(self) -> dict:
        self.approve_story_review()
        return pipeline.command_lock_story(
            argparse.Namespace(project=self.project, story=None)
        )

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
        self.assertEqual(pipeline.DEFAULT_PDF_PAGES, result["pageCount"])
        self.assertFalse(result["readyToLock"])

        story = pipeline.read_json(self.project / "input" / "story.json")
        book = pipeline.load_book(self.project)
        self.assertIn("أحمد", story["title"])
        self.assertNotIn("{{hero}}", json.dumps(story, ensure_ascii=False))
        self.assertEqual(note, story["customizationNote"])
        self.assertEqual(pipeline.DEFAULT_PDF_PAGES, len(story["pages"]))
        self.assertEqual("story_template_selected", book["status"])
        self.assertIsNone(book["storyPath"])
        self.assertEqual(
            pipeline.DEFAULT_PDF_PAGES, book["settings"]["pdfPageCount"]
        )
        self.assertEqual(
            pipeline.DEFAULT_PDF_PAGES + 1, len(book["assets"])
        )  # character sheet + every PDF page
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
        self.assertIn(f"- pageCount: {pipeline.DEFAULT_PDF_PAGES}", requirements)

    def test_apply_requires_goal_and_preserves_the_family_goal(self) -> None:
        brief_path = self.project / "input" / "brief.json"
        book_path = self.project / "output" / "book.json"
        brief = pipeline.read_json(brief_path)
        book = pipeline.read_json(book_path)
        brief["storyGoal"] = None
        book["storyGoal"] = None
        pipeline.atomic_json(brief_path, brief)
        pipeline.atomic_json(book_path, book)
        with self.assertRaisesRegex(pipeline.WorkflowError, "set-story-goal"):
            pipeline.command_apply_template(
                argparse.Namespace(
                    project=self.project,
                    template=self.template_id,
                    note=None,
                    force=False,
                )
            )

        family_goal = "يلاقي خيط النور وينقذ المدينة قبل ما الفوانيس تطفي"
        pipeline.command_set_story_goal(
            argparse.Namespace(
                project=self.project,
                mode="entertainment",
                goal=family_goal,
            )
        )
        pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.template_id,
                note=None,
                force=False,
            )
        )
        story = pipeline.read_json(self.project / "input" / "story.json")
        self.assertEqual(family_goal, story["storyGoal"]["goalAr"])

    def test_apply_rejects_wrong_intent_and_unknown_template(self) -> None:
        pipeline.command_set_story_goal(
            argparse.Namespace(
                project=self.project,
                mode="educational",
                goal="يتعلم يتعاون مع أصحابه في حل مشكلة",
            )
        )
        with self.assertRaisesRegex(pipeline.WorkflowError, "Book goal"):
            pipeline.command_apply_template(
                argparse.Namespace(
                    project=self.project,
                    template=self.template_id,
                    note=None,
                    force=False,
                )
            )

        pipeline.command_set_story_goal(
            argparse.Namespace(
                project=self.project,
                mode="entertainment",
                goal="يساعد بطل أصلي في مغامرة جوه مدينة سحرية",
            )
        )
        with self.assertRaisesRegex(pipeline.WorkflowError, "Unknown story template"):
            pipeline.command_apply_template(
                argparse.Namespace(
                    project=self.project,
                    template="not-in-catalog",
                    note=None,
                    force=False,
                )
            )

    def test_educational_goal_remains_available_for_custom_story_authoring(self) -> None:
        result = pipeline.command_set_story_goal(
            argparse.Namespace(
                project=self.project,
                mode="educational",
                goal="يتعلم يطلب المساعدة بهدوء لما المشكلة تكبر",
            )
        )
        self.assertEqual("educational", result["storyGoal"]["mode"])
        self.assertIsNone(pipeline.load_book(self.project)["templateSelection"])
        listed = pipeline.command_list_templates(
            argparse.Namespace(
                category=None,
                intent="educational",
                include_drafts=False,
            )
        )
        self.assertEqual(0, listed["count"])
        self.assertEqual([], listed["templates"])

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
        # The structure gate blocks completion until the opened slots are real
        # pages, then clears itself.
        with self.assertRaisesRegex(pipeline.WorkflowError, "لسه فاضية"):
            pipeline.command_complete_template_customization(
                argparse.Namespace(project=self.project)
            )
        self.fill_structure_gaps()
        completed = pipeline.command_complete_template_customization(
            argparse.Namespace(project=self.project)
        )
        self.assertIn("قطة برتقالية", completed["customizationNote"])
        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_complete_template_customization(
                argparse.Namespace(project=self.project)
            )

        self.lock_story()
        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_set_template_note(
                argparse.Namespace(project=self.project, note="ملاحظة متأخرة")
            )

    def test_switching_theme_replaces_only_managed_style_refs(self) -> None:
        style_dir = self.project / "input" / "style"
        style_dir.mkdir(parents=True, exist_ok=True)
        user_ref = style_dir / "my-family-style.png"
        user_ref.write_bytes(b"private user reference")

        first = pipeline.command_apply_theme(
            argparse.Namespace(project=self.project, theme="cartoony")
        )
        first_refs = {Path(path) for path in first["styleRefsCopied"]}
        self.assertEqual(2, len(first_refs))
        self.assertTrue(all(path.is_file() for path in first_refs))

        second = pipeline.command_apply_theme(
            argparse.Namespace(project=self.project, theme="feature-cgi")
        )
        second_refs = {Path(path) for path in second["styleRefsCopied"]}
        self.assertEqual(1, len(second_refs))
        self.assertTrue(all(path.is_file() for path in second_refs))
        self.assertTrue(all(not path.exists() for path in first_refs))
        self.assertEqual(b"private user reference", user_ref.read_bytes())
        manifest = pipeline.read_json(style_dir / pipeline.THEME_REFS_MANIFEST)
        self.assertEqual("feature-cgi", manifest["themeId"])

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
        with self.assertRaisesRegex(pipeline.WorkflowError, "fixed outfits"):
            pipeline.command_prepare_story_review(
                argparse.Namespace(project=self.project, force=False)
            )

    def test_existing_story_requires_force_and_prompts_block_replacement(self) -> None:
        catalog = pipeline.load_story_templates_catalog()
        template_ids = [
            template_id
            for template_id, template in catalog["templates"].items()
            if template.get("qualityStatus") == "ready"
            and template.get("storyIntent") == "entertainment"
        ]
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
            pipeline.command_prepare_story_review(
                argparse.Namespace(project=self.project, force=False)
            )

        canonical = copy.deepcopy(story)
        canonical.pop("templateSelection")
        external = self.project / "external-story.json"
        pipeline.atomic_json(external, canonical)
        with self.assertRaises(pipeline.WorkflowError):
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
        # Applying a template already leaves requiresRevision on (the structure
        # gate), so drift one of the other workflow-owned fields instead.
        story["templateSelection"]["requiresStructureExpansion"] = False
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
        self.fill_structure_gaps()
        pipeline.command_complete_template_customization(
            argparse.Namespace(project=self.project)
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
        # page-01 is the fixed dedication; put the fake persona on a story page.
        story["pages"][2]["participants"].append("persona-99")
        pipeline.atomic_json(story_path, story)
        with self.assertRaisesRegex(pipeline.WorkflowError, "without client image"):
            pipeline.command_prepare_story_review(
                argparse.Namespace(project=self.project, force=False)
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
                template=self.template_id_age_6_8,
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
        self.fill_structure_gaps()

        story_path = self.project / "input" / "story.json"
        story = pipeline.read_json(story_path)
        original_text = {
            page["id"]: page["text"]
            for page in story["pages"]
            if page["id"].startswith("page-")
        }
        age_six_clause = (
            "وده خلّى الفريق يفهم الخطوة الجاية ويكمل خطته سوا."
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
        locked = self.lock_story()
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
                template=self.template_id_age_6_8,
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
