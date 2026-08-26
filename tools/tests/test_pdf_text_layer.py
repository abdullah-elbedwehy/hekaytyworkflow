"""End-to-end proof that the book's Arabic survives as real PDF text.

The whole point of drawing captions as a text layer instead of painting them
into the art is that they stay selectable and editable. That property is
invisible on screen — a PDF whose text layer silently failed looks identical to
one that works — so it gets an integration test that builds an actual PDF and
reads the words back out.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS / "scripts"))

import story_pipeline as pipeline  # noqa: E402
import story_review  # noqa: E402
import textlayout  # noqa: E402

PAGE_TEXT = "سارة راحت الجنينة مع جدتها"


def has_deps() -> bool:
    try:
        import arabic_reshaper  # noqa: F401
        import reportlab  # noqa: F401
        from bidi.algorithm import get_display  # noqa: F401
        from pypdf import PdfReader  # noqa: F401
    except ImportError:
        return False
    return True


@unittest.skipUnless(has_deps(), "reportlab / pypdf / arabic shaping not installed")
class PdfTextLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "client"
        (self.project / "output" / "images").mkdir(parents=True)
        self.page_size = (1200, 800)

    def _image(self, name: str) -> str:
        """A plain painted page — stands in for a generated illustration."""
        from PIL import Image

        path = self.project / "output" / "images" / name
        Image.new("RGB", self.page_size, (140, 170, 200)).save(path)
        return str(path.relative_to(self.project))

    def _book(self) -> dict:
        input_dir = self.project / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        story = {
            "title": "سارة في الجنينة",
            "targetAge": 5,
            "pages": [
                {
                    "id": page_id,
                    "text": PAGE_TEXT if page_id == "page-01" else page_id,
                    "beat": "مشهد واضح",
                    "setting": "الجنينة",
                    "action": "سارة ماشية",
                }
                for page_id in ("cover", "page-01", "back-cover")
            ],
        }
        story_path = input_dir / "story.json"
        pipeline.atomic_json(story_path, story)
        story_sha = pipeline.sha256(story_path)
        review_text = story_review.render_story_review(
            story,
            story_sha256=story_sha,
            revision=1,
            prepared_at="2026-08-26T00:00:00+03:00",
        )
        review_path = input_dir / "story-review.md"
        pipeline.atomic_text(review_path, review_text)
        review_sha = story_review.normalized_markdown_sha256(review_text)
        book = {
            "schemaVersion": pipeline.SCHEMA_VERSION,
            "project": str(self.project),
            "status": "review",
            "settings": {
                "pdfPageCount": 3,
                "storyPageCount": 1,
                "orientation": "landscape",
            },
            "pdf": {},
            "storyReview": {
                "status": "approved",
                "path": "input/story-review.md",
                "preparedStorySha256": story_sha,
                "preparedReviewSha256": review_sha,
                "approvedStorySha256": story_sha,
                "approvedReviewSha256": review_sha,
            },
            "review": {
                "status": "not_started",
                "pass": 0,
                "mergedReviewPaths": [],
                "fixQueue": [],
                "manualReview": [],
            },
            "assets": [
                {
                    "id": "cover",
                    "pdfOrder": 1,
                    "includeInPdf": True,
                    "status": "accepted",
                    "imagePath": self._image("cover.png"),
                    "storySha256": story_sha,
                },
                {
                    "id": "page-01",
                    "pdfOrder": 2,
                    "includeInPdf": True,
                    "status": "accepted",
                    "imagePath": self._image("page-01.png"),
                    "storyText": PAGE_TEXT,
                    "storySha256": story_sha,
                },
                {
                    "id": "back-cover",
                    "pdfOrder": 3,
                    "includeInPdf": True,
                    "status": "accepted",
                    "imagePath": self._image("back-cover.png"),
                    "storySha256": story_sha,
                },
            ],
        }
        for asset in book["assets"]:
            asset.setdefault("attempt", 0)
            asset.setdefault("promptVersion", 1)
            asset.setdefault("promptPath", f"input/prompts/{asset['id']}.v01.json")
            asset.setdefault("versions", [])
        return book

    def _build(self) -> dict:
        import argparse

        book = self._book()
        pipeline.save_book(self.project, book)
        return pipeline.command_build(
            argparse.Namespace(project=self.project, edition="draft")
        )

    def test_caption_is_drawn_only_on_pages_that_carry_story_text(self) -> None:
        result = self._build()
        self.assertEqual(1, result["captionCount"])
        self.assertEqual("page-01", result["captions"][0]["assetId"])
        self.assertEqual(PAGE_TEXT, result["captions"][0]["text"])

    def test_arabic_comes_back_out_of_the_pdf_in_logical_order(self) -> None:
        """What a reader copies must be the original Arabic, not glyph soup."""
        from pypdf import PdfReader

        result = self._build()
        reader = PdfReader(result["pdf"])
        recovered = pipeline.page_caption_text(reader.pages[1])
        self.assertEqual(PAGE_TEXT, recovered)

    def test_pages_without_story_text_carry_no_caption(self) -> None:
        from pypdf import PdfReader

        result = self._build()
        reader = PdfReader(result["pdf"])
        for index in (0, 2):
            self.assertEqual("", pipeline.page_caption_text(reader.pages[index]))

    def test_font_is_embedded(self) -> None:
        from pypdf import PdfReader

        result = self._build()
        reader = PdfReader(result["pdf"])
        fonts = reader.pages[1]["/Resources"]["/Font"]
        # reportlab subsets the .ttf into a simple /TrueType font whose
        # descriptor carries the glyph program; the base-14 Helvetica it also
        # registers has no descriptor at all.
        embedded = []
        for font in fonts.values():
            resolved = font.get_object()
            descriptor = resolved.get("/FontDescriptor")
            if descriptor is not None and "/FontFile2" in descriptor.get_object():
                embedded.append(str(resolved["/BaseFont"]))
        self.assertTrue(
            embedded,
            "caption font is not embedded — the PDF would not render off this machine",
        )
        self.assertTrue(
            any("Cairo" in name or "Amiri" in name for name in embedded),
            f"unexpected embedded caption font: {embedded}",
        )

    def test_verify_rejects_a_pdf_whose_text_layer_is_missing(self) -> None:
        """A page that lost its caption must fail verify, not ship silently."""
        import argparse
        from reportlab.pdfgen import canvas

        result = self._build()
        # Replace the built file with a structurally valid three-page PDF that
        # carries no /ActualText caption spans, then bind the manifest hash to
        # that corrupt artifact. This isolates the text-layer gate from the
        # separate asset-snapshot gate.
        broken = canvas.Canvas(result["pdf"], pagesize=(900, 600))
        for _ in range(3):
            broken.showPage()
        broken.save()
        book = pipeline.load_book(self.project)
        book["pdf"]["draft"]["sha256"] = pipeline.sha256(Path(result["pdf"]))
        pipeline.save_book(self.project, book)
        with self.assertRaises(pipeline.WorkflowError) as ctx:
            pipeline.command_verify(
                argparse.Namespace(project=self.project, edition="draft")
            )
        self.assertIn("lost their text layer", str(ctx.exception))
        self.assertTrue(Path(result["pdf"]).is_file())

    def test_verify_renders_the_actual_pdf_pages(self) -> None:
        """Visual review files come from the PDF, including its text overlay."""
        import argparse
        from PIL import Image

        self._build()
        result = pipeline.command_verify(
            argparse.Namespace(project=self.project, edition="draft")
        )
        self.assertEqual(3, len(result["renderedPages"]))
        middle = Path(result["renderedPages"][1])
        self.assertTrue(middle.is_file())
        with Image.open(middle) as rendered:
            self.assertNotEqual(self.page_size, rendered.size)

    def test_stale_draft_cannot_be_reverified_after_an_image_change(self) -> None:
        import argparse
        from PIL import Image

        self._build()
        pipeline.command_verify(
            argparse.Namespace(project=self.project, edition="draft")
        )
        changed = self.project / "output" / "images" / "page-01.png"
        Image.new("RGB", self.page_size, (10, 20, 30)).save(changed)
        book = pipeline.load_book(self.project)
        pipeline.invalidate_pdf_and_reviews(book)
        pipeline.save_book(self.project, book)
        with self.assertRaisesRegex(pipeline.WorkflowError, "not built"):
            pipeline.command_verify(
                argparse.Namespace(project=self.project, edition="draft")
            )

    def test_silent_image_overwrite_breaks_the_pdf_snapshot(self) -> None:
        import argparse
        from PIL import Image

        self._build()
        pipeline.command_verify(
            argparse.Namespace(project=self.project, edition="draft")
        )
        changed = self.project / "output" / "images" / "page-01.png"
        Image.new("RGB", self.page_size, (30, 20, 10)).save(changed)
        with self.assertRaisesRegex(pipeline.WorkflowError, "older page images"):
            pipeline.command_verify(
                argparse.Namespace(project=self.project, edition="draft")
            )

    def test_reviews_and_final_approval_bind_to_the_verified_draft(self) -> None:
        import argparse

        self._build()
        verified = pipeline.command_verify(
            argparse.Namespace(project=self.project, edition="draft")
        )
        review_paths: list[Path] = []
        for role in sorted(pipeline.REVIEWER_ROLES):
            path = self.project / "output" / "reviews" / f"incoming-{role}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            pipeline.atomic_json(
                path,
                {
                    "reviewerRole": role,
                    "decision": "accept",
                    "draftSha256": verified["draftSha256"],
                    "storySha256": verified["storySha256"],
                    "issues": [],
                },
            )
            review_paths.append(path)
        stale = pipeline.read_json(review_paths[0])
        stale["draftSha256"] = "0" * 64
        pipeline.atomic_json(review_paths[0], stale)
        with self.assertRaisesRegex(pipeline.WorkflowError, "draftSha256"):
            pipeline.command_merge_reviews(
                argparse.Namespace(project=self.project, review=review_paths)
            )
        stale["draftSha256"] = verified["draftSha256"]
        pipeline.atomic_json(review_paths[0], stale)
        inconsistent = pipeline.read_json(review_paths[0])
        inconsistent["decision"] = "revise"
        pipeline.atomic_json(review_paths[0], inconsistent)
        with self.assertRaisesRegex(pipeline.WorkflowError, "no blocking issue"):
            pipeline.command_merge_reviews(
                argparse.Namespace(project=self.project, review=review_paths)
            )
        inconsistent["decision"] = "accept"
        pipeline.atomic_json(review_paths[0], inconsistent)
        merged = pipeline.command_merge_reviews(
            argparse.Namespace(project=self.project, review=review_paths)
        )
        self.assertEqual([], merged["fixQueue"])
        pipeline.command_approve_final(
            argparse.Namespace(
                project=self.project,
                statement="راجعت النسخة النهائية وموافق عليها",
            )
        )
        final = pipeline.command_build(
            argparse.Namespace(project=self.project, edition="final")
        )
        self.assertTrue(Path(final["pdf"]).is_file())
        self.assertTrue(final["copiedFromApprovedDraft"])
        self.assertEqual(verified["draftSha256"], final["sha256"])
        checked = pipeline.command_verify(
            argparse.Namespace(project=self.project, edition="final")
        )
        self.assertEqual(3, checked["pageCount"])
        self.assertEqual("complete", pipeline.load_book(self.project)["status"])

        # A later verified draft/approval must make the old final ineligible,
        # even when pixels and captions stayed identical.
        book = pipeline.load_book(self.project)
        draft_path = self.project / book["pdf"]["draft"]["path"]
        with draft_path.open("ab") as handle:
            handle.write(b"\n% second verified draft revision\n")
        book["pdf"]["draft"]["sha256"] = pipeline.sha256(draft_path)
        book["pdf"]["draft"]["status"] = "built"
        pipeline.save_book(self.project, book)
        verified_b = pipeline.command_verify(
            argparse.Namespace(project=self.project, edition="draft")
        )
        review_paths_b: list[Path] = []
        for role in sorted(pipeline.REVIEWER_ROLES):
            path = self.project / "output" / "reviews" / f"second-{role}.json"
            pipeline.atomic_json(
                path,
                {
                    "reviewerRole": role,
                    "decision": "accept",
                    "draftSha256": verified_b["draftSha256"],
                    "storySha256": verified_b["storySha256"],
                    "issues": [],
                },
            )
            review_paths_b.append(path)
        pipeline.command_merge_reviews(
            argparse.Namespace(project=self.project, review=review_paths_b)
        )
        pipeline.command_approve_final(
            argparse.Namespace(
                project=self.project,
                statement="موافق على النسخة التجريبية التانية",
            )
        )
        with self.assertRaisesRegex(
            pipeline.WorkflowError, "not the exact currently approved draft"
        ):
            pipeline.command_verify(
                argparse.Namespace(project=self.project, edition="final")
            )

    def test_attempt_limit_has_an_explicit_manual_resolution(self) -> None:
        import argparse

        self._build()
        verified = pipeline.command_verify(
            argparse.Namespace(project=self.project, edition="draft")
        )
        book = pipeline.load_book(self.project)
        pipeline.asset_by_id(book, "page-01")["attempt"] = pipeline.MAX_ATTEMPTS
        pipeline.save_book(self.project, book)

        review_paths: list[Path] = []
        for role in sorted(pipeline.REVIEWER_ROLES):
            path = self.project / "output" / "reviews" / f"manual-{role}.json"
            issue = []
            decision = "accept"
            if role == "story":
                decision = "revise"
                issue = [
                    {
                        "assetId": "page-01",
                        "severity": "high",
                        "category": "alignment",
                        "detail": "المشهد محتاج قرار بشري بعد تلات محاولات",
                        "fix": "راجع الصورة يدويًا واقبلها أو استبدلها",
                        "fixTarget": "image",
                    }
                ]
            pipeline.atomic_json(
                path,
                {
                    "reviewerRole": role,
                    "decision": decision,
                    "draftSha256": verified["draftSha256"],
                    "storySha256": verified["storySha256"],
                    "issues": issue,
                },
            )
            review_paths.append(path)
        merged = pipeline.command_merge_reviews(
            argparse.Namespace(project=self.project, review=review_paths)
        )
        self.assertEqual(["page-01"], merged["manualReview"])
        resolved = pipeline.command_resolve_manual_review(
            argparse.Namespace(
                project=self.project,
                asset="page-01",
                accept=True,
                image=None,
                statement="راجعت الصورة يدويًا وموافق عليها رغم الملاحظة",
            )
        )
        self.assertEqual("accept-existing", resolved["decision"])
        final_book = pipeline.load_book(self.project)
        self.assertEqual("passed", final_book["review"]["status"])
        self.assertEqual([], final_book["review"]["manualReview"])

    def test_caption_lands_inside_the_declared_safe_zone(self) -> None:
        """The band the illustration was told to keep clear is the band used."""
        page_width, page_height = 1200.0, 800.0
        zone = textlayout.safe_zone_rect(page_width, page_height)
        font = pipeline.register_caption_font({})
        from reportlab.pdfbase import pdfmetrics

        layout = textlayout.layout_caption(
            PAGE_TEXT,
            zone,
            lambda text, size: pdfmetrics.stringWidth(text, font, size),
        )
        for line in layout.lines:
            self.assertGreaterEqual(line.x, zone.x)
            self.assertLessEqual(line.baseline, zone.top)
            self.assertGreaterEqual(line.baseline, zone.y)


if __name__ == "__main__":
    unittest.main()
