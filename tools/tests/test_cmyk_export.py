"""The last step before print: is the file the press gets actually CMYK?

A book that looks right on screen and separates wrong on press is only caught
here, so the export refuses to leave a file named `-cmyk.pdf` behind unless it
verified. These tests cover the refusal paths as well as the happy one.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS / "scripts"))

import cmyk_export  # noqa: E402


def has_deps() -> bool:
    try:
        import reportlab  # noqa: F401
        from PIL import Image  # noqa: F401
        from pypdf import PdfReader  # noqa: F401
    except ImportError:
        return False
    return shutil.which("gs") is not None


class SourceResolutionTests(unittest.TestCase):
    """Which PDF gets converted is read from book.json, never guessed."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        (self.project / "output" / "pdf").mkdir(parents=True)

    def _book(self, entry: dict) -> None:
        (self.project / "output" / "book.json").write_text(
            json.dumps({"pdf": {"final": entry}}), encoding="utf-8"
        )

    def test_missing_book_is_an_actionable_error(self) -> None:
        with self.assertRaises(cmyk_export.CmykError) as caught:
            cmyk_export.pdf_from_project(self.project, "final")
        self.assertIn("--pdf", str(caught.exception))

    def test_unbuilt_edition_is_refused(self) -> None:
        self._book({})
        with self.assertRaises(cmyk_export.CmykError) as caught:
            cmyk_export.pdf_from_project(self.project, "final")
        self.assertIn("Build and verify", str(caught.exception))

    def test_an_unverified_pdf_is_refused(self) -> None:
        pdf = self.project / "output" / "pdf" / "final.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        self._book({"path": "output/pdf/final.pdf", "status": "stale"})
        with self.assertRaises(cmyk_export.CmykError) as caught:
            cmyk_export.pdf_from_project(self.project, "final")
        self.assertIn("stale", str(caught.exception))


class IccResolutionTests(unittest.TestCase):
    def test_a_missing_explicit_profile_is_named(self) -> None:
        with self.assertRaises(cmyk_export.CmykError) as caught:
            cmyk_export.resolve_icc("/no/such/profile.icc")
        self.assertIn("profile.icc", str(caught.exception))

    def test_a_press_profile_outranks_the_generic_one(self) -> None:
        """Generic CMYK converts, but no press tuned it — it is the last resort."""
        candidates = list(cmyk_export.DEFAULT_ICC_CANDIDATES)
        generic = [i for i, c in enumerate(candidates) if "Generic CMYK" in c]
        press = [i for i, c in enumerate(candidates) if "FOGRA" in c or "SWOP" in c]
        self.assertTrue(press, "no press profile is offered")
        self.assertTrue(
            min(press) < min(generic), "generic profile is tried before a press one"
        )


class GsCommandTests(unittest.TestCase):
    """The flags that decide whether the output separates correctly."""

    def _command(self, **kwargs) -> list[str]:
        defaults = {"preserve_k": True, "lossless": False}
        defaults.update(kwargs)
        return cmyk_export.gs_command(
            Path("/in.pdf"), Path("/out-cmyk.pdf"), None, **defaults
        )

    def test_colour_flags_follow_the_prepress_preset(self) -> None:
        """/prepress sets LeaveColorUnchanged, so CMYK must be stated after it."""
        command = self._command()
        self.assertLess(
            command.index("-dPDFSETTINGS=/prepress"),
            command.index("-sColorConversionStrategy=CMYK"),
        )

    def test_marked_content_is_preserved(self) -> None:
        """Without this the recoverable Arabic is rebuilt away by pdfwrite."""
        self.assertIn("-dPreserveMarkedContent=true", self._command())

    def test_black_preservation_is_optional_but_on_by_default(self) -> None:
        self.assertIn("-dKPreserve=2", self._command())
        self.assertNotIn("-dKPreserve=2", self._command(preserve_k=False))

    def test_an_icc_profile_is_granted_read_access_under_safer(self) -> None:
        icc = Path("/profiles/CoatedFOGRA39.icc")
        command = cmyk_export.gs_command(
            Path("/in.pdf"),
            Path("/out-cmyk.pdf"),
            icc,
            preserve_k=True,
            lossless=False,
        )
        self.assertIn(f"--permit-file-read={icc}", command)
        self.assertIn(f"-sOutputICCProfile={icc}", command)


class ProofTests(unittest.TestCase):
    """What blocks an export versus what is merely reported."""

    BEFORE = {
        "pageCount": 3,
        "colorSpaces": {"/DeviceRGB": 3},
        "rgbPages": [1, 2, 3],
        "minDpi": 400,
        "textLayerPages": 3,
    }

    def _proof(self, after: dict, min_dpi: int = 300) -> dict:
        original = cmyk_export.inspect
        cmyk_export.inspect = lambda _path: after
        try:
            return cmyk_export.proof(self.BEFORE, Path("/out-cmyk.pdf"), min_dpi=min_dpi)
        finally:
            cmyk_export.inspect = original

    def _clean(self, **overrides) -> dict:
        after = {
            "pageCount": 3,
            "colorSpaces": {"/DeviceCMYK": 3},
            "rgbPages": [],
            "minDpi": 400,
            "textLayerPages": 3,
        }
        after.update(overrides)
        return after

    def test_a_fully_converted_file_is_press_ready(self) -> None:
        report = self._proof(self._clean())
        self.assertTrue(report["pressReady"])
        self.assertEqual([], report["problems"])
        self.assertEqual([], report["warnings"])

    def test_a_leftover_rgb_page_blocks_the_export(self) -> None:
        report = self._proof(self._clean(rgbPages=[2], colorSpaces={"/DeviceCMYK": 3, "/DeviceRGB": 1}))
        self.assertFalse(report["pressReady"])
        self.assertIn("DeviceRGB", report["problems"][0])

    def test_a_lost_page_blocks_the_export(self) -> None:
        report = self._proof(self._clean(pageCount=2))
        self.assertFalse(report["pressReady"])
        self.assertIn("page count changed", report["problems"][0])

    def test_low_resolution_is_a_warning_not_a_block(self) -> None:
        """Colour conversion cannot add detail — it is a fact about the art."""
        report = self._proof(self._clean(minDpi=124))
        self.assertTrue(report["pressReady"])
        self.assertIn("124 dpi", report["warnings"][0])

    def test_losing_the_text_layer_is_reported(self) -> None:
        report = self._proof(self._clean(textLayerPages=0))
        self.assertTrue(report["pressReady"])
        self.assertIn("text layer", report["warnings"][0])


def has_pil_and_profile() -> bool:
    try:
        from PIL import Image, ImageCms  # noqa: F401
    except ImportError:
        return False
    return cmyk_export.resolve_icc(None) is not None


@unittest.skipUnless(has_pil_and_profile(), "Pillow or a CMYK ICC profile missing")
class ImageConversionTests(unittest.TestCase):
    """One illustration into a press file, and what it reports about the ink."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.icc = cmyk_export.resolve_icc(None)

    def _image(self, colour=(190, 80, 60)) -> Path:
        from PIL import Image

        path = self.dir / "page.png"
        Image.new("RGB", (64, 48), colour).save(path)
        return path

    def test_it_writes_a_cmyk_tiff_and_a_viewable_proof(self) -> None:
        from PIL import Image

        result = cmyk_export.convert_image(self._image(), icc=self.icc)
        tiff = Path(result["cmykImage"])
        self.assertTrue(tiff.name.endswith("-cmyk.tif"))
        with Image.open(tiff) as opened:
            self.assertEqual("CMYK", opened.mode)
            self.assertTrue(opened.info.get("icc_profile"), "profile not embedded")
        proof = Path(result["proofImage"])
        with Image.open(proof) as opened:
            self.assertEqual("RGB", opened.mode)

    def test_ink_coverage_is_reported_against_the_profile_limit(self) -> None:
        result = cmyk_export.convert_image(self._image(), icc=self.icc)
        self.assertGreater(result["maxTacPercent"], 0)
        self.assertLessEqual(result["maxTacPercent"], 400)
        self.assertGreaterEqual(result["maxTacPercent"], result["meanTacPercent"])
        self.assertIsInstance(result["tacLimit"], int)

    def test_paper_white_asks_for_almost_no_ink(self) -> None:
        result = cmyk_export.convert_image(self._image((255, 255, 255)), icc=self.icc)
        self.assertLess(result["meanTacPercent"], 10)

    def test_rich_dark_asks_for_a_lot_of_ink(self) -> None:
        result = cmyk_export.convert_image(self._image((8, 8, 10)), icc=self.icc)
        self.assertGreater(result["meanTacPercent"], 200)

    def test_an_unknown_intent_names_the_valid_ones(self) -> None:
        with self.assertRaises(cmyk_export.CmykError) as caught:
            cmyk_export.convert_image(self._image(), icc=self.icc, intent="cinematic")
        self.assertIn("perceptual", str(caught.exception))

    def test_conversion_without_a_profile_is_refused(self) -> None:
        with self.assertRaises(cmyk_export.CmykError) as caught:
            cmyk_export.convert_image(self._image(), icc=None)
        self.assertIn("--icc", str(caught.exception))

    def test_baked_in_text_is_reported_as_a_prepress_problem(self) -> None:
        """Handoff §9 P8 cannot be met once the Arabic is pixels — say so."""
        result = cmyk_export.convert_image(self._image(), icc=self.icc)
        self.assertTrue(
            any("K-only" in warning for warning in result["warnings"]),
            "the rich-black warning is missing",
        )

    def test_there_is_no_per_pixel_k_only_knob(self) -> None:
        """It cannot tell text from dark art, and it shredded real denim."""
        self.assertFalse(hasattr(cmyk_export, "apply_k_only"))


@unittest.skipUnless(has_deps(), "ghostscript / reportlab / pypdf not installed")
class EndToEndTests(unittest.TestCase):
    """A real RGB PDF through a real Ghostscript pass."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.source = self.dir / "draft.pdf"
        self._write_rgb_pdf(self.source, pages=2)

    def _write_rgb_pdf(self, path: Path, *, pages: int) -> None:
        from PIL import Image
        from reportlab.pdfgen import canvas

        image = self.dir / "page.png"
        Image.new("RGB", (240, 160), (200, 90, 60)).save(image)
        pdf = canvas.Canvas(str(path), pagesize=(240, 160))
        for _ in range(pages):
            pdf.drawImage(str(image), 0, 0, width=240, height=160)
            pdf.showPage()
        pdf.save()

    def test_the_source_is_rgb_and_the_export_is_cmyk(self) -> None:
        before = cmyk_export.inspect(self.source)
        self.assertIn("/DeviceRGB", before["colorSpaces"])

        result = cmyk_export.export(self.source, icc=None, min_dpi=1)

        destination = Path(result["cmykPdf"])
        self.assertTrue(destination.is_file())
        self.assertTrue(destination.name.endswith("-cmyk.pdf"))
        self.assertEqual([], result["after"]["rgbPages"])
        self.assertIn("/DeviceCMYK", result["after"]["colorSpaces"])
        self.assertTrue(result["pressReady"])

    def test_it_refuses_to_silently_replace_an_existing_export(self) -> None:
        cmyk_export.export(self.source, icc=None, min_dpi=1)
        with self.assertRaises(cmyk_export.CmykError) as caught:
            cmyk_export.export(self.source, icc=None, min_dpi=1)
        self.assertIn("--force", str(caught.exception))
        cmyk_export.export(self.source, icc=None, min_dpi=1, force=True)

    def test_a_failed_conversion_leaves_no_cmyk_file_behind(self) -> None:
        """A half-written `-cmyk.pdf` is the one that reaches a press unnoticed."""
        broken = self.dir / "broken.pdf"
        broken.write_bytes(b"not a pdf at all")
        with self.assertRaises(cmyk_export.CmykError):
            cmyk_export.export(broken, icc=None, min_dpi=1)
        self.assertFalse((self.dir / "broken-cmyk.pdf").exists())


if __name__ == "__main__":
    unittest.main()
