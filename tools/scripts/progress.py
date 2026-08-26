#!/usr/bin/env python3
"""Book completion percentage, phase, and ETA — derived from book.json alone.

The family sits through a run that takes tens of minutes and, until now, saw
nothing but a `nextAction` string. This module turns the manifest into a single
honest number so the agent can say "٦٢٪ — باقي ٨ صفحات، تقريبًا ١٢ دقيقة".

Two rules shape the weights below:

* They are **wall-clock** weights, not step counts. Writing the story is one
  command and 12% of the wait; rendering 22 interior pages is 35%. Weighting by
  command count made the bar sprint to 80% and then sit still for half an hour.
* A phase that does not apply to this book (a book with no location sheets)
  scores 1.0 rather than 0.0, so its weight is redistributed by completion
  instead of capping the book below 100%.

Pure and dependency-free on purpose: no I/O, no imports from story_pipeline, so
it is unit-testable against a hand-written dict and cannot deadlock the CLI.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any

COVER_ASSET_IDS = ("cover", "back-cover")
LOCATION_PREFIX = "location-sheet-"
CHARACTER_SHEET_ID = "character-sheet"

# Fallback when the book has rendered nothing yet and there is no measured
# duration to extrapolate from. Roughly one Codex page render on a warm machine.
ASSUMED_IMAGE_SEC = 150
# Non-image tail: build + verify + the four review passes.
PDF_BUILD_SEC = 45
REVIEW_PASS_SEC = 120
DEFAULT_WORKERS = 6

BAR_WIDTH = 24


@dataclass(frozen=True)
class Phase:
    key: str
    weight: int
    label_en: str
    label_ar: str


# Order is the order the user experiences them. Weights sum to 100.
PHASES: tuple[Phase, ...] = (
    Phase("setup", 3, "Setup and consent", "التجهيز والموافقة"),
    Phase("story", 12, "Writing and locking the story", "كتابة القصة وقفلها"),
    Phase("prompts", 10, "Writing image prompts", "كتابة أوصاف الرسم"),
    Phase("character_sheet", 7, "Character sheet", "ورقة الشخصيات"),
    Phase("location_sheets", 8, "Location sheets", "أوراق الأماكن"),
    Phase("interior", 35, "Story page illustrations", "رسم صفحات القصة"),
    Phase("covers", 5, "Covers", "الغلاف والغلاف الخلفي"),
    Phase("draft_pdf", 5, "Draft PDF", "نسخة PDF أولية"),
    Phase("review", 10, "Review and fixes", "المراجعة والتصحيح"),
    Phase("final_pdf", 5, "Final PDF", "النسخة النهائية"),
)
PHASE_BY_KEY = {phase.key: phase for phase in PHASES}
assert sum(p.weight for p in PHASES) == 100


def _assets(book: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in (book.get("assets") or []) if isinstance(a, dict)]


def _by_id(book: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {a["id"]: a for a in _assets(book) if isinstance(a.get("id"), str)}


def _group_ids(book: dict[str, Any]) -> dict[str, list[str]]:
    """Split this book's assets into the groups the progress bar tracks."""
    locations: list[str] = []
    interior: list[str] = []
    covers: list[str] = []
    for asset in _assets(book):
        asset_id = asset.get("id")
        if not isinstance(asset_id, str) or asset_id == CHARACTER_SHEET_ID:
            continue
        if asset_id.startswith(LOCATION_PREFIX):
            locations.append(asset_id)
        elif asset_id in COVER_ASSET_IDS:
            covers.append(asset_id)
        elif asset.get("includeInPdf"):
            interior.append(asset_id)
    return {"locations": locations, "interior": interior, "covers": covers}


def _rendered_fraction(book: dict[str, Any], ids: list[str]) -> float:
    """Share of a group that already has an image. Empty group counts as done."""
    if not ids:
        return 1.0
    index = _by_id(book)
    done = sum(1 for i in ids if (index.get(i) or {}).get("imagePath"))
    return done / len(ids)


def _pending(book: dict[str, Any], ids: list[str]) -> list[str]:
    index = _by_id(book)
    return [i for i in ids if not (index.get(i) or {}).get("imagePath")]


def _setup_fraction(book: dict[str, Any]) -> float:
    score = 1.0 / 3.0  # book.json exists at all, so init ran
    if book.get("storyGoal"):
        score += 1.0 / 3.0
    if (book.get("consent") or {}).get("confirmed"):
        score += 1.0 / 3.0
    return min(1.0, score)


def _story_fraction(book: dict[str, Any]) -> float:
    if book.get("storyPath"):
        return 1.0
    if book.get("templateSelection"):
        return 0.6
    if book.get("storyGoal"):
        return 0.2
    return 0.0


def _prompts_fraction(book: dict[str, Any]) -> float:
    """Prompts move planned → prompted only when validate-prompts passes.

    Counted per asset rather than as one boolean so a half-written prompts
    folder does not read as 0%; the agent writes them all in one pass but a
    failed validation leaves a mix.
    """
    assets = _assets(book)
    if not assets:
        return 0.0
    done = sum(1 for a in assets if a.get("status") not in {"planned", None})
    return done / len(assets)


def _character_sheet_fraction(book: dict[str, Any]) -> float:
    sheet = _by_id(book).get(CHARACTER_SHEET_ID) or {}
    if sheet.get("status") == "accepted":
        return 1.0
    if sheet.get("imagePath"):
        return 0.6  # rendered, waiting on the human accept gate
    return 0.0


def _pdf_fraction(book: dict[str, Any], edition: str) -> float:
    entry = (book.get("pdf") or {}).get(edition) or {}
    status = entry.get("status")
    if status == "verified":
        return 1.0
    if status == "built" or entry.get("path"):
        return 0.7
    return 0.0


def _review_fraction(book: dict[str, Any]) -> float:
    review = book.get("review") or {}
    status = review.get("status")
    if status in {"passed", "manual_review"}:
        return 1.0
    if status == "fixes_pending":
        # A review pass ran — real progress — but an open fix queue is not done,
        # and each fix costs another render. Credit the pass, not the queue.
        return 0.5
    if int(review.get("pass") or 0) > 0:
        return 0.4
    return 0.0


def phase_fractions(book: dict[str, Any]) -> dict[str, float]:
    """Completion 0..1 for every phase of this specific book."""
    groups = _group_ids(book)
    return {
        "setup": _setup_fraction(book),
        "story": _story_fraction(book),
        "prompts": _prompts_fraction(book),
        "character_sheet": _character_sheet_fraction(book),
        "location_sheets": _rendered_fraction(book, groups["locations"]),
        "interior": _rendered_fraction(book, groups["interior"]),
        "covers": _rendered_fraction(book, groups["covers"]),
        "draft_pdf": _pdf_fraction(book, "draft"),
        "review": _review_fraction(book),
        "final_pdf": _pdf_fraction(book, "final"),
    }


def current_phase(fractions: dict[str, float]) -> Phase:
    """First phase that is not finished — that is what the user is waiting on."""
    for phase in PHASES:
        if fractions.get(phase.key, 0.0) < 1.0:
            return phase
    return PHASES[-1]


def measured_image_seconds(book: dict[str, Any]) -> float | None:
    """Median render time of the assets this book already finished.

    Per-book rather than a global constant: a 4-persona page with five
    reference images costs several times a location sheet, and the family only
    cares about the machine in front of them.
    """
    durations = [
        float(a["durationSec"])
        for a in _assets(book)
        if isinstance(a.get("durationSec"), (int, float)) and a["durationSec"] > 0
    ]
    if not durations:
        return None
    return statistics.median(durations)


def eta_seconds(book: dict[str, Any], *, workers: int = DEFAULT_WORKERS) -> int | None:
    """Rough seconds of work left. None once nothing measurable remains."""
    groups = _group_ids(book)
    index = _by_id(book)
    sheet_pending = 0 if (index.get(CHARACTER_SHEET_ID) or {}).get("imagePath") else 1
    pending_images = (
        sheet_pending
        + len(_pending(book, groups["locations"]))
        + len(_pending(book, groups["interior"]))
        + len(_pending(book, groups["covers"]))
    )
    per_image = measured_image_seconds(book) or ASSUMED_IMAGE_SEC
    lanes = max(1, workers)
    # Jobs queue behind the worker pool, so the cost is rounds, not jobs.
    rounds = -(-pending_images // lanes)
    total = rounds * per_image

    fractions = phase_fractions(book)
    if fractions["draft_pdf"] < 1.0:
        total += PDF_BUILD_SEC
    if fractions["review"] < 1.0:
        total += REVIEW_PASS_SEC
    if fractions["final_pdf"] < 1.0:
        total += PDF_BUILD_SEC
    return int(total) if total > 0 else None


def render_bar(percent: int, width: int = BAR_WIDTH) -> str:
    filled = max(0, min(width, round(percent / 100 * width)))
    return "█" * filled + "░" * (width - filled)


# The Arabic message is pasted straight to the family, so its numerals are
# Arabic-Indic. The English message and every machine-read field stay Latin.
ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def ar_digits(text: str) -> str:
    return text.translate(ARABIC_INDIC)


def _duration_ar(seconds: int) -> str:
    minutes = max(1, round(seconds / 60))
    if minutes < 60:
        return ar_digits(f"حوالي {minutes} دقيقة")
    hours = minutes // 60
    rest = minutes % 60
    return ar_digits(f"حوالي {hours} ساعة" + (f" و{rest} دقيقة" if rest else ""))


def _duration_en(seconds: int) -> str:
    minutes = max(1, round(seconds / 60))
    if minutes < 60:
        return f"about {minutes} min"
    hours = minutes // 60
    rest = minutes % 60
    return f"about {hours}h" + (f" {rest}m" if rest else "")


def _phase_counter(book: dict[str, Any], phase: Phase) -> dict[str, Any]:
    """done/total for the phase the user is waiting on, when it is countable."""
    groups = _group_ids(book)
    index = _by_id(book)
    mapping = {
        "location_sheets": (groups["locations"], "location sheets", "أوراق أماكن"),
        "interior": (groups["interior"], "pages", "صفحة"),
        "covers": (groups["covers"], "covers", "غلاف"),
    }
    if phase.key in mapping:
        ids, unit_en, unit_ar = mapping[phase.key]
        done = sum(1 for i in ids if (index.get(i) or {}).get("imagePath"))
        return {"done": done, "total": len(ids), "unitEn": unit_en, "unitAr": unit_ar}
    if phase.key == "prompts":
        assets = _assets(book)
        done = sum(1 for a in assets if a.get("status") not in {"planned", None})
        return {
            "done": done,
            "total": len(assets),
            "unitEn": "prompts",
            "unitAr": "وصف رسم",
        }
    return {"done": None, "total": None, "unitEn": None, "unitAr": None}


def book_progress(
    book: dict[str, Any], *, workers: int = DEFAULT_WORKERS
) -> dict[str, Any]:
    """The block every command attaches to its JSON so the agent can report it.

    `messageAr` is written to be pasted straight to the family; the agent should
    not re-derive a percentage of its own.
    """
    fractions = phase_fractions(book)
    percent = int(
        round(sum(PHASE_BY_KEY[k].weight * v for k, v in fractions.items()))
    )
    percent = max(0, min(100, percent))
    phase = current_phase(fractions)
    counter = _phase_counter(book, phase)
    eta = eta_seconds(book, workers=workers)
    complete = percent >= 100

    if complete:
        message_ar = "١٠٠٪ — الكتاب خلص."
        message_en = "100% — book complete."
    else:
        piece_ar = f"{phase.label_ar}"
        if counter["total"]:
            piece_ar += ar_digits(
                f" ({counter['done']}/{counter['total']} {counter['unitAr']})"
            )
        message_ar = f"{ar_digits(str(percent))}٪ — {piece_ar}"
        if eta:
            message_ar += f" — باقي {_duration_ar(eta)}"
        piece_en = phase.label_en
        if counter["total"]:
            piece_en += f" ({counter['done']}/{counter['total']} {counter['unitEn']})"
        message_en = f"{percent}% — {piece_en}"
        if eta:
            message_en += f" — {_duration_en(eta)} left"

    return {
        "percent": percent,
        "bar": render_bar(percent),
        "phase": phase.key,
        "phaseLabelEn": phase.label_en,
        "phaseLabelAr": phase.label_ar,
        "done": counter["done"],
        "total": counter["total"],
        "etaSeconds": eta,
        "etaLabelEn": _duration_en(eta) if eta else None,
        "etaLabelAr": _duration_ar(eta) if eta else None,
        "measuredImageSeconds": measured_image_seconds(book),
        "phases": [
            {
                "key": p.key,
                "labelEn": p.label_en,
                "labelAr": p.label_ar,
                "weight": p.weight,
                "percent": int(round(fractions[p.key] * 100)),
            }
            for p in PHASES
        ],
        "messageAr": message_ar,
        "messageEn": message_en,
    }
