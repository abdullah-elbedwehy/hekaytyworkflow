#!/usr/bin/env python3
"""Measure whether a page is bright enough to print as a children's book.

This module measures. It does not edit the art, and that is a deliberate
reversal: an earlier version graded every render onto brightness targets, and
the numbers looked excellent — mean luminance 118 to 146, peak ink coverage 326%
down to 298%. The pictures did not. Lifting a warm, lamp-lit room pushed it
orange: on page-19 the Lab b* went from 25.6 to 40.0 and chroma rose 17 points.

The metric used to police that was mean hue, which reported under 1 degree of
drift and passed every page. It was blind by construction — hue is an *angle*,
and the cast did not rotate the colour, it doubled its magnitude. Switching off
the chroma restore did not save it either: raising L raises Lab chroma on its
own (+7.3 with chroma at 1.00), so no version of the grade left the model's
colour alone.

So the brightness fix lives at generation, where it belongs. The prompt asks for
open, daylit pages with coloured shadows, and night scenes in readable moonlit
blue-grey. This module tells you which pages did not come back that way, so they
can be regenerated rather than doctored.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from PIL import Image
except ImportError:  # pragma: no cover - reported by doctor
    Image = None  # type: ignore[assignment]


class ColorGradeError(RuntimeError):
    pass


# What a printed children's page should measure. These are the targets the
# grade solves for, not preferences applied by eye.
# What a printed children's page has to clear. Measured, not preferred: across
# this repo's books the median page arrived at mean luminance 115/255 with a
# fifth of its pixels below level 60, which prints heavy and muddy.
MIN_MEAN_LUMA = 105.0
MAX_SHADOW_PERCENT = 25.0
MIN_P05 = 20.0
SHADOW_FLOOR = 34.0        # darkest ink; below this a shadow prints as a hole
HIGHLIGHT_CEILING = 248.0  # keep a little off paper-white so highlights hold detail
CHROMA_RESTORE = 1.18      # lifting luminance flattens colour; put it back
# A page is "dark" below this; used for reporting, not for the maths.
SHADOW_LEVEL = 60


def _require_pillow() -> None:
    if Image is None:
        raise ColorGradeError(
            "Pillow is required: python3 -m pip install -r tools/requirements.txt"
        )


def _percentile(histogram: list[int], total: int, quantile: float) -> float:
    running = 0
    for value, count in enumerate(histogram):
        running += count
        if running >= total * quantile:
            return float(value)
    return 255.0


def analyze(image: Any) -> dict[str, float]:
    """What the page actually measures, before or after grading."""
    luma = image.convert("L")
    histogram = luma.histogram()
    total = sum(histogram) or 1
    mean = sum(value * count for value, count in enumerate(histogram)) / total
    shadow = sum(
        count for value, count in enumerate(histogram) if value < SHADOW_LEVEL
    )
    blown = sum(count for value, count in enumerate(histogram) if value >= 254)
    saturation = image.convert("HSV").split()[1]
    sat_hist = saturation.histogram()
    sat_mean = sum(v * c for v, c in enumerate(sat_hist)) / total
    return {
        "meanLuma": round(mean, 1),
        "p05": _percentile(histogram, total, 0.05),
        "median": _percentile(histogram, total, 0.50),
        "p95": _percentile(histogram, total, 0.95),
        "shadowPercent": round(shadow / total * 100, 1),
        "blownPercent": round(blown / total * 100, 2),
        "saturation": round(sat_mean, 1),
    }


def brightness_verdict(measured: dict[str, float]) -> dict[str, Any]:
    """Is this page bright enough to print, and if not, what is wrong with it?

    Deliberately not a single threshold. A night scene is *supposed* to sit
    darker than a picnic; what makes a page unprintable is not being dark but
    being heavy — a large share of it crushed into the bottom of the range,
    where ink piles up and detail disappears.
    """
    reasons: list[str] = []
    if measured["meanLuma"] < MIN_MEAN_LUMA:
        reasons.append(
            f"mean luminance {measured['meanLuma']} is below {MIN_MEAN_LUMA}"
        )
    if measured["shadowPercent"] > MAX_SHADOW_PERCENT:
        reasons.append(
            f"{measured['shadowPercent']}% of the page is in shadow "
            f"(limit {MAX_SHADOW_PERCENT}%)"
        )
    if measured["p05"] < MIN_P05:
        reasons.append(
            f"shadows are crushed: 5th percentile {measured['p05']} < {MIN_P05}"
        )
    return {"bright_enough": not reasons, "reasons": reasons}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure whether page art is bright enough to print."
    )
    parser.add_argument("--image", required=True, help="Page image to measure")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _require_pillow()
    source = Path(args.image).expanduser().resolve()
    if not source.is_file():
        print(f"error: image not found: {source}", file=sys.stderr)
        return 1
    measured = analyze(Image.open(source).convert("RGB"))
    verdict = brightness_verdict(measured)
    print(json.dumps({**measured, **verdict}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
