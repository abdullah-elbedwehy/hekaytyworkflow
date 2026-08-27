#!/usr/bin/env python3
"""Arabic shaping + font resolution for text that lives **inside** the art.

The book has no caption overlay: no bottom band, no scrim, no PDF text box
floating above the illustration. The image model draws each page's Arabic inside
the artwork itself, on the surface the prompt named.

Shaping is still needed twice. The PDF carries the same string invisibly, so
copy, search and ``verify`` keep working; and books authored before the change
still project their Arabic onto a planned carrier (see ``scene_text.py``). Both
need the same thing from here: locate the Arabic display font, and turn logical
Arabic into the visually-ordered, contextually-shaped string a non-shaping
renderer can actually draw.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

# Env / settings keys for the Arabic display font (an OFL .ttf the user supplies;
# we never auto-download one).
FONT_ENV_VAR = "HEKAYATI_ARABIC_FONT"
BUNDLED_FONT_DIR = Path(__file__).resolve().parents[1] / "references" / "fonts"


class TextLayoutError(Exception):
    """Text could not be prepared (missing font, missing dependency)."""


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
        "No Arabic font found. Provide an OFL .ttf via settings.textFont, "
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
    Those dropped out as blank boxes.

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

    Pillow and reportlab do not do Arabic contextual shaping or bidi on their
    own, so glyphs would render isolated and left-to-right. This returns the
    visually-ordered, contextually-shaped string.
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
    """Characters in a shaped run that the font cannot draw.

    A font missing a glyph renders a blank box and the page still builds — so
    this is checked before drawing rather than discovered in a printed book.
    """
    return sorted({ch for ch in shaped if ch.strip() and not covered(ch)})
