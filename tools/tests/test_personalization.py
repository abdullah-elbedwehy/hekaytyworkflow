from __future__ import annotations

import argparse
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


HABIT_PAYLOAD = {
    "habitFocus": {
        "personaId": "persona-01",
        "habitAr": "بيقضم ضوافره لما يتوتر",
        "type": "reduce",
        "targetBehaviorAr": "يمسك كورة الإسفنج ويعد لتلاتة",
        "triggerAr": "قبل ما يقف قدام الفصل",
    },
    "traits": [{"personaId": "persona-01", "textAr": "بيحب الديناصورات"}],
    "requests": [
        {"kind": "place", "textAr": "بيت جدته في إسكندرية"},
        {"kind": "thing", "textAr": "دبدوبه البني"},
        {"kind": "moment", "textAr": "لقطة قبل النوم", "required": False},
    ],
}


def build_story(project: Path, page_ids: list[str]) -> dict:
    """Minimal but lock-valid custom story for the given asset ids."""
    beats = {
        "cover": "عنوان يوعد برحلة هادية",
        "page-01": "أحمد يستعد قبل الفصل",
        "page-02": "التوتر يبدأ قبل دوره",
        "page-03": "زيارة جدته تكشف فكرة مفيدة",
        "page-04": "أحمد يرجع ويجرب الفكرة",
        "page-05": "أحمد يختار التصرف الهادي",
        "page-06": "اختيار أحمد ينجح قدام الفصل",
        "back-cover": "أحمد يثبت عادته الجديدة",
    }
    texts = {
        "cover": "أحمد وخطوته الهادية",
        "page-01": "قبل الفصل، أحمد مسك كورة الإسفنج.",
        "page-02": "قلبه دق بسرعة لما سمع اسمه.",
        "page-03": "بعد المدرسة، أحمد راح بيت جدته في إسكندرية.",
        "page-04": "بعد الزيارة، أحمد رجع المدرسة عشان يجرب الفكرة.",
        "page-05": "اختار يعد لتلاتة قبل ما يبدأ كلامه.",
        "page-06": "قال فكرته بهدوء، فصحابه سمعوه للآخر.",
        "back-cover": "أحمد حط الكورة في شنطته للمرة الجاية.",
    }
    story_pages = []
    for page_id in page_ids:
        page = {
                "id": page_id,
                "text": texts[page_id],
                "beat": beats[page_id],
                "participants": ["persona-01"],
                "guests": [],
                "locationId": "grandma-house" if page_id == "page-03" else "school-yard",
                "setting": "مكان",
                "action": beats[page_id],
            }
        if page_id == "page-03":
            page["transitionFromPrevious"] = (
                "بعد المدرسة، أحمد راح بيت جدته في إسكندرية."
            )
        elif page_id == "page-04":
            page["transitionFromPrevious"] = texts[page_id]
        if page_id == "page-05":
            page["combinedArcStages"] = ["choice", "decisiveAction"]
        story_pages.append(page)
    return {
        "title": "قصة أحمد",
        "targetAge": 5,
        "languageProfileId": "age-3-5",
        "language": "natural Egyptian Arabic",
        "themeId": "storybook",
        "visualStyle": "premium whimsical children's storybook digital illustration",
        "purpose": "habit",
        "pageCount": len(page_ids),
        "outline": "أحمد بيتعلم يهدّي نفسه",
        "personas": [
            {
                "id": "persona-01",
                "displayName": "أحمد",
                "role": "hero",
                "fixedOutfit": "تيشرت أخضر وبنطلون جينز",
            }
        ],
        "guestCharacters": [],
        "locations": [
            {
                "id": "school-yard",
                "nameAr": "فناء المدرسة",
                "visualDefinition": (
                    "A wide school yard with cream plaster walls, a green painted "
                    "iron gate, four tall ficus trees along the east wall, grey "
                    "concrete tiles, a red-and-white four-square court, and a low "
                    "blue bench under the arcade."
                ),
                "pageCue": "the cream yard with the green gate and the blue bench",
            },
            {
                "id": "grandma-house",
                "nameAr": "بيت جدته في إسكندرية",
                "visualDefinition": (
                    "A first-floor Alexandria flat with a wooden balcony over a "
                    "sea-facing street, teal shutters, a round brass tea tray on a "
                    "carved side table, faded rose wallpaper, and a tall bookcase "
                    "with glass doors beside the balcony arch."
                ),
                "pageCue": "the teal-shuttered balcony over the sea street",
            },
        ],
        "continuity": {
            "recurringProps": ["دبدوبه البني", "كورة إسفنج زرقاء"],
            "palette": "teal, sand, warm gold",
            "avoid": [],
        },
        "narrativeArc": {
            "setup": [page_ids[1]],
            "disruption": [page_ids[2]],
            "goal": [page_ids[3]],
            "attempts": [page_ids[4]],
            "choice": [page_ids[-3]],
            "decisiveAction": [page_ids[-3]],
            "payoff": [page_ids[-2]],
            "resolution": [page_ids[-1]],
        },
        "pages": story_pages,
    }


class PersonalizationCase(unittest.TestCase):
    """Initialized single-persona client project. Holds no tests of its own."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()
        personas = self.project / "personas"
        personas.mkdir()
        (personas / "ahmed.png").write_bytes(b"test fixture")
        pipeline.command_init(argparse.Namespace(project=self.project, pages=8))
        self.brief_path = self.project / "input" / "brief.json"
        brief = pipeline.read_json(self.brief_path)
        brief["personas"][0]["displayName"] = "أحمد"
        brief["personas"][0]["fixedOutfit"] = "تيشرت أخضر وبنطلون جينز"
        pipeline.atomic_json(self.brief_path, brief)

    def set_personalization(self, payload: dict, *, replace: bool = False) -> dict:
        return pipeline.command_set_personalization(
            argparse.Namespace(
                project=self.project,
                json=json.dumps(payload, ensure_ascii=False),
                file=None,
                replace=replace,
            )
        )


class PersonalizationBriefTests(PersonalizationCase):
    def test_init_seeds_an_empty_block(self) -> None:
        brief = pipeline.read_json(self.brief_path)
        self.assertIn("personalization", brief)
        self.assertTrue(pipeline.personalization_is_empty(brief["personalization"]))

    def test_habits_and_requests_reach_brief_must_show_and_avoid(self) -> None:
        result = self.set_personalization(HABIT_PAYLOAD)
        brief = pipeline.read_json(self.brief_path)
        stored = brief["personalization"]
        self.assertEqual("persona-01", stored["habitFocus"]["personaId"])
        self.assertEqual(
            ["req-01", "req-02", "req-03"], [r["id"] for r in stored["requests"]]
        )
        self.assertFalse(stored["requests"][2]["required"])

        tagged = [m for m in brief["mustShow"] if m.startswith(pipeline.PERSONALIZATION_TAG)]
        self.assertEqual(len(tagged), len(result["mustShow"]))
        self.assertTrue(any("قوس العادة" in m for m in tagged))
        self.assertTrue(any("بيت جدته" in m for m in tagged))
        # Anti-shaming bans ride along with any habit work.
        self.assertTrue(any("عقاب" in a for a in brief["avoid"]))

    def test_second_call_merges_without_duplicating_tagged_lines(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        first = pipeline.read_json(self.brief_path)["mustShow"]
        self.set_personalization(
            {"requests": [{"kind": "person", "textAr": "خالتو هدى"}]}
        )
        brief = pipeline.read_json(self.brief_path)
        self.assertEqual(len(brief["mustShow"]), len(set(brief["mustShow"])))
        self.assertGreater(len(brief["mustShow"]), len(first))
        self.assertEqual(
            ["req-01", "req-02", "req-03", "req-04"],
            [r["id"] for r in brief["personalization"]["requests"]],
        )
        self.assertIsNotNone(brief["personalization"]["habitFocus"])

    def test_replace_drops_previous_entries(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        self.set_personalization(
            {"requests": [{"kind": "thing", "textAr": "دراجته الحمرا"}]}, replace=True
        )
        brief = pipeline.read_json(self.brief_path)
        self.assertIsNone(brief["personalization"]["habitFocus"])
        self.assertEqual(1, len(brief["personalization"]["requests"]))
        self.assertEqual(
            1, len([m for m in brief["mustShow"] if m.startswith(pipeline.PERSONALIZATION_TAG)])
        )
        self.assertEqual([], brief["avoid"])

    def test_show_personalization(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        shown = pipeline.command_show_personalization(
            argparse.Namespace(project=self.project)
        )
        self.assertEqual(3, len(shown["personalization"]["requests"]))
        self.assertIsNone(shown["storyPersonalization"])

    def test_rejects_unusable_input(self) -> None:
        cases = [
            {"habitFocus": {**HABIT_PAYLOAD["habitFocus"], "personaId": "persona-09"}},
            {"habitFocus": {**HABIT_PAYLOAD["habitFocus"], "targetBehaviorAr": "يبطل"}},
            {"habitFocus": {**HABIT_PAYLOAD["habitFocus"], "type": "punish"}},
            {"requests": [{"kind": "vibe", "textAr": "حاجة"}]},
            {
                "secondaryHabits": [
                    {
                        "personaId": "persona-01",
                        "habitAr": "بينسى يرتب",
                        "type": "build",
                        "targetBehaviorAr": "يرجع اللعب مكانها قبل النوم",
                    }
                ]
            },
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(pipeline.WorkflowError):
                    self.set_personalization(payload)

    def test_json_and_file_are_mutually_exclusive(self) -> None:
        with self.assertRaises(pipeline.WorkflowError):
            pipeline.command_set_personalization(
                argparse.Namespace(
                    project=self.project, json=None, file=None, replace=False
                )
            )


class PersonalizationLockTests(PersonalizationCase):
    def setUp(self) -> None:
        super().setUp()
        self.page_ids = pipeline.build_pdf_asset_ids(8)
        self.story_path = self.project / "input" / "story.json"

    def write_story(self, story: dict) -> None:
        pipeline.atomic_json(self.story_path, story)

    def lock(self) -> dict:
        return pipeline.command_lock_story(
            argparse.Namespace(project=self.project, story=None)
        )

    def full_story(self) -> dict:
        story = build_story(self.project, self.page_ids)
        pipeline.sync_personalization_into_story(
            story, pipeline.read_json(self.brief_path)["personalization"]
        )
        story["personalization"]["habitArc"] = {
            "setup": ["page-01"],
            "challenge": ["page-02"],
            "turn": ["page-04"],
            "reinforce": ["page-05", "page-06"],
        }
        story["personalization"]["requestCoverage"] = {
            "req-01": {"pages": ["page-03"], "locationId": "grandma-house"},
            "req-02": {"pages": ["page-01", "page-04"]},
        }
        return story

    def test_complete_story_locks_and_reports_the_arc(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        self.write_story(self.full_story())
        result = self.lock()
        self.assertEqual(["page-04"], result["habitArc"]["turn"])
        self.assertEqual(["req-01", "req-02"], result["coveredRequests"])

    def test_story_without_personalization_still_locks(self) -> None:
        self.write_story(build_story(self.project, self.page_ids))
        self.assertEqual(8, self.lock()["pageCount"])

    def test_missing_habit_arc_blocks_lock(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        story = self.full_story()
        story["personalization"]["habitArc"] = None
        self.write_story(story)
        with self.assertRaisesRegex(pipeline.WorkflowError, "habitArc"):
            self.lock()

    def test_stages_must_run_in_order(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        story = self.full_story()
        story["personalization"]["habitArc"]["turn"] = ["page-01"]
        self.write_story(story)
        with self.assertRaisesRegex(pipeline.WorkflowError, "must finish before"):
            self.lock()

    def test_arc_page_must_include_the_child(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        story = self.full_story()
        for page in story["pages"]:
            if page["id"] == "page-04":
                page["participants"] = []
        self.write_story(story)
        with self.assertRaisesRegex(pipeline.WorkflowError, "participants"):
            self.lock()

    def test_cover_cannot_carry_the_arc(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        story = self.full_story()
        story["personalization"]["habitArc"]["setup"] = ["cover"]
        self.write_story(story)
        with self.assertRaisesRegex(pipeline.WorkflowError, "cover"):
            self.lock()

    def test_required_request_needs_coverage(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        story = self.full_story()
        del story["personalization"]["requestCoverage"]["req-02"]
        self.write_story(story)
        with self.assertRaisesRegex(pipeline.WorkflowError, "req-02"):
            self.lock()

    def test_place_request_must_match_the_page_location(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        story = self.full_story()
        story["personalization"]["requestCoverage"]["req-01"]["pages"] = ["page-02"]
        self.write_story(story)
        with self.assertRaisesRegex(pipeline.WorkflowError, "set elsewhere"):
            self.lock()

    def test_place_request_needs_a_location_id(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        story = self.full_story()
        story["personalization"]["requestCoverage"]["req-01"].pop("locationId")
        self.write_story(story)
        with self.assertRaisesRegex(pipeline.WorkflowError, "locationId"):
            self.lock()

    def test_required_thing_must_be_a_recurring_prop(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        story = self.full_story()
        story["continuity"]["recurringProps"] = ["كورة إسفنج زرقاء"]
        self.write_story(story)
        with self.assertRaisesRegex(pipeline.WorkflowError, "recurringProps"):
            self.lock()

    def test_optional_request_needs_no_coverage(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        story = self.full_story()
        self.assertNotIn("req-03", story["personalization"]["requestCoverage"])
        self.write_story(story)
        self.assertEqual(["req-01", "req-02"], self.lock()["coveredRequests"])

    def test_personalization_is_frozen_after_lock(self) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        self.write_story(self.full_story())
        self.lock()
        with self.assertRaisesRegex(pipeline.WorkflowError, "after lock-story"):
            self.set_personalization({"requests": [{"kind": "thing", "textAr": "شنطته"}]})


class PersonalizationTemplateRouteTests(PersonalizationCase):
    def apply_template(self, template_id: str) -> dict:
        return pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project, template=template_id, note=None, force=False
            )
        )

    def first_template_id(self) -> str:
        return pipeline.command_list_templates(argparse.Namespace(category=None))[
            "templates"
        ][0]["templateId"]

    def test_personalization_after_apply_reopens_the_revision_gate(self) -> None:
        applied = self.apply_template(self.first_template_id())
        self.assertTrue(applied["readyToLock"])
        result = self.set_personalization(HABIT_PAYLOAD)
        selection = result["templateSelection"]
        self.assertTrue(selection["requiresRevision"])
        self.assertIn(pipeline.PERSONALIZATION_NOTE_TAG, selection["customizationNote"])
        self.assertIn("بيت جدته", selection["customizationNote"])
        story = pipeline.read_json(self.project / "input" / "story.json")
        self.assertEqual(
            "persona-01", story["personalization"]["habitFocus"]["personaId"]
        )
        self.assertTrue(
            any("عقاب" in item for item in story["continuity"]["avoid"])
        )

    def test_personalization_before_apply_is_carried_into_the_template_story(
        self,
    ) -> None:
        self.set_personalization(HABIT_PAYLOAD)
        applied = self.apply_template(self.first_template_id())
        self.assertFalse(applied["readyToLock"])
        self.assertIn(pipeline.PERSONALIZATION_NOTE_TAG, applied["customizationNote"])
        story = pipeline.read_json(self.project / "input" / "story.json")
        self.assertEqual(3, len(story["personalization"]["requests"]))

    def test_family_note_survives_a_personalization_update(self) -> None:
        pipeline.command_apply_template(
            argparse.Namespace(
                project=self.project,
                template=self.first_template_id(),
                note="خلي المغامرة يوم عيد ميلاده",
                force=False,
            )
        )
        result = self.set_personalization(HABIT_PAYLOAD)
        note = result["templateSelection"]["customizationNote"]
        self.assertIn("عيد ميلاده", note)
        self.assertIn(pipeline.PERSONALIZATION_NOTE_TAG, note)
        # Re-running must refresh the generated part, not stack another copy.
        again = self.set_personalization({"traits": []})
        self.assertEqual(
            1,
            again["templateSelection"]["customizationNote"].count(
                pipeline.PERSONALIZATION_NOTE_TAG
            ),
        )


if __name__ == "__main__":
    unittest.main()
