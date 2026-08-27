#!/usr/bin/env python3
"""Final print step: convert a built book PDF to DeviceCMYK.

Everything upstream works in RGB — the illustrations come back RGB, and the
Arabic is composed into them as RGB pixels. A press wants CMYK separations, so
the last thing that happens to a finished book is this: one pass that rewrites
every colour into DeviceCMYK, and one pass that *checks* it actually happened.

The output is always named ``<stem>-cmyk.pdf`` so the converted file is
impossible to confuse with the RGB original at the print shop.

Conversion runs through Ghostscript, which rewrites colour operators and image
colour spaces in place — the page images stay images and the invisible Arabic
text layer stays text, so copy, search and accessibility survive the trip.

Usage
-----
    python3 cmyk_export.py --project /path/to/client --edition final
    python3 cmyk_export.py --pdf /path/to/draft.pdf
    python3 cmyk_export.py --project /path/to/client --icc "/path/Coated FOGRA39.icc"
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

try:  # Pillow is only needed for the single-image path
    from PIL import Image
except ImportError:  # pragma: no cover - reported by doctor
    Image = None  # type: ignore[assignment]

# macOS ships one; a press-supplied profile (Coated FOGRA39, US Web Coated
# SWOP) is better and can be passed with --icc.
ADOBE_PROFILE_DIR = "/Library/Application Support/Adobe/Color/Profiles/Recommended"
DEFAULT_ICC_CANDIDATES = (
    # A real press profile first — these ship with any Adobe install and are what
    # an Egyptian coated-stock job is actually separated for.
    f"{ADOBE_PROFILE_DIR}/CoatedFOGRA39.icc",
    f"{ADOBE_PROFILE_DIR}/USWebCoatedSWOP.icc",
    "/usr/share/color/icc/ISOcoated_v2_eci.icc",
    # Generic is the fallback of last resort: it converts, but no press tuned it.
    "/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc",
)
CMYK_SUFFIX = "-cmyk.pdf"
# Ghostscript writes a fresh file; refuse to clobber a previous export by default.
GS_TIMEOUT_SEC = 3600


class CmykError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Locating the source PDF
# ---------------------------------------------------------------------------


def pdf_from_project(project: Path, edition: str) -> Path:
    """The built PDF a project's book.json points at for this edition."""
    book_path = project / "output" / "book.json"
    if not book_path.is_file():
        raise CmykError(f"No book.json under {project} — pass --pdf instead")
    try:
        book = json.loads(book_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CmykError(f"Cannot read {book_path}: {exc}") from exc
    entry = (book.get("pdf") or {}).get(edition) or {}
    relative = str(entry.get("path") or "").strip()
    if not relative:
        raise CmykError(
            f"book.json has no {edition} PDF yet. Build and verify it first, "
            "then run this export."
        )
    path = project / relative
    if not path.is_file():
        raise CmykError(f"book.json points at a missing PDF: {path}")
    if entry.get("status") not in {"built", "verified"}:
        raise CmykError(
            f"{edition} PDF status is {entry.get('status')!r}; build and verify "
            "it before exporting for print."
        )
    return path


def resolve_icc(explicit: str | None) -> Path | None:
    """The CMYK output profile, or None to let Ghostscript use its default."""
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise CmykError(f"ICC profile not found: {path}")
        return path.resolve()
    for candidate in DEFAULT_ICC_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def ghostscript() -> str:
    for name in ("gs", "gswin64c", "gswin32c"):
        found = shutil.which(name)
        if found:
            return found
    raise CmykError(
        "Ghostscript is required for CMYK conversion and was not found.\n"
        "  macOS:  brew install ghostscript\n"
        "  Debian: sudo apt install ghostscript"
    )


def gs_command(
    source: Path,
    destination: Path,
    icc: Path | None,
    *,
    preserve_k: bool,
    lossless: bool,
) -> list[str]:
    """Ghostscript invocation for a press-ready CMYK rewrite.

    ``/prepress`` sets the quality floor (300dpi, no aggressive downsampling)
    but also sets ColorConversionStrategy=LeaveColorUnchanged, so every colour
    flag has to come *after* it to win.
    """
    command = [
        ghostscript(),
        "-dBATCH",
        "-dNOPAUSE",
        "-dSAFER",
        "-sDEVICE=pdfwrite",
        "-dPDFSETTINGS=/prepress",
        # Colour: rewrite everything into DeviceCMYK.
        "-dProcessColorModel=/DeviceCMYK",
        "-sColorConversionStrategy=CMYK",
        # Keep the page images at full fidelity — this is the print master.
        "-dAutoRotatePages=/None",
        "-dDownsampleColorImages=false",
        "-dDownsampleGrayImages=false",
        "-dDownsampleMonoImages=false",
        # Embed everything the press needs.
        "-dEmbedAllFonts=true",
        "-dSubsetFonts=true",
        # Keep the BDC/EMC spans that carry the logical Arabic. Without this,
        # pdfwrite rebuilds every content stream and the recoverable text is
        # gone; with it, the /ActualText moves into the page's /Properties
        # resource and survives (see ``_actual_text``).
        "-dPreserveMarkedContent=true",
    ]
    if lossless:
        # pdfwrite re-encodes images as JPEG by default. For a print master that
        # is usually fine, but a page that has already been through one lossy
        # generation should not take a second one.
        command += [
            "-dAutoFilterColorImages=false",
            "-dAutoFilterGrayImages=false",
            "-sColorImageFilter=FlateEncode",
            "-sGrayImageFilter=FlateEncode",
        ]
    if preserve_k:
        # Black preservation across the ICC link: greys and near-blacks come out
        # on the K plate instead of as four-colour rich black. This is what keeps
        # the Arabic composed into the art from separating into a registration
        # nightmare (handoff §9 P8).
        command += ["-dKPreserve=2", "-dBlackPtComp=1"]
    if icc is not None:
        # -dSAFER (on by default in Ghostscript 10) refuses to read anything
        # outside the input's own directory, and the ICC profile lives in the
        # system colour folder. Grant exactly that one file, nothing wider.
        command += [
            f"--permit-file-read={icc}",
            "-dOverrideICC=true",
            f"-sOutputICCProfile={icc}",
        ]
    command += ["-o", str(destination), str(source)]
    return command


def convert(
    source: Path,
    destination: Path,
    icc: Path | None,
    *,
    preserve_k: bool,
    lossless: bool,
) -> None:
    command = gs_command(
        source, destination, icc, preserve_k=preserve_k, lossless=lossless
    )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=GS_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CmykError(f"Ghostscript timed out after {GS_TIMEOUT_SEC}s") from exc
    if result.returncode != 0 or not destination.is_file():
        # Ghostscript often leaves a truncated file behind when it dies partway.
        # A half-written "-cmyk.pdf" is exactly the thing that reaches a press
        # unnoticed, so it does not get to survive a failed run.
        destination.unlink(missing_ok=True)
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-12:]
        raise CmykError(
            "Ghostscript failed to write the CMYK PDF:\n" + "\n".join(tail)
        )


# ---------------------------------------------------------------------------
# Proof — did it actually convert?
# ---------------------------------------------------------------------------


def _colour_space_names(value: Any, seen: set[int] | None = None) -> Iterable[str]:
    """Every colour-space name reachable from a /ColorSpace entry."""
    seen = seen if seen is not None else set()
    try:
        obj = value.get_object()
    except AttributeError:
        obj = value
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _colour_space_names(item, seen)
        return
    name = str(obj)
    if name.startswith("/"):
        yield name


def inspect(path: Path) -> dict[str, Any]:
    """What the finished file actually contains: colour, resolution, text.

    Three things decide whether a book file is press-ready, and none of them are
    visible by looking at the page: the colour space, the effective resolution
    of the full-bleed image once it is scaled onto the page, and whether the
    recoverable Arabic survived whatever tool touched the file last.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - exercised via requirements
        raise CmykError(
            "pypdf is required to verify the export: "
            "python3 -m pip install -r tools/requirements.txt"
        ) from exc

    try:
        reader = PdfReader(str(path))
        page_count = len(reader.pages)
    except Exception as exc:
        raise CmykError(f"Cannot read PDF {path.name}: {exc}") from exc
    spaces: dict[str, int] = {}
    rgb_pages: list[int] = []
    dpi_by_page: dict[int, int] = {}
    text_pages: list[int] = []
    for index, page in enumerate(reader.pages, start=1):
        if _actual_text(page).strip():
            text_pages.append(index)
        resources = page.get("/Resources")
        if resources is None:
            continue
        resources = resources.get_object()
        page_spaces: set[str] = set()
        widest = 0
        for entry in (resources.get("/XObject"), resources.get("/ColorSpace")):
            if entry is None:
                continue
            for value in entry.get_object().values():
                obj = value.get_object()
                target = obj.get("/ColorSpace") if hasattr(obj, "get") else None
                page_spaces.update(
                    _colour_space_names(target if target is not None else obj)
                )
                if hasattr(obj, "get") and obj.get("/Subtype") == "/Image":
                    widest = max(widest, int(obj.get("/Width") or 0))
        for name in page_spaces:
            spaces[name] = spaces.get(name, 0) + 1
        if "/DeviceRGB" in page_spaces:
            rgb_pages.append(index)
        page_inches = float(page.mediabox.width) / 72.0
        if widest and page_inches > 0:
            dpi_by_page[index] = round(widest / page_inches)
    return {
        "pageCount": page_count,
        "colorSpaces": dict(sorted(spaces.items())),
        "rgbPages": rgb_pages,
        "minDpi": min(dpi_by_page.values()) if dpi_by_page else None,
        "textLayerPages": len(text_pages),
    }


ACTUAL_TEXT_SPAN = re.compile(rb"/ActualText\s*<([0-9A-Fa-f]+)>")


def _actual_text(page: Any) -> str:
    """Logical Arabic recovered from a page, in either of the two shapes it takes.

    reportlab writes the span inline in the content stream as
    ``/Span << /ActualText <FEFF…> >> BDC``. Ghostscript keeps the span but
    lifts the dictionary out into ``/Resources /Properties``, leaving a named
    reference behind. Both are the same text; only the storage differs, so a
    check that knows one shape reports a converted file as having lost its text.
    """
    out: list[str] = []
    try:
        raw = page.get_contents().get_data()
    except Exception:  # pragma: no cover - a page with no content stream
        raw = b""
    for match in ACTUAL_TEXT_SPAN.finditer(raw):
        try:
            decoded = bytes.fromhex(match.group(1).decode("ascii"))
        except ValueError:
            continue
        if decoded[:2] == b"\xfe\xff":
            decoded = decoded[2:]
        out.append(decoded.decode("utf-16-be", errors="ignore"))
    out.extend(_properties_actual_text(page))
    return " ".join(part for part in out if part)


def _properties_actual_text(page: Any) -> list[str]:
    """/ActualText values parked in the page's /Properties resource dictionary."""
    try:
        resources = page.get("/Resources")
        properties = resources.get_object().get("/Properties") if resources else None
        if properties is None:
            return []
        found: list[str] = []
        for value in properties.get_object().values():
            entry = value.get_object()
            text = entry.get("/ActualText") if hasattr(entry, "get") else None
            if text:
                found.append(str(text))
        return found
    except Exception:  # pragma: no cover - malformed resource tree
        return []


def proof(before: dict[str, Any], destination: Path, *, min_dpi: int) -> dict[str, Any]:
    """Compare source and output, and decide whether the export is press-ready.

    ``problems`` block the export — the file is deleted rather than handed to a
    press. ``warnings`` are reported and kept: they are real, but they are facts
    about the source book that a colour conversion cannot fix.
    """
    after = inspect(destination)
    problems: list[str] = []
    warnings: list[str] = []

    if after["pageCount"] != before["pageCount"]:
        problems.append(
            f"page count changed: {before['pageCount']} → {after['pageCount']}"
        )
    if after["rgbPages"]:
        shown = ", ".join(str(n) for n in after["rgbPages"][:10])
        problems.append(f"{len(after['rgbPages'])} page(s) still DeviceRGB: {shown}")
    if "/DeviceCMYK" not in after["colorSpaces"]:
        problems.append("no DeviceCMYK colour space found in the output")

    if after["minDpi"] is not None and after["minDpi"] < min_dpi:
        warnings.append(
            f"lowest effective resolution is {after['minDpi']} dpi, below the "
            f"{min_dpi} dpi print target — regenerate the page art larger; a "
            "colour conversion cannot add detail"
        )
    if before["textLayerPages"] and not after["textLayerPages"]:
        warnings.append(
            f"the invisible Arabic text layer ({before['textLayerPages']} pages) "
            "did not survive conversion — Ghostscript rebuilds content streams "
            "and drops it. The visible Arabic is inside the art, so the printed "
            "book is unaffected, but this file will not copy, search, or pass "
            "`verify`. Keep the RGB original as the archive master"
        )
    return {
        "before": before,
        "after": after,
        "problems": problems,
        "warnings": warnings,
        "pressReady": not problems,
    }


# ---------------------------------------------------------------------------
# Single-image conversion
# ---------------------------------------------------------------------------

# Pillow's rendering intents. Relative colorimetric with black point
# compensation is the safe default for illustration: it keeps in-gamut colour
# where it is and only moves what the press cannot print. Perceptual compresses
# the whole gamut instead, which protects gradients in very saturated art at the
# cost of shifting colours that would have printed fine.
INTENTS = {
    "perceptual": 0,
    "relative": 1,
    "saturation": 2,
    "absolute": 3,
}
# Ink limits the common profiles are built for, quoted in the report so a TAC
# number means something without looking it up.
PROFILE_TAC_HINTS = {
    "coatedfogra39": 330,
    "coatedfogra27": 350,
    "uswebcoatedswop": 300,
    "ussheetfedcoated": 350,
    "uncoatedfogra29": 300,
}


class ImageResult(dict):
    """A converted image plus what the press needs to know about it."""


# Why there is no per-pixel "K-only" option here, despite handoff §9 P8:
# once the Arabic is drawn inside the artwork it is just pixels, and printed
# black text is not distinguishable from dark art by pixel value. Measured on
# page-19 of this book: the text ink is rgb(30,35,38), the boy's denim is
# rgb(37,43,47) and his hair is rgb(27,21,17) — the hair is darker and more
# neutral than the jeans. Any threshold that catches the text also catches
# both, and moving those to K alone tears the denim into grey speckle.
#
# The lever that does work is the separation itself: ask the press for a
# profile built with heavy GCR/UCR and pass it with --icc. That pulls neutrals
# toward K smoothly across the whole image instead of per pixel. Genuinely
# K-only text needs the text to still be text at prepress, not baked pixels.


def ink_coverage(cmyk: Any) -> dict[str, Any]:
    """Total area coverage: how much ink the wettest pixel actually asks for.

    Summed in quarters because an 8-bit channel cannot hold 1020; the rounding
    costs under 1% TAC, which is far inside the tolerance any press quotes.
    """
    from PIL import ImageChops

    cyan, magenta, yellow, black = cmyk.split()
    quarter = ImageChops.add(
        ImageChops.add(cyan, magenta, scale=2),
        ImageChops.add(yellow, black, scale=2),
        scale=2,
    )
    histogram = quarter.histogram()
    pixels = sum(histogram) or 1
    def as_tac(value: int) -> float:
        return round(value * 4 / 255 * 100, 1)
    total = sum(value * count for value, count in enumerate(histogram))
    return {
        "maxTacPercent": as_tac(quarter.getextrema()[1]),
        "meanTacPercent": as_tac(total / pixels),
        "histogram": histogram,
        "pixels": pixels,
    }


def _over_limit(coverage: dict[str, Any], limit: int) -> float:
    """Share of the image asking for more ink than the limit allows."""
    cutoff = limit / 100 * 255 / 4
    over = sum(
        count
        for value, count in enumerate(coverage["histogram"])
        if value > cutoff
    )
    return round(over / coverage["pixels"] * 100, 2)


def profile_tac_limit(icc: Path | None) -> int | None:
    if icc is None:
        return None
    key = icc.stem.replace(" ", "").replace("_", "").casefold()
    return PROFILE_TAC_HINTS.get(key)


def convert_image(
    source: Path,
    *,
    icc: Path | None,
    intent: str = "relative",
    black_point_compensation: bool = True,
    tac_limit: int | None = None,
    proof: bool = True,
) -> ImageResult:
    """One RGB illustration into a CMYK print file, plus a viewable soft proof.

    The TIFF is what goes to the press: CMYK, lossless, ICC embedded. The proof
    PNG is that same separation converted back to screen colour, so the drop in
    saturation you see is the drop the press will actually print — looking at
    the original RGB tells you nothing about that.
    """
    from PIL import Image, ImageCms

    if icc is None:
        raise CmykError(
            "Image conversion needs a CMYK profile. Pass --icc, or install one "
            "of: " + ", ".join(Path(c).name for c in DEFAULT_ICC_CANDIDATES)
        )
    if intent not in INTENTS:
        raise CmykError(
            f"Unknown rendering intent {intent!r}; expected one of "
            + ", ".join(INTENTS)
        )
    if not source.is_file():
        raise CmykError(f"Image not found: {source}")

    rgb = Image.open(source).convert("RGB")
    source_profile = ImageCms.createProfile("sRGB")
    target_profile = ImageCms.getOpenProfile(str(icc))
    flags = 0
    if black_point_compensation:
        flags |= ImageCms.Flags.BLACKPOINTCOMPENSATION
    transform = ImageCms.buildTransform(
        source_profile,
        target_profile,
        "RGB",
        "CMYK",
        renderingIntent=INTENTS[intent],
        flags=flags,
    )
    cmyk = ImageCms.applyTransform(rgb, transform)

    coverage = ink_coverage(cmyk)
    limit = tac_limit or profile_tac_limit(icc) or 300
    destination = source.with_name(source.stem + "-cmyk.tif")
    cmyk.save(
        destination,
        compression="tiff_lzw",
        icc_profile=Path(icc).read_bytes(),
        dpi=rgb.info.get("dpi", (300, 300)),
    )

    proof_path = None
    if proof:
        back = ImageCms.buildTransform(
            target_profile,
            source_profile,
            "CMYK",
            "RGB",
            renderingIntent=INTENTS[intent],
            flags=flags,
        )
        proof_path = source.with_name(source.stem + "-cmyk-proof.png")
        ImageCms.applyTransform(cmyk, back).save(proof_path)

    warnings: list[str] = []
    over = _over_limit(coverage, limit)
    if over > 0.5:
        warnings.append(
            f"{over}% of the image exceeds {limit}% total ink (peak "
            f"{coverage['maxTacPercent']}%). Ask the press for their ink limit "
            "and separate with a profile built for it"
        )
    warnings.append(
        "the Arabic is baked into the artwork, so it separates as four-colour "
        "black like the rest of the picture. Handoff §9 P8 wants printed text "
        "K-only; that is a prepress conversation now, not something this "
        "conversion can recover"
    )
    return ImageResult(
        source=str(source),
        cmykImage=str(destination),
        proofImage=str(proof_path) if proof_path else None,
        size=list(rgb.size),
        iccProfile=str(icc),
        intent=intent,
        blackPointCompensation=black_point_compensation,
        maxTacPercent=coverage["maxTacPercent"],
        meanTacPercent=coverage["meanTacPercent"],
        tacLimit=limit,
        percentOverTacLimit=over,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def export(
    source: Path,
    *,
    icc: Path | None,
    preserve_k: bool = True,
    lossless: bool = False,
    min_dpi: int = 300,
    force: bool = False,
) -> dict[str, Any]:
    if not source.is_file():
        raise CmykError(f"Source PDF not found: {source}")
    destination = source.with_name(source.stem + CMYK_SUFFIX)
    if destination.exists() and not force:
        raise CmykError(
            f"CMYK export already exists: {destination}\nPass --force to replace it."
        )
    # Read the source before spending minutes in Ghostscript, and so a corrupt
    # input fails as a clear message instead of as a mystery halfway through.
    before = inspect(source)
    convert(source, destination, icc, preserve_k=preserve_k, lossless=lossless)
    try:
        report = proof(before, destination, min_dpi=min_dpi)
    except CmykError:
        destination.unlink(missing_ok=True)
        raise
    if not report["pressReady"]:
        # A file with "cmyk" in its name that is not actually CMYK is worse than
        # no file at all: it reaches the press unchecked.
        destination.unlink(missing_ok=True)
        raise CmykError(
            "CMYK export did not verify, so the file was removed:\n- "
            + "\n- ".join(report["problems"])
        )
    return {
        "source": str(source),
        "cmykPdf": str(destination),
        "sizeMb": round(destination.stat().st_size / (1024 * 1024), 1),
        "iccProfile": str(icc) if icc else "ghostscript default",
        "blackPreservation": preserve_k,
        "lossless": lossless,
        **report,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a built book PDF to DeviceCMYK for print."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--project", help="Client project folder (uses book.json)")
    source.add_argument("--pdf", help="Convert this PDF directly")
    source.add_argument("--image", help="Convert one illustration to a CMYK TIFF")
    parser.add_argument(
        "--edition",
        default="final",
        choices=("draft", "final"),
        help="Which built edition to convert when --project is used",
    )
    parser.add_argument("--icc", help="CMYK output ICC profile (press-supplied)")
    parser.add_argument(
        "--no-preserve-black",
        action="store_true",
        help="Allow near-black to separate as rich black instead of K-only",
    )
    parser.add_argument(
        "--lossless",
        action="store_true",
        help="Keep images Flate-encoded instead of re-encoding them as JPEG",
    )
    parser.add_argument(
        "--min-dpi",
        type=int,
        default=300,
        help="Warn when the effective page resolution falls below this (default 300)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Replace an existing CMYK export"
    )
    image = parser.add_argument_group("--image options")
    image.add_argument(
        "--intent",
        default="relative",
        choices=tuple(INTENTS),
        help="Rendering intent. 'relative' keeps in-gamut colour where it is; "
        "'perceptual' compresses the whole gamut and protects gradients in very "
        "saturated art (default: relative)",
    )
    image.add_argument(
        "--no-bpc",
        action="store_true",
        help="Turn off black point compensation (shadows will plug)",
    )
    image.add_argument(
        "--max-tac",
        type=int,
        help="Total ink limit to report against (default: the profile's own)",
    )
    image.add_argument(
        "--no-proof", action="store_true", help="Skip the sRGB soft-proof PNG"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.image:
            result = convert_image(
                Path(args.image).expanduser().resolve(),
                icc=resolve_icc(args.icc),
                intent=args.intent,
                black_point_compensation=not args.no_bpc,
                tac_limit=args.max_tac,
                proof=not args.no_proof,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            for warning in result.get("warnings") or []:
                print(f"warning: {warning}", file=sys.stderr)
            return 0
        if args.project:
            project = Path(args.project).expanduser()
            if not project.is_absolute():
                raise CmykError("--project must be an absolute path")
            source = pdf_from_project(project, args.edition)
        else:
            source = Path(args.pdf).expanduser().resolve()
        result = export(
            source,
            icc=resolve_icc(args.icc),
            preserve_k=not args.no_preserve_black,
            lossless=args.lossless,
            min_dpi=args.min_dpi,
            force=args.force,
        )
    except CmykError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    for warning in result.get("warnings") or []:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
