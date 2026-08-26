#!/usr/bin/env python3
"""Caption geometry + Arabic shaping for the book's text layer.

Illustrations are generated **text-free** with a calm "safe zone" at the bottom
of the frame, and the story text is drawn afterwards as a real text layer — a
selectable, editable PDF text stream, and an editable box in the Canva/PPTX
export. This module owns everything about that layer except the actual drawing
call, so the PDF builder and the deck exporter place the caption identically.

It is pure and dependency-light on purpose: no image or PDF library is imported
here, so the geometry is unit-testable on its own. Callers supply a measuring
function that knows their font metrics.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Sequence

# Caption band as fractions of the full page, origin BOTTOM-LEFT (reportlab
# convention). A bottom band is the storybook norm; the illustration prompt is
# told to keep this region low-detail so overlaid text stays legible. The Canva
# export converts these to its top-left fractional coordinates.
SAFE_ZONE = {
    "marginX": 0.06,   # left/right inset
    "marginBottom": 0.05,
    "height": 0.24,    # band height
}
# What the illustration prompt promises to keep clear. Slightly taller than the
# band so text never crowds busy art right at the band's top edge.
SAFE_ZONE_PROMPT_FRACTION = 0.32

# Type size search bounds, in points, for a caption that must fit the band.
MAX_FONT_PT = 34.0
MIN_FONT_PT = 12.0
FONT_STEP_PT = 0.5
# Line spacing and the inset that keeps glyphs off the band's own edges.
LEADING_RATIO = 1.55
PADDING_RATIO = 0.12

# Env / settings keys for the Arabic display font (an OFL .ttf the user supplies;
# we never auto-download one).
FONT_ENV_VAR = "HEKAYATI_ARABIC_FONT"
BUNDLED_FONT_DIR = Path(__file__).resolve().parents[1] / "references" / "fonts"

# A measuring callback: (text, fontSize) -> width in the caller's page units.
Measure = Callable[[str, float], float]


class TextLayoutError(Exception):
    """The caption could not be laid out (missing font, missing dep, no fit)."""


@dataclass(frozen=True)
class SafeZone:
    """Caption band rectangle in absolute page units (origin bottom-left)."""

    x: float
    y: float
    width: float
    height: float

    @property
    def top(self) -> float:
        return self.y + self.height


@dataclass(frozen=True)
class CaptionLine:
    """One laid-out line.

    ``shaped`` is what gets drawn (visually ordered, contextually shaped);
    ``logical`` is the original Arabic, which the PDF carries as /ActualText so
    copy and text-extraction return real Arabic instead of presentation forms.
    """

    logical: str
    shaped: str
    x: float
    baseline: float


@dataclass(frozen=True)
class CaptionLayout:
    font_size: float
    leading: float
    lines: tuple[CaptionLine, ...]

    @property
    def logical_text(self) -> str:
        return " ".join(line.logical for line in self.lines)


def safe_zone_rect(page_width: float, page_height: float) -> SafeZone:
    """Absolute caption-band rectangle for a page of the given size.

    reportlab points, PPTX EMUs, or any linear unit — the fractions are unitless,
    so callers pass whatever page units they work in.
    """
    if page_width <= 0 or page_height <= 0:
        raise TextLayoutError(f"page size must be positive: {page_width}x{page_height}")
    margin_x = SAFE_ZONE["marginX"] * page_width
    height = SAFE_ZONE["height"] * page_height
    y = SAFE_ZONE["marginBottom"] * page_height
    width = page_width - 2 * margin_x
    return SafeZone(x=margin_x, y=y, width=width, height=height)


def safe_zone_norm_topleft() -> dict[str, float]:
    """Caption band as top-left fractional coords (Canva / PPTX convention).

    x/y/width/height in [0,1] of the page, y measured from the TOP.
    """
    width = 1.0 - 2 * SAFE_ZONE["marginX"]
    height = SAFE_ZONE["height"]
    # bottom-left y=marginBottom → top-left y = 1 - marginBottom - height
    y_top = 1.0 - SAFE_ZONE["marginBottom"] - height
    return {
        "x": SAFE_ZONE["marginX"],
        "y": y_top,
        "width": width,
        "height": height,
    }


def safe_zone_prompt_clause() -> str:
    """Instruction fragment telling the image model to keep the band clear."""
    pct = round(SAFE_ZONE_PROMPT_FRACTION * 100)
    return (
        f"Render NO text, letters, numbers, captions, or signage anywhere in the "
        f"image. Keep the bottom {pct}% of the frame a calm, low-detail zone "
        f"(soft, uncluttered, no faces/hands/key action there) so a caption can be "
        f"placed over it later. Do not draw a box, band, or panel — just keep that "
        f"area visually quiet."
    )


def resolve_arabic_font(settings: dict[str, Any] | None = None) -> Path:
    """Locate an Arabic display .ttf.

    Order: settings.textFont → $HEKAYATI_ARABIC_FONT → a .ttf bundled under
    references/fonts/. We never download one; raise a clear, actionable error.
    """
    candidates: list[Path] = []
    if settings:
        raw = settings.get("textFont")
        if isinstance(raw, str) and raw.strip():
            candidates.append(Path(raw.strip()).expanduser())
    env = os.environ.get(FONT_ENV_VAR)
    if env and env.strip():
        candidates.append(Path(env.strip()).expanduser())
    if BUNDLED_FONT_DIR.is_dir():
        candidates.extend(sorted(BUNDLED_FONT_DIR.glob("*.ttf")))
    for path in candidates:
        if path.is_file():
            return path.resolve()
    raise TextLayoutError(
        "No Arabic overlay font found. Provide an OFL .ttf via settings.textFont, "
        f"the {FONT_ENV_VAR} env var, or drop one into "
        f"{BUNDLED_FONT_DIR} (e.g. Cairo-Regular.ttf or Amiri-Regular.ttf)."
    )


@lru_cache(maxsize=1)
def _reshaper() -> Any:
    """The shared reshaper, configured for real-world font coverage.

    ``use_unshaped_instead_of_isolated`` matters: shaping maps every letter to a
    Presentation Forms-B codepoint, but modern OFL fonts do contextual shaping
    through OpenType and carry only part of that legacy block. Cairo, for one,
    has 89 of 144 — the gaps are the *isolated* forms of the non-joining letters
    (ا ة ر و), which is exactly what a standalone word like ``سارة`` ends on.
    Those dropped out of the PDF as blank boxes.

    An isolated non-joining letter is visually identical to its plain form, so
    emitting the plain letter there costs nothing and is covered by every
    Arabic font.
    """
    try:
        from arabic_reshaper import ArabicReshaper  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised via requirements
        raise TextLayoutError(
            "Arabic shaping needs arabic-reshaper and python-bidi: "
            "python3 -m pip install -r tools/requirements.txt"
        ) from exc
    return ArabicReshaper(configuration={"use_unshaped_instead_of_isolated": True})


@lru_cache(maxsize=4096)
def shape_arabic(text: str) -> str:
    """Reshape + bidi-order Arabic so a non-shaping renderer draws it correctly.

    reportlab and python-pptx do not do Arabic contextual shaping or bidi on
    their own, so glyphs would render isolated and left-to-right. This returns
    the visually-ordered, contextually-shaped string.

    Cached: the type-size search reshapes the same words once per candidate
    size, and shaping is the expensive part of laying a caption out.
    """
    if not text:
        return ""
    try:
        from bidi.algorithm import get_display  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised via requirements
        raise TextLayoutError(
            "Arabic shaping needs arabic-reshaper and python-bidi: "
            "python3 -m pip install -r tools/requirements.txt"
        ) from exc
    return get_display(_reshaper().reshape(text))


def missing_glyphs(shaped: str, covered: Callable[[str], bool]) -> list[str]:
    """Characters in a shaped run that the caption font cannot draw.

    A font missing a glyph renders a blank box, and the page still builds — so
    this is checked before drawing rather than discovered in a printed book.
    """
    return sorted({ch for ch in shaped if ch.strip() and not covered(ch)})


def wrap_words(
    words: Sequence[str],
    measure: Measure,
    font_size: float,
    max_width: float,
) -> list[str] | None:
    """Greedy word wrap in *logical* order.

    Returns ``None`` when a single word cannot fit ``max_width`` at this size,
    which tells the caller to try a smaller one. Arabic words never join across
    a space, so measuring word by word is safe.
    """
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        if measure(shape_arabic(word), font_size) > max_width:
            return None
        candidate = current + [word]
        if measure(shape_arabic(" ".join(candidate)), font_size) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(" ".join(current))
        current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def layout_caption(text: str, zone: SafeZone, measure: Measure) -> CaptionLayout:
    """Fit ``text`` into ``zone``, right-aligned, at the largest size that fits.

    Searches type sizes downward so short captions read large and long ones
    still land inside the band the illustration was told to keep clear.
    """
    words = str(text or "").split()
    if not words:
        raise TextLayoutError("Cannot lay out an empty caption")
    padding = zone.height * PADDING_RATIO
    usable_width = zone.width - 2 * padding
    usable_height = zone.height - 2 * padding
    if usable_width <= 0 or usable_height <= 0:
        raise TextLayoutError(f"Caption band is too small to hold text: {zone}")

    size = MAX_FONT_PT
    while size >= MIN_FONT_PT:
        lines = wrap_words(words, measure, size, usable_width)
        leading = size * LEADING_RATIO
        if lines is not None and len(lines) * leading <= usable_height:
            return _place(lines, size, leading, zone, padding, measure)
        size -= FONT_STEP_PT

    raise TextLayoutError(
        f"Caption does not fit the safe zone even at {MIN_FONT_PT}pt "
        f"({len(words)} words). Shorten the page text — the age profile's word "
        "budget exists for exactly this reason."
    )


def _place(
    lines: list[str],
    font_size: float,
    leading: float,
    zone: SafeZone,
    padding: float,
    measure: Measure,
) -> CaptionLayout:
    """Right-align the wrapped lines and centre the block vertically."""
    block_height = len(lines) * leading
    # Baseline of the first line, measured down from the block's top edge.
    top = zone.y + (zone.height + block_height) / 2 - leading + font_size * 0.25
    right_edge = zone.x + zone.width - padding
    placed: list[CaptionLine] = []
    for index, logical in enumerate(lines):
        shaped = shape_arabic(logical)
        width = measure(shaped, font_size)
        placed.append(
            CaptionLine(
                logical=logical,
                shaped=shaped,
                x=right_edge - width,
                baseline=top - index * leading,
            )
        )
    return CaptionLayout(font_size=font_size, leading=leading, lines=tuple(placed))
