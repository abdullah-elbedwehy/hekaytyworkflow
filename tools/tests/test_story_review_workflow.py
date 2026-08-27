from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
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


def build_valid_story(page_ids: list[str]) -> dict:
    """The shared `hekayati-22` story (handoff §7)."""
    story = handoff_fixture.build_handoff_story()
    assert [page["id"] for page in story["pages"]] == list(page_ids)
    return story


def replace_review_field(markdown: str, page_id: str, field: str, value: str) -> str:
    page_marker = f'<!-- hekayati:page:start id="{page_id}" -->'
    next_page_marker = f'<!-- hekayati:page:end id="{page_id}" -->'
    field_marker = f'<!-- hekayati:field:start name="{field}" -->'
    field_end_marker = f'<!-- hekayati:field:end name="{field}" -->'
    page_start = markdown.index(page_marker)
    page_end = markdown.index(next_page_marker, page_start)
    field_start = markdown.index(field_marker, page_start, page_end) + len(field_marker)
    field_end = markdown.index(field_end_marker, field_start, page_end)
    return markdown[:field_start] + f"\n{value}\n" + markdown[field_end:]


class StoryReviewWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()
        personas = self.project / "personas"
        personas.mkdir()
        self.persona_path = (personas / "ahmed.png").resolve()
        self.persona_path.write_bytes(b"test fixture")

        pipeline.command_init(argparse.Namespace(project=self.project, pages=handoff_fixture.PDF_PAGE_COUNT))
        brief_path = self.project / "input" / "brief.json"
        brief = pipeline.read_json(brief_path)
        brief["personas"][0]["displayName"] = "أحمد"
        brief["personas"][0]["fixedOutfit"] = "تيشرت أخضر وبنطلون جينز"
        pipeline.atomic_json(brief_path, brief)
        pipeline.command_set_story_goal(
            argparse.Namespace(
                project=self.project,
                mode="educational",
                goal="يمسك كورة الإسفنج ويعد لتلاتة",
            )
        )
        self.story_path = self.project / "input" / "story.json"
        pipeline.atomic_json(
            self.story_path,
            build_valid_story(pipeline.build_pdf_asset_ids(handoff_fixture.PDF_PAGE_COUNT)),
        )
        self.review_path = self.project / "input" / "story-review.md"

    def prepare(self) -> dict:
        return pipeline.command_prepare_story_review(
            argparse.Namespace(project=self.project, force=False)
        )

    def approve(self, statement: str = "راجعت القصة ووافقت على كل صفحاتها") -> dict:
        return pipeline.command_approve_story_review(
            argparse.Namespace(project=self.project, statement=statement)
        )

    def lock(self) -> dict:
        return pipeline.command_lock_story(
            argparse.Namespace(project=self.project, story=None)
        )

    def confirm_consent(self) -> None:
        pipeline.command_confirm_consent(
            argparse.Namespace(
                project=self.project,
                statement="ولي الأمر وافق على استخدام الصورة في القصة",
            )
        )

    def assert_story_gate_blocks_downstream(self) -> None:
        with self.assertRaisesRegex(pipeline.WorkflowError, "Story review.*stale"):
            pipeline.command_begin_asset(
                argparse.Namespace(
                    project=self.project,
                    asset="character-sheet",
                    allow_parallel=False,
                )
            )
        with self.assertRaisesRegex(pipeline.WorkflowError, "Story review.*stale"):
            pipeline.command_build(
                argparse.Namespace(project=self.project, edition="draft")
            )
        preflight = pipeline.command_preflight(argparse.Namespace(project=self.project))
        check = next(
            row for row in preflight["checks"] if row["id"] == "story-review-approved"
        )
        self.assertFalse(check["ok"])
        self.assertIn("stale", check["detail"])

    def test_prepare_creates_obsidian_markdown_and_lock_waits_for_approval(self) -> None:
        result = self.prepare()
        markdown = self.review_path.read_text(encoding="utf-8")

        self.assertTrue(result["created"])
        self.assertEqual("awaiting_user", result["storyReview"]["status"])
        self.assertTrue(markdown.startswith("---\nreview_type: hekayati-story\n"))
        self.assertIn("# مراجعة قصة: قصة أحمد", markdown)
        self.assertIn("> [!warning]", markdown)
        self.assertEqual(
            handoff_fixture.PDF_PAGE_COUNT,
            markdown.count("<!-- hekayati:page:start"),
        )
        self.assertEqual(
            handoff_fixture.PDF_PAGE_COUNT, markdown.count("\n## ")
        )
        # The two doctrine-owned pages announce themselves to the editor.
        self.assertIn("الإهداء (نص ثابت)", markdown)
        self.assertIn("قصص تانية (تخطيط ثابت)", markdown)
        self.assertNotIn(str(self.persona_path), markdown)
        self.assertNotIn("imagePath", markdown)

        with self.assertRaisesRegex(pipeline.WorkflowError, "awaiting_user"):
            self.lock()

    def test_approval_requires_statement_then_applies_edited_markdown_and_locks(self) -> None:
        self.prepare()
        markdown = self.review_path.read_text(encoding="utf-8")
        revised_text = "قبل الفصل، أحمد ابتسم ومسك كورة الإسفنج."
        revised_setting = "فناء المدرسة في شمس الصبح"
        markdown = replace_review_field(markdown, "page-02", "text", revised_text)
        markdown = replace_review_field(
            markdown, "page-02", "setting", revised_setting
        )
        self.review_path.write_text(markdown, encoding="utf-8")

        with self.assertRaisesRegex(pipeline.WorkflowError, "too short"):
            self.approve("")

        before = pipeline.command_story_review_status(
            argparse.Namespace(project=self.project)
        )
        self.assertEqual("changes_detected", before["storyReview"]["status"])

        approved = self.approve()
        story = pipeline.read_json(self.story_path)
        page = next(row for row in story["pages"] if row["id"] == "page-02")
        self.assertEqual(revised_text, page["text"])
        self.assertEqual(revised_setting, page["setting"])
        self.assertEqual("approved", approved["storyReview"]["status"])

        locked = self.lock()
        self.assertEqual(handoff_fixture.PDF_PAGE_COUNT, locked["pageCount"])
        self.assertEqual("input/story.json", pipeline.load_book(self.project)["storyPath"])

    def test_status_reports_each_review_transition(self) -> None:
        initial = pipeline.command_story_review_status(
            argparse.Namespace(project=self.project)
        )
        self.assertEqual("not_prepared", initial["storyReview"]["status"])

        self.prepare()
        waiting = pipeline.command_story_review_status(
            argparse.Namespace(project=self.project)
        )
        self.assertEqual("awaiting_user", waiting["storyReview"]["status"])

        markdown = self.review_path.read_text(encoding="utf-8")
        self.review_path.write_text(markdown + "\nملاحظة للمراجع\n", encoding="utf-8")
        changed = pipeline.command_story_review_status(
            argparse.Namespace(project=self.project)
        )
        self.assertEqual("changes_detected", changed["storyReview"]["status"])

        self.approve()
        approved = pipeline.command_story_review_status(
            argparse.Namespace(project=self.project)
        )
        self.assertEqual("approved", approved["storyReview"]["status"])

    def test_approval_hashes_the_same_markdown_snapshot_it_applies(self) -> None:
        self.prepare()
        original = self.review_path.read_text(encoding="utf-8")
        edited = replace_review_field(
            original,
            "page-02",
            "text",
            "قبل الفصل، أحمد مسك كورة الإسفنج الزرقا وابتسم.",
        )
        self.review_path.write_text(edited, encoding="utf-8")
        real_read_text = Path.read_text
        review_reads = 0

        def changing_read_text(path: Path, *args: object, **kwargs: object) -> str:
            nonlocal review_reads
            value = real_read_text(path, *args, **kwargs)
            if path.resolve() == self.review_path.resolve():
                review_reads += 1
                if review_reads > 1:
                    return value + "\nتعديل متزامن بعد لقطة الاعتماد\n"
            return value

        with mock.patch.object(Path, "read_text", changing_read_text):
            result = self.approve()

        self.assertEqual("stale", result["storyReview"]["status"])
        state = pipeline.load_book(self.project)["storyReview"]
        self.assertEqual(
            pipeline.normalized_markdown_sha256(edited),
            state["approvedReviewSha256"],
        )
        story = pipeline.read_json(self.story_path)
        self.assertEqual(
            "قبل الفصل، أحمد مسك كورة الإسفنج الزرقا وابتسم.",
            handoff_fixture.page_by_id(story, "page-02")["text"],
        )

    def test_story_json_drift_after_approval_blocks_generation_build_and_preflight(self) -> None:
        self.prepare()
        self.approve()
        self.lock()
        self.confirm_consent()

        story = pipeline.read_json(self.story_path)
        story["pages"][1]["text"] = "تعديل اتعمل بعد موافقة اليوزر."
        pipeline.atomic_json(self.story_path, story)

        self.assert_story_gate_blocks_downstream()

    def test_review_markdown_drift_after_approval_blocks_generation_build_and_preflight(self) -> None:
        self.prepare()
        self.approve()
        self.lock()
        self.confirm_consent()

        markdown = self.review_path.read_text(encoding="utf-8")
        self.review_path.write_text(markdown + "\nتعديل بعد الموافقة\n", encoding="utf-8")

        self.assert_story_gate_blocks_downstream()

    def test_init_rejects_client_project_inside_workflow_repository(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw_project:
            nested_project = Path(raw_project).resolve()
            with self.assertRaisesRegex(
                pipeline.WorkflowError, "allowed only under.*Rawy/Clients"
            ):
                pipeline.command_init(
                    argparse.Namespace(project=nested_project, pages=handoff_fixture.PDF_PAGE_COUNT)
                )


if __name__ == "__main__":
    unittest.main()
