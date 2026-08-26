#!/usr/bin/env python3
"""Density gate for image prompts — the rule that makes the model be specific.

`compile-prompts` already refuses a compiled string under 320 characters, but
that floor is trivially cleared by long vague sentences. "A beautiful detailed
kitchen with nice morning light" is 50 characters of nothing: the image model
invents the kitchen, and it invents a different one on every page, which is
exactly how continuity breaks and why pages get regenerated.

So the gate here scores the *structured fields*, before compilation, on three
axes an illustrator actually needs:

* **Substance** — each field carries enough words to describe a real thing.
* **Concreteness** — colour, material, and state words are present where the
  field exists to specify them (props, lighting, foreground).
* **Absence of filler** — a banned-word list for the adjectives that feel
  descriptive and specify nothing, in English and Arabic.

The score is deliberately readable rather than clever: every deduction names
the field and says what to add, because the consumer is a model rewriting the
JSON, not a human reading a dashboard.

Pure and dependency-free — no I/O, no story_pipeline import.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Words that read as description and commit to nothing. A prompt writer reaching
# for these is skipping the decision the image model then makes at random.
VAGUE_TERMS = frozenset(
    {
        # English
        "nice", "beautiful", "pretty", "lovely", "amazing", "wonderful",
        "detailed", "highly detailed", "very detailed", "intricate",
        "various", "some", "several", "a few", "many", "etc", "and so on",
        "appropriate", "suitable", "fitting", "typical", "normal", "usual",
        "generic", "standard", "classic", "stuff", "things", "objects",
        "elements", "background elements", "atmospheric", "moody",
        "interesting", "dynamic", "epic", "stunning", "gorgeous",
        "masterpiece", "best quality", "high quality", "4k", "8k",
        # Arabic — the same failure in the language the family speaks
        "جميل", "جميلة", "حلو", "حلوة", "رائع", "رائعة", "مناسب", "مناسبة",
        "عادي", "عادية", "بعض", "أشياء", "حاجات", "مميز", "مميزة", "تفاصيل كثيرة",
    }
)

# A prop or a lit surface has to have a colour. Substring match on purpose:
# "deep-plum", "off-white", "الأزرق" all hit.
COLOR_HINTS = (
    "red", "orange", "yellow", "green", "blue", "indigo", "violet", "purple",
    "pink", "brown", "beige", "cream", "ivory", "white", "black", "grey",
    "gray", "gold", "silver", "bronze", "copper", "teal", "turquoise", "mint",
    "amber", "ochre", "rust", "plum", "lilac", "navy", "olive", "sand",
    "charcoal", "crimson", "scarlet", "emerald", "sapphire", "peach", "coral",
    "أحمر", "أزرق", "أخضر", "أصفر", "بني", "أبيض", "أسود", "ذهبي", "فضي",
    "برتقالي", "بنفسجي", "وردي", "رمادي", "بيج", "نحاسي", "زيتي",
)

# Material and surface words — "a chair" is a guess, "a worn pine chair" is a
# drawing.
MATERIAL_HINTS = (
    "wood", "wooden", "pine", "oak", "bamboo", "wicker", "rattan", "straw",
    "cork", "metal", "steel", "iron", "brass", "copper", "tin", "aluminium",
    "aluminum", "glass", "crystal", "ceramic", "porcelain", "clay",
    "terracotta", "stone", "marble", "granite", "concrete", "brick", "plaster",
    "chalk", "cloth", "fabric", "cotton", "linen", "wool", "yarn", "felt",
    "silk", "velvet", "denim", "canvas", "leather", "suede", "paper",
    "cardboard", "plastic", "rubber", "sponge", "foam", "plush", "woven",
    "knitted", "embroidered", "painted", "varnished", "polished", "matte",
    "glossy", "enamel", "wax", "wicker",
    "خشب", "خشبي", "معدن", "معدني", "زجاج", "زجاجي", "قماش", "قطن", "صوف",
    "جلد", "ورق", "بلاستيك", "فخار", "حجر", "رخام", "مطرز", "إسفنج", "شمع",
)

# State words. A prop's *state* is what carries continuity across pages — the
# half-eaten sandwich on page 4 is the same one from page 3. A prop that names
# its state is as specific as one that names its material, so either satisfies
# the concreteness rule.
STATE_HINTS = (
    "worn", "chipped", "cracked", "faded", "scratched", "dusty", "damp", "wet",
    "dry", "muddy", "bent", "half-eaten", "half-full", "half-empty", "open",
    "closed", "folded", "crumpled", "torn", "stacked", "spilled", "tangled",
    "knotted", "peeling", "rusted", "rust", "melting", "compressed",
    "squeezed", "clenched", "tied", "loose", "frayed", "burnt", "wilted",
    "مكسور", "مقصوص", "مفتوح", "مقفول", "مطوي", "متسخ", "مبلول", "ممزق",
)

# Light has a direction and a temperature or it is not lighting, it is a wish.
LIGHT_HINTS = (
    "left", "right", "above", "below", "behind", "front", "side", "back",
    "window", "lamp", "sun", "sunlight", "moon", "fire", "candle", "screen",
    "warm", "cool", "golden", "blue", "amber", "soft", "hard", "diffuse",
    "rim", "fill", "key", "backlit", "shadow", "highlight", "overcast",
    "يمين", "شمال", "فوق", "تحت", "خلف", "شباك", "شمس", "دافئ", "بارد", "ظل",
)


@dataclass(frozen=True)
class FieldRule:
    """One scored field: where it lives, how much it owes, what it must name."""

    path: str            # dotted path into the prompt payload
    min_words: int
    weight: int
    requires: tuple[str, ...] = ()   # hint families that must appear
    per_persona: bool = False        # keyed by personaId instead of a plain value
    page_only: bool = True           # skipped on character/location sheets


# The weights add to 100 for a story page. Identity and place carry the most
# because they are what breaks across pages and forces a regeneration.
PAGE_RULES: tuple[FieldRule, ...] = (
    FieldRule("narrativeBeat", 6, 6),
    FieldRule("primaryRequest", 6, 8),
    FieldRule("scene.place", 6, 8, requires=("material",)),
    FieldRule("scene.timeOfDay", 4, 4, requires=("light",)),
    FieldRule("scene.lighting", 8, 10, requires=("light", "color")),
    FieldRule("scene.atmosphere", 5, 4),
    FieldRule("scene.foreground", 8, 8, requires=("material", "color")),
    FieldRule("scene.midground", 8, 8, requires=("material",)),
    FieldRule("scene.background", 7, 6),
    FieldRule("scene.backdropDetails", 12, 6),
    FieldRule("identityLocks.face", 6, 10, per_persona=True),
    FieldRule("identityLocks.hair", 4, 6, per_persona=True),
    FieldRule("fixedOutfits", 6, 8, per_persona=True, requires=("color",)),
    FieldRule("actionAndEmotion.action", 6, 8, per_persona=True),
    FieldRule("actionAndEmotion.emotion", 4, 4, per_persona=True),
    FieldRule("palette", 4, 4, requires=("color",)),
)

# Each asset kind owes a different subset. A character sheet is people against a
# neutral field — asking it for a background layer produces invented scenery that
# then contradicts the location sheets. A location sheet is the opposite: the
# place is the whole point and nobody is in it.
CHARACTER_SHEET_SKIP = (
    "narrativeBeat",
    "primaryRequest",
    "actionAndEmotion.action",
    "actionAndEmotion.emotion",
    "scene.place",
    "scene.timeOfDay",
    "scene.atmosphere",
    "scene.foreground",
    "scene.midground",
    "scene.background",
    "scene.backdropDetails",
)
LOCATION_SHEET_SKIP = ("narrativeBeat",)

# propsInFrame is a list, scored on its own terms.
MIN_PROPS_PAGE = 3
PROPS_WEIGHT = 8

# Scored but never blocking on their own. Worth ~15% of a page, so a prompt that
# skips all of them tops out in the mid-eighties: fine at the default threshold,
# impossible at --min-depth 95.
# (path, points, min words, why it matters). shotScale and viewpoint are one
# word each by design — "wide", "low" — so they are scored on presence.
RECOMMENDED_RULES: tuple[tuple[str, int, int, str], ...] = (
    ("composition.shotScale", 3, 1, "the page has no stated framing"),
    ("composition.viewpoint", 3, 1, "the page has no stated camera height"),
    ("composition.focalHierarchy", 3, 3, "nothing states what the eye hits first"),
    ("composition.lens", 3, 3, "every page reads as the same flat camera"),
    ("composition.depthOfField", 3, 3, "nothing tells the model what to hold sharp"),
    ("colorScript", 3, 3, "the beat gets no colour emphasis of its own"),
)

DEFAULT_MIN_SCORE = 80
SHEET_MIN_SCORE = 70
# Every recommended field filled as well. Set --min-depth 95 to require them.
STRICT_MIN_SCORE = 95

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass
class DepthReport:
    asset_id: str
    score: int
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict[str, Any]:
        return {
            "assetId": self.asset_id,
            "score": self.score,
            "ok": self.ok,
            "failures": self.failures,
            "warnings": self.warnings,
        }


def word_count(value: Any) -> int:
    if not isinstance(value, str):
        return 0
    return len(_WORD_RE.findall(value))


def is_stub(value: Any) -> bool:
    """True for an unfilled template field — the literal CHANGE: placeholder."""
    return isinstance(value, str) and value.strip().upper().startswith("CHANGE")


def vague_hits(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    lowered = value.lower()
    hits = []
    for term in VAGUE_TERMS:
        # Word-boundary match for Latin; plain containment for Arabic, which the
        # \b class does not segment reliably.
        if term.isascii():
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                hits.append(term)
        elif term in value:
            hits.append(term)
    return sorted(set(hits))


def _has_hint(value: str, hints: tuple[str, ...]) -> bool:
    lowered = value.lower()
    return any(hint in lowered for hint in hints)


_HINT_FAMILIES = {
    "color": (COLOR_HINTS, "a colour"),
    "material": (MATERIAL_HINTS, "a material or surface state"),
    "light": (LIGHT_HINTS, "a light direction or temperature"),
}


def _dig(payload: dict[str, Any], path: str) -> Any:
    node: Any = payload
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _persona_ids(payload: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for entry in payload.get("participants") or []:
        if not isinstance(entry, dict) or entry.get("onPage", True) is False:
            continue
        pid = entry.get("id")
        if isinstance(pid, str) and pid.startswith("persona-"):
            ids.append(pid)
    return ids


def _resolve_values(
    payload: dict[str, Any], rule: FieldRule, persona_ids: list[str]
) -> list[tuple[str, Any]]:
    """(label, value) pairs this rule scores — one per persona when keyed."""
    if not rule.per_persona:
        return [(rule.path, _dig(payload, rule.path))]
    head, _, leaf = rule.path.partition(".")
    container = payload.get(head)
    if not isinstance(container, dict):
        return [(f"{rule.path} [{pid}]", None) for pid in persona_ids]
    out: list[tuple[str, Any]] = []
    for pid in persona_ids:
        entry = container.get(pid)
        value = entry.get(leaf) if leaf and isinstance(entry, dict) else entry
        out.append((f"{head}.{pid}{'.' + leaf if leaf else ''}", value))
    return out


def _score_props(payload: dict[str, Any], minimum: int) -> tuple[int, list[str]]:
    """propsInFrame: enough entries, each naming a colour and a material/state."""
    props = _dig(payload, "scene.propsInFrame")
    entries = [p for p in props if isinstance(p, str) and not is_stub(p)] if isinstance(props, list) else []
    failures: list[str] = []
    if len(entries) < minimum:
        failures.append(
            f"scene.propsInFrame has {len(entries)} usable entries, needs {minimum}. "
            "List every visible prop with its colour, material, and current state."
        )
        return 0, failures
    thin = [
        p for p in entries
        if not (
            _has_hint(p, COLOR_HINTS)
            and (_has_hint(p, MATERIAL_HINTS) or _has_hint(p, STATE_HINTS))
        )
    ]
    if thin:
        failures.append(
            f"scene.propsInFrame entries need a colour AND either a material or a "
            f"state — these have only one: {'; '.join(thin[:3])}"
        )
        return PROPS_WEIGHT // 2, failures
    return PROPS_WEIGHT, failures


def score_prompt(payload: dict[str, Any], *, asset_id: str | None = None) -> DepthReport:
    """Score one prompt payload. Failures block; warnings only inform."""
    asset_id = asset_id or str(payload.get("assetId") or "asset")
    is_character_sheet = asset_id == "character-sheet"
    is_location_sheet = asset_id.startswith("location-sheet-")
    is_sheet = is_character_sheet or is_location_sheet
    is_page = not is_sheet

    persona_ids = _persona_ids(payload)
    if is_location_sheet:
        persona_ids = []

    report = DepthReport(asset_id=asset_id, score=0)
    earned = 0.0
    available = 0.0

    skip: tuple[str, ...] = ()
    if is_character_sheet:
        skip = CHARACTER_SHEET_SKIP
    elif is_location_sheet:
        skip = LOCATION_SHEET_SKIP

    for rule in PAGE_RULES:
        if rule.path in skip:
            continue
        if is_location_sheet and rule.per_persona:
            continue
        if rule.per_persona and not persona_ids:
            continue
        pairs = _resolve_values(payload, rule, persona_ids)
        share = rule.weight / max(1, len(pairs))
        for label, value in pairs:
            available += share
            if value is None or is_stub(value) or not str(value).strip():
                report.failures.append(
                    f"{label} is empty or still a CHANGE stub — it must describe "
                    f"something drawable in at least {rule.min_words} words."
                )
                continue
            text = str(value)
            words = word_count(text)
            if words < rule.min_words:
                report.failures.append(
                    f"{label} is {words} words, needs {rule.min_words}+. "
                    "Name the specific thing, not the category."
                )
                continue
            missing_hints = [
                _HINT_FAMILIES[fam][1]
                for fam in rule.requires
                if not _has_hint(text, _HINT_FAMILIES[fam][0])
            ]
            if missing_hints:
                report.failures.append(
                    f"{label} never names {' or '.join(missing_hints)}: {text[:90]}"
                )
                continue
            hits = vague_hits(text)
            if hits:
                report.failures.append(
                    f"{label} uses filler words ({', '.join(hits)}) — replace each "
                    "with the specific thing it is standing in for."
                )
                continue
            earned += share

    # A character sheet has no scene, so it has no props to keep consistent.
    if not is_character_sheet:
        prop_points, prop_failures = _score_props(
            payload, MIN_PROPS_PAGE if is_page else 2
        )
        available += PROPS_WEIGHT
        earned += prop_points
        report.failures.extend(prop_failures)

    # Continuity is what stops a book looking like 22 unrelated drawings. Only
    # meaningful once there is a previous page to carry state from.
    if is_page and asset_id.startswith("page-") and asset_id != "page-01":
        available += 6
        carried = _dig(payload, "continuity.fromPreviousPage")
        if not carried or is_stub(carried) or word_count(carried) < 5:
            report.failures.append(
                "continuity.fromPreviousPage must name what each returning "
                "person still wears, holds, or carries from the page before."
            )
        else:
            earned += 6

    # Recommended fields: they warn instead of blocking, because projects
    # written before they existed must still validate — but they DO carry score.
    # That is what makes --min-depth a real lever: leave the default and a book
    # without them still ships; raise it to 95 and the writer has to fill every
    # one. A warning that costs nothing gets ignored, so these cost points.
    if is_page:
        for rule_path, points, min_words, why in RECOMMENDED_RULES:
            available += points
            value = _dig(payload, rule_path)
            if not value or is_stub(value) or word_count(value) < min_words:
                report.warnings.append(f"{rule_path} is unset — {why}.")
            else:
                earned += points

    report.score = int(round(100 * earned / available)) if available else 0
    return report


def minimum_score(asset_id: str) -> int:
    if asset_id == "character-sheet" or asset_id.startswith("location-sheet-"):
        return SHEET_MIN_SCORE
    return DEFAULT_MIN_SCORE


def gate(payload: dict[str, Any], *, asset_id: str, threshold: int | None = None) -> DepthReport:
    """Score, then convert a low total into a blocking failure of its own."""
    report = score_prompt(payload, asset_id=asset_id)
    limit = threshold if threshold is not None else minimum_score(asset_id)
    if report.score < limit and not report.failures:
        report.failures.append(
            f"prompt depth score {report.score} is under the {limit} minimum — "
            "expand the scene layers, identity locks, and props."
        )
    return report
