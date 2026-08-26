from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS / "scripts"))

import story_review  # noqa: E402


def make_story() -> dict:
    return {
        "title": "أحمد في المزرعة",
        "targetAge": 5,
        "personas": [
            {
                "id": "persona-01",
                "displayName": "أحمد",
                "sourcePath": "/private/personas/ahmed-face.png",
            }
        ],
        "pages": [
            {
                "id": "cover",
                "text": "أحمد في المزرعة",
                "beat": "وعد بمغامرة أحمد الجديدة",
                "setting": "مدخل المزرعة وقت الصبح",
                "action": "أحمد بيفتح بوابة المزرعة",
                "participants": ["persona-01"],
            },
            {
                "id": "page-01",
                "text": "مشي أحمد جنب البقرة وقال: صباح الخير!",
                "beat": "أحمد بيتعرف على أول صاحبة في المزرعة",
                "setting": "طريق ترابي جنب الحظيرة",
                "action": "أحمد والبقرة ماشيين جنب بعض",
                "participants": ["persona-01"],
            },
            {
                "id": "back-cover",
                "text": "رجع أحمد مبسوط ومستني مغامرة جديدة.",
                "beat": "نهاية هادية تقفل المغامرة",
                "setting": "باب المزرعة وقت الغروب",
                "action": "أحمد بيلوح للحيوانات وهو ماشي",
                "participants": ["persona-01"],
            },
        ],
    }


def render() -> str:
    return story_review.render_story_review(
        make_story(),
        story_sha256="a" * 64,
        revision=3,
        prepared_at="2026-08-25T12:00:00+03:00",
    )


class StoryReviewRenderTests(unittest.TestCase):
    def test_render_is_obsidian_friendly_and_private(self) -> None:
        markdown = render()
        self.assertTrue(markdown.startswith("---\nreview_type: hekayati-story\n"))
        self.assertIn('title: "أحمد في المزرعة"', markdown)
        self.assertIn("target_age: 5", markdown)
        self.assertIn("page_count: 3", markdown)
        self.assertIn("ماتغيّرش، ماتنقلش، ولا تمسح", markdown)
        self.assertIn(
            '<!-- hekayati:page:start id="page-01" -->', markdown
        )
        for field in story_review.EDITABLE_FIELDS:
            self.assertIn(
                f'<!-- hekayati:field:start name="{field}" -->', markdown
            )
        self.assertNotIn("/private/personas/ahmed-face.png", markdown)
        self.assertNotIn("sourcePath", markdown)

    def test_render_parse_apply_round_trip_without_mutating_source(self) -> None:
        source = make_story()
        source_snapshot = copy.deepcopy(source)
        markdown = render().replace(
            "مشي أحمد جنب البقرة وقال: صباح الخير!",
            "مشي أحمد جنب البقرة، وقال لها: صباح الخير!",
        )
        expected_ids = [page["id"] for page in source["pages"]]
        edits = story_review.parse_story_review(markdown, expected_ids)
        updated = story_review.apply_story_review(source, edits)

        self.assertEqual(source_snapshot, source)
        self.assertEqual(
            "مشي أحمد جنب البقرة، وقال لها: صباح الخير!",
            updated["pages"][1]["text"],
        )
        self.assertEqual(
            source["pages"][1]["participants"],
            updated["pages"][1]["participants"],
        )

    def test_hash_normalises_crlf_and_trailing_whitespace(self) -> None:
        clean = "# عنوان\n\nسطر عربي\n"
        drifted = "# عنوان  \r\n\r\nسطر عربي\t\r\n\r\n"
        self.assertEqual(
            story_review.normalized_markdown_sha256(clean),
            story_review.normalized_markdown_sha256(drifted),
        )


class StoryReviewParserTests(unittest.TestCase):
    expected_ids = ["cover", "page-01", "back-cover"]

    def assert_rejected(self, markdown: str, message: str) -> None:
        with self.assertRaisesRegex(story_review.StoryReviewError, message):
            story_review.parse_story_review(markdown, self.expected_ids)

    def test_missing_page_id_is_rejected(self) -> None:
        start = '<!-- hekayati:page:start id="page-01" -->\n'
        end = '<!-- hekayati:page:end id="page-01" -->\n'
        markdown = render()
        first = markdown.index(start)
        last = markdown.index(end, first) + len(end)
        self.assert_rejected(markdown[:first] + markdown[last:], "Missing start page ids")

    def test_duplicate_page_id_is_rejected(self) -> None:
        marker = '<!-- hekayati:page:start id="page-01" -->'
        self.assert_rejected(
            render().replace(marker, f"{marker}\n{marker}", 1),
            "Duplicate start page markers",
        )

    def test_unknown_page_id_is_rejected(self) -> None:
        self.assert_rejected(
            render().replace('id="page-01"', 'id="page-99"'),
            "Unknown start page ids",
        )

    def test_out_of_order_page_ids_are_rejected(self) -> None:
        markdown = render()
        markdown = markdown.replace('id="cover"', 'id="swap"')
        markdown = markdown.replace('id="page-01"', 'id="cover"')
        markdown = markdown.replace('id="swap"', 'id="page-01"')
        self.assert_rejected(markdown, "Start page ids are out of order")

    def test_missing_field_marker_is_rejected(self) -> None:
        marker = '<!-- hekayati:field:end name="setting" -->'
        self.assert_rejected(render().replace(marker, "", 1), "missing setting")

    def test_duplicate_field_marker_is_rejected(self) -> None:
        marker = '<!-- hekayati:field:start name="beat" -->'
        self.assert_rejected(
            render().replace(marker, f"{marker}\n{marker}", 1),
            "duplicate beat",
        )

    def test_empty_editable_value_is_rejected(self) -> None:
        old = (
            '<!-- hekayati:field:start name="action" -->\n'
            "أحمد بيفتح بوابة المزرعة\n"
            '<!-- hekayati:field:end name="action" -->'
        )
        new = (
            '<!-- hekayati:field:start name="action" -->\n\n'
            '<!-- hekayati:field:end name="action" -->'
        )
        self.assert_rejected(render().replace(old, new, 1), "empty action")

    def test_apply_requires_exact_four_fields_for_every_page(self) -> None:
        edits = story_review.parse_story_review(render(), self.expected_ids)
        del edits["page-01"]["action"]
        with self.assertRaisesRegex(story_review.StoryReviewError, "missing fields"):
            story_review.apply_story_review(make_story(), edits)


if __name__ == "__main__":
    unittest.main()
