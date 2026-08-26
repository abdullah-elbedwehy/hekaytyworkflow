from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import tempfile
import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parent))

import handoff_fixture  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PIPELINE_PATH = ROOT / "tools" / "scripts" / "story_pipeline.py"
SPEC = importlib.util.spec_from_file_location("story_pipeline", PIPELINE_PATH)
assert SPEC and SPEC.loader
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


# The shared fixture is a full `hekayati-22` book, so index 1 is the fixed
# dedication and the first authored story page sits at index 2.
FIRST_STORY_INDEX = 2
FIRST_STORY_PAGE_ID = "page-02"


def make_story() -> dict:
    """A clean, doctrine-valid story to mutate one page at a time."""
    return handoff_fixture.build_handoff_story()


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
        story["pages"][FIRST_STORY_INDEX]["text"] = "ذهب سلمى إلى بيتًا بعيدًا."
        report = pipeline.review_story_quality(story)
        codes = {issue["code"] for issue in report["errors"]}
        self.assertIn("formal-case-ending", codes)
        self.assertIn("age-language-term", codes)

        story = make_story()
        story["pages"][FIRST_STORY_INDEX]["text"] = "قالت سلمى: شكرًا يا ماما."
        report = pipeline.review_story_quality(story)
        self.assertFalse(
            any(issue["code"] == "formal-case-ending" for issue in report["errors"])
        )

    def test_exact_quote_can_be_protected(self) -> None:
        story = make_story()
        quote = "عِلْمًا نَافِعًا"
        story["pages"][FIRST_STORY_INDEX]["text"] = quote
        story["pages"][FIRST_STORY_INDEX]["protectedPhrases"] = [
            {"registryId": "dua-beneficial-knowledge"}
        ]
        report = pipeline.review_story_quality(story)
        self.assertFalse(
            any(issue.get("pageId") == FIRST_STORY_PAGE_ID for issue in report["errors"])
        )

    def test_arbitrary_protection_cannot_hide_bad_copy(self) -> None:
        story = make_story()
        bad = "ذهب سلمى إلى بيتًا بعيدًا With Latin."
        story["pages"][FIRST_STORY_INDEX]["text"] = bad
        story["pages"][FIRST_STORY_INDEX]["protectedPhrases"] = [bad]
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
        story["pages"][FIRST_STORY_INDEX]["text"] = "فذهبت سلمى للبيت، وليست مستعدة، واستيقظت بدري."
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
        story["pages"][FIRST_STORY_INDEX]["text"] = "وجدان سلمى كان هادي في رأي ماما."
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
        story["pages"][FIRST_STORY_INDEX + 1]["text"] = " ".join(["كلمة"] * 23) + "."
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "page-too-long" for issue in report["errors"])
        )

    def test_sentence_caps_and_cover_exemption(self) -> None:
        story = make_story()
        story["pages"][FIRST_STORY_INDEX]["text"] = "سلمى جريت. سلمى وقفت. سلمى ضحكت."
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "too-many-sentences" for issue in report["errors"])
        )

        story = make_story()
        story["pages"][FIRST_STORY_INDEX]["text"] = " ".join(["كلمة"] * 11) + "."
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
        story["pages"][FIRST_STORY_INDEX + 1]["text"] = story["pages"][FIRST_STORY_INDEX]["text"]
        story["refrainPhrases"] = [story["pages"][FIRST_STORY_INDEX]["text"]]
        story["pages"][FIRST_STORY_INDEX + 2]["text"] = "فجأة الباب فتح، وفجأة النور اختفى."
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
        story["pages"][FIRST_STORY_INDEX]["text"] = "هيلا هوب"
        story["pages"][FIRST_STORY_INDEX + 1]["text"] = "هيلا هوب"
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
        story["narrativeArc"]["decisiveAction"] = list(story["narrativeArc"]["choice"])
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "arc-stage-overlap" for issue in report["errors"])
        )

        story = make_story()
        by_id = {page["id"]: page for page in story["pages"]}
        by_id[story["narrativeArc"]["choice"][0]]["participants"] = []
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
        story["narrativeArc"]["disruption"] = [FIRST_STORY_PAGE_ID]
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(
                issue["code"] == "page-owned-by-multiple-stages"
                for issue in report["errors"]
            )
        )

        story = make_story()
        story["pages"][FIRST_STORY_INDEX]["combinedArcStages"] = ["setup", "resolution"]
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(
                issue["code"] == "unused-combined-arc-stages"
                for issue in report["errors"]
            )
        )

    def test_new_cast_and_place_need_an_explicit_bridge(self) -> None:
        story = make_story()
        story["pages"][FIRST_STORY_INDEX + 1]["participants"] = ["persona-02"]
        story["pages"][FIRST_STORY_INDEX + 1]["locationId"] = "street"
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "unbridged-scene-cut" for issue in report["errors"])
        )
        story["pages"][FIRST_STORY_INDEX + 1]["transitionFromPrevious"] = (
            "لأن سلمى بعتت الرسالة، صاحبتها خرجت تدور عليها في الشارع."
        )
        story["pages"][FIRST_STORY_INDEX + 1]["text"] = story["pages"][FIRST_STORY_INDEX + 1]["transitionFromPrevious"]
        story["pages"][FIRST_STORY_INDEX + 2]["transitionFromPrevious"] = (
            "صاحبتها رجعت لسلمى وقالت لها اللي شافته."
        )
        story["pages"][FIRST_STORY_INDEX + 2]["text"] = story["pages"][FIRST_STORY_INDEX + 2]["transitionFromPrevious"]
        report = pipeline.review_story_quality(story)
        self.assertFalse(
            any(issue["code"] == "unbridged-scene-cut" for issue in report["errors"])
        )

    def test_same_hero_cannot_teleport_with_hidden_metadata(self) -> None:
        story = make_story()
        story["pages"][FIRST_STORY_INDEX + 1]["locationId"] = "moon"
        story["pages"][FIRST_STORY_INDEX + 1]["transitionFromPrevious"] = "بعدها سلمى وصلت للقمر."
        report = pipeline.review_story_quality(story)
        self.assertTrue(
            any(issue["code"] == "unbridged-scene-cut" for issue in report["errors"])
        )
        story["pages"][FIRST_STORY_INDEX + 1]["text"] = "بعدها سلمى وصلت للقمر عشان تكمل مهمتها."
        story["pages"][FIRST_STORY_INDEX + 1]["transitionFromPrevious"] = story["pages"][FIRST_STORY_INDEX + 1]["text"]
        story["pages"][FIRST_STORY_INDEX + 2]["text"] = "بعد الرحلة سلمى رجعت مكتبها ومعاها العلامة."
        story["pages"][FIRST_STORY_INDEX + 2]["transitionFromPrevious"] = story["pages"][FIRST_STORY_INDEX + 2]["text"]
        report = pipeline.review_story_quality(story)
        self.assertFalse(
            any(issue["code"] == "unbridged-scene-cut" for issue in report["errors"])
        )

    def test_malformed_json_shapes_return_review_errors_not_type_errors(self) -> None:
        cases = []
        story = make_story()
        story["pages"][FIRST_STORY_INDEX]["id"] = []
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
