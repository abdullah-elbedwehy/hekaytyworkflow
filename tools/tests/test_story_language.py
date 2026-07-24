from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
PIPELINE_PATH = ROOT / "tools" / "scripts" / "story_pipeline.py"
SPEC = importlib.util.spec_from_file_location("story_pipeline", PIPELINE_PATH)
assert SPEC and SPEC.loader
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


def make_story() -> dict:
    page_ids = [
        "cover",
        *[f"page-{index:02d}" for index in range(1, 9)],
        "back-cover",
    ]
    beats = [
        "عنوان يعد بخطوة صغيرة",
        "سلمى تشوف الغرض لأول مرة",
        "الغرض يتحرك بعيد عنها",
        "سلمى تحدد هدفها الواضح",
        "سلمى تجرب الحل الأول",
        "المحاولة تكشف علامة جديدة",
        "سلمى تختار الحل المناسب",
        "سلمى تنفذ اختيارها بنفسها",
        "النتيجة تظهر قدام سلمى",
        "سلمى ترجع مبسوطة وهادية",
    ]
    actions = [
        "سلمى بتبص للعنوان",
        "سلمى بتمد إيدها",
        "الغرض بيتحرك بعيد",
        "سلمى بتشاور لهدفها",
        "سلمى بتحرك أول أداة",
        "سلمى بتلاحظ العلامة",
        "سلمى بتختار بإيدها",
        "سلمى بتنظم القطع",
        "سلمى بتشوف النتيجة",
        "سلمى بترجع مكانها",
    ]
    texts = [
        "سلمى وعلبة الألوان",
        "سلمى لقت علبة ألوان مقفولة فوق مكتبها.",
        "هزّت العلبة، فسمعت قطعة صغيرة بتتحرك جواها.",
        "قالت: هفتحها من غير ما أكسر الغطا.",
        "جرّبت المفتاح الأزرق، لكنه ما لفّش.",
        "بصّت تحت المكتب، ولقت علامة نجمة.",
        "اختارت المفتاح اللي عليه نفس النجمة.",
        "حطّته في القفل، ولفّته براحة.",
        "اتفتحت العلبة، وظهرت ألوان جدتها القديمة.",
        "سلمى رتبت الألوان، وقفلت العلبة في مكانها.",
    ]
    pages = [
        {
            "id": page_id,
            "text": texts[index],
            "beat": beats[index],
            "participants": ["persona-01"],
            "guests": [],
            "locationId": "home",
            "setting": "أوضة سلمى",
            "action": actions[index],
        }
        for index, page_id in enumerate(page_ids)
    ]
    return {
        "title": "حكاية سلمى",
        "targetAge": 5,
        "languageProfileId": "age-3-5",
        "language": "natural Egyptian Arabic",
        "visualStyle": "storybook",
        "personas": [
            {
                "id": "persona-01",
                "displayName": "سلمى",
                "role": "hero",
                "fixedOutfit": "فستان أخضر",
            }
        ],
        "narrativeArc": {
            "setup": ["page-01"],
            "disruption": ["page-02"],
            "goal": ["page-03"],
            "attempts": ["page-04", "page-05"],
            "choice": ["page-06"],
            "decisiveAction": ["page-07"],
            "payoff": ["page-08"],
            "resolution": ["back-cover"],
        },
        "pages": pages,
    }


class AgeProfileCatalogTests(unittest.TestCase):
    def test_age_boundaries_resolve_without_overlap(self) -> None:
        expected = {
            1: "age-1-2",
            2: "age-1-2",
            3: "age-3-5",
            5: "age-3-5",
            6: "age-6-8",
            8: "age-6-8",
        }
        for age, profile_id in expected.items():
            with self.subTest(age=age):
                self.assertEqual(
                    profile_id, pipeline.get_story_language_profile(age)["id"]
                )
        for age in (0, 9):
            with self.subTest(age=age):
                with self.assertRaises(pipeline.WorkflowError):
                    pipeline.get_story_language_profile(age)

    def test_profile_commands_expose_budgets_and_lexicon(self) -> None:
        listed = pipeline.command_list_age_profiles(argparse.Namespace())
        self.assertEqual(3, len(listed["profiles"]))
        shown = pipeline.command_show_age_profile(argparse.Namespace(age=6))
        self.assertEqual("age-6-8", shown["profile"]["id"])
        self.assertTrue(shown["profile"]["lexicon"]["preferred"])
        self.assertEqual(32, shown["profile"]["pageBudget"]["hardMaxWords"])

    def test_malformed_dictionary_entry_is_rejected(self) -> None:
        catalog = copy.deepcopy(pipeline.load_story_language_catalog())
        del catalog["profiles"]["age-3-5"]["lexicon"]["avoidOrReplace"][0][
            "severity"
        ]
        with tempfile.TemporaryDirectory() as raw_tmp:
            path = Path(raw_tmp) / "age-profiles.json"
            path.write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with mock.patch.object(
                pipeline, "story_language_catalog_path", return_value=path
            ):
                with self.assertRaises(pipeline.WorkflowError):
                    pipeline.load_story_language_catalog()


class StoryLanguageReviewTests(unittest.TestCase):
    def test_clean_story_passes_with_non_blocking_density_warnings(self) -> None:
        report = pipeline.review_story_quality(make_story())
        self.assertEqual("pass", report["decision"])
        self.assertEqual([], report["errors"])
        self.assertEqual("age-3-5", report["languageProfileId"])

    def test_formal_register_and_tanween_are_blocking(self) -> None:
        story = make_story()
        story["pages"][1]["text"] = "ذهب سلمى إلى بيتًا بعيدًا."
        report = pipeline.review_story_quality(story)
        codes = {issue["code"] for issue in report["errors"]}
        self.assertIn("formal-case-ending", codes)
        self.assertIn("age-language-term", codes)

        story = make_story()
        story["pages"][1]["text"] = "قالت سلمى: شكرًا يا ماما."
        report = pipeline.review_story_quality(story)
        self.assertFalse(
            any(issue["code"] == "formal-case-ending" for issue in report["errors"])
        )

    def test_exact_quote_can_be_protected(self) -> None:
        story = make_story()
        quote = "عِلْمًا نَافِعًا"
        story["pages"][1]["text"] = quote
        story["pages"][1]["protectedPhrases"] = [
            {"registryId": "dua-beneficial-knowledge"}
        ]
        report = pipeline.review_story_quality(story)
        self.assertFalse(
            any(issue.get("pageId") == "page-01" for issue in report["errors"])
        )

    def test_arbitrary_protection_cannot_hide_bad_copy(self) -> None:
        story = make_story()
        bad = "ذهب سلمى إلى بيتًا بعيدًا With Latin."
        story["pages"][1]["text"] = bad
        story["pages"][1]["protectedPhrases"] = [bad]
        report = pipeline.review_story_quality(story)
        codes = {issue["code"] for issue in report["errors"]}
        self.assertIn("invalid-protected-phrase", codes)
        self.assertIn("age-language-term", codes)
        self.assertIn("formal-case-ending", codes)
        self.assertIn("latin-in-story-text", codes)

    def test_language_label_must_be_canonical(self) -> None:
        story = make_story()
        story["language"] = "not Egyptian at all"
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "wrong-language-register" for issue in report["errors"])
        )

    def test_inflected_formal_verbs_are_found(self) -> None:
        story = make_story()
        story["pages"][1]["text"] = "فذهبت سلمى للبيت، وليست مستعدة، واستيقظت بدري."
        report = pipeline.review_story_quality(story)
        blocked_terms = {
            issue.get("term")
            for issue in report["errors"]
            if issue["code"] == "age-language-term"
        }
        warned_terms = {
            issue.get("term")
            for issue in report["warnings"]
            if issue["code"] == "age-language-term"
        }
        self.assertIn("ذهب", blocked_terms)
        self.assertIn("ليس", blocked_terms)
        self.assertIn("استيقظ", warned_terms)

        story = make_story()
        story["pages"][1]["text"] = "وجدان سلمى كان هادي في رأي ماما."
        report = pipeline.review_story_quality(story)
        self.assertFalse(
            any(
                issue.get("term") == "وجد"
                for issue in [*report["errors"], *report["warnings"]]
            )
        )
        self.assertFalse(
            any(
                issue.get("term") == "رأى"
                for issue in [*report["errors"], *report["warnings"]]
            )
        )

    def test_page_hard_word_cap_blocks_lock_quality(self) -> None:
        story = make_story()
        story["pages"][2]["text"] = " ".join(["كلمة"] * 23) + "."
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "page-too-long" for issue in report["errors"])
        )

    def test_sentence_caps_and_cover_exemption(self) -> None:
        story = make_story()
        story["pages"][1]["text"] = "سلمى جريت. سلمى وقفت. سلمى ضحكت."
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "too-many-sentences" for issue in report["errors"])
        )

        story = make_story()
        story["pages"][1]["text"] = " ".join(["كلمة"] * 11) + "."
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "sentence-too-long" for issue in report["errors"])
        )

        story = make_story()
        story["pages"][0]["text"] = " ".join(["عنوان"] * 30) + "."
        report = pipeline.review_story_quality(story)
        self.assertFalse(
            any(
                issue.get("pageId") == "cover"
                and issue["code"] in {"page-too-long", "sentence-too-long"}
                for issue in report["errors"]
            )
        )

    def test_repeated_visible_text_and_suddenly_are_blocking(self) -> None:
        story = make_story()
        story["pages"][2]["text"] = story["pages"][1]["text"]
        story["refrainPhrases"] = [story["pages"][1]["text"]]
        story["pages"][3]["text"] = "فجأة الباب فتح، وفجأة النور اختفى."
        report = pipeline.review_story_quality(story)
        codes = {issue["code"] for issue in report["errors"]}
        self.assertIn("repeated-visible-text", codes)
        self.assertIn("suddenly-as-story-glue", codes)

    def test_refrain_must_be_real_short_arabic_used_on_multiple_pages(self) -> None:
        story = make_story()
        story["targetAge"] = 2
        story["languageProfileId"] = "age-1-2"
        story["refrainPhrases"] = ["!!!"]
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "invalid-refrain-list" for issue in report["errors"])
        )

        story = make_story()
        story["refrainPhrases"] = ["هيلا هوب"]
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "invalid-refrain-use" for issue in report["errors"])
        )

        story = make_story()
        story["targetAge"] = 2
        story["languageProfileId"] = "age-1-2"
        story["refrainPhrases"] = ["هيلا هوب", "هيلا، هوب"]
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "invalid-refrain-list" for issue in report["errors"])
        )

        story = make_story()
        story["targetAge"] = 2
        story["languageProfileId"] = "age-1-2"
        story["refrainPhrases"] = ["هيلا هوب"]
        story["pages"][1]["text"] = "هيلا هوب"
        story["pages"][2]["text"] = "هيلا هوب"
        report = pipeline.review_story_quality(story)
        self.assertFalse(
            any(issue["code"] == "repeated-visible-text" for issue in report["errors"])
        )

    def test_missing_arc_and_unassigned_pages_are_blocking(self) -> None:
        story = make_story()
        story.pop("narrativeArc")
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "missing-narrative-arc" for issue in report["errors"])
        )

        story = make_story()
        story["narrativeArc"]["attempts"] = ["page-04"]
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "unassigned-story-pages" for issue in report["errors"])
        )

    def test_arc_order_and_hero_owned_choice_are_blocking(self) -> None:
        story = make_story()
        story["narrativeArc"]["choice"] = ["page-07"]
        story["narrativeArc"]["decisiveAction"] = ["page-06"]
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "arc-stage-overlap" for issue in report["errors"])
        )

        story = make_story()
        by_id = {page["id"]: page for page in story["pages"]}
        by_id["page-06"]["participants"] = []
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(
                issue["code"] == "hero-does-not-own-stage"
                and issue["stage"] == "choice"
                for issue in report["errors"]
            )
        )

    def test_arc_page_cannot_implicitly_own_two_stages(self) -> None:
        story = make_story()
        story["narrativeArc"]["disruption"] = ["page-01"]
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(
                issue["code"] == "page-owned-by-multiple-stages"
                for issue in report["errors"]
            )
        )

        story = make_story()
        story["pages"][1]["combinedArcStages"] = ["setup", "resolution"]
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(
                issue["code"] == "unused-combined-arc-stages"
                for issue in report["errors"]
            )
        )

    def test_new_cast_and_place_need_an_explicit_bridge(self) -> None:
        story = make_story()
        story["pages"][2]["participants"] = ["persona-02"]
        story["pages"][2]["locationId"] = "street"
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "unbridged-scene-cut" for issue in report["errors"])
        )
        story["pages"][2]["transitionFromPrevious"] = (
            "لأن سلمى بعتت الرسالة، صاحبتها خرجت تدور عليها في الشارع."
        )
        story["pages"][2]["text"] = story["pages"][2]["transitionFromPrevious"]
        story["pages"][3]["transitionFromPrevious"] = (
            "صاحبتها رجعت لسلمى وقالت لها اللي شافته."
        )
        story["pages"][3]["text"] = story["pages"][3]["transitionFromPrevious"]
        report = pipeline.review_story_quality(story)
        self.assertFalse(
            any(issue["code"] == "unbridged-scene-cut" for issue in report["errors"])
        )

    def test_same_hero_cannot_teleport_with_hidden_metadata(self) -> None:
        story = make_story()
        story["pages"][2]["locationId"] = "moon"
        story["pages"][2]["transitionFromPrevious"] = "بعدها سلمى وصلت للقمر."
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "unbridged-scene-cut" for issue in report["errors"])
        )
        story["pages"][2]["text"] = "بعدها سلمى وصلت للقمر عشان تكمل مهمتها."
        story["pages"][2]["transitionFromPrevious"] = story["pages"][2]["text"]
        story["pages"][3]["text"] = "بعد الرحلة سلمى رجعت مكتبها ومعاها العلامة."
        story["pages"][3]["transitionFromPrevious"] = story["pages"][3]["text"]
        report = pipeline.review_story_quality(story)
        self.assertFalse(
            any(issue["code"] == "unbridged-scene-cut" for issue in report["errors"])
        )

    def test_malformed_json_shapes_return_review_errors_not_type_errors(self) -> None:
        cases = []
        story = make_story()
        story["pages"][1]["id"] = []
        cases.append(story)
        story = make_story()
        story["personas"] = 1
        cases.append(story)
        story = make_story()
        story["narrativeArc"]["choice"] = 1
        cases.append(story)
        for story in cases:
            with self.subTest(story=story):
                report = pipeline.review_story_quality(story)
                self.assertEqual("revise", report["decision"])


if __name__ == "__main__":
    unittest.main()
