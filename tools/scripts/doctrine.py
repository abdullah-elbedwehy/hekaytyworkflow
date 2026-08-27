"""Hekayati handoff doctrine — load, query, and enforce Omar's rulebook.

`tools/references/handoff.md` is the single source of truth for this business.
Its machine-readable twin is `tools/references/handoff/doctrine.json`, and this
module is the only code path that reads it.

Everything here is deliberately standalone: `story_pipeline.py` imports it, the
Obsidian vault builder renders from it, and the manual ChatGPT dispatch pastes
its clauses verbatim. One rulebook, three consumers, no second copy to drift.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

DOCTRINE_SCHEMA_VERSION = 1
BOOK_STRUCTURE_ID = "hekayati-22"

_SCRIPT_DIR = Path(__file__).resolve().parent
_REFERENCES = _SCRIPT_DIR.parent / "references"
DOCTRINE_PATH = _REFERENCES / "handoff" / "doctrine.json"
HANDOFF_PATH = _REFERENCES / "handoff.md"

# Same fold as story_pipeline._fold_story_text: doctrine patterns are written
# against folded text so a hamza or a fatha cannot smuggle a banned phrase past
# the check.
_ARABIC_DIACRITICS_RE = re.compile(r"[ً-ٰٟۖ-ۭ]")
_FOLD_MAP = {
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ٱ": "ا",
    "ى": "ي",
    "ؤ": "و",
    "ئ": "ي",
    "ة": "ه",
    "ـ": "",  # tatweel
}

_PAGE_ID_RE = re.compile(r"^page-(\d{2,})$")

_STORY_PAGE_ROLE = "story"
_ROLE_ORDER = ("cover", "dedication", "story", "other-stories", "back-cover")


class DoctrineError(RuntimeError):
    """Raised when the doctrine file itself is unusable."""


_CACHE: dict[str, Any] = {}


def _fold_chars(value: Any) -> str:
    text = _ARABIC_DIACRITICS_RE.sub("", str(value or ""))
    for source, target in _FOLD_MAP.items():
        text = text.replace(source, target)
    return text


def fold(value: Any) -> str:
    """Normalize Arabic for pattern matching (diacritics, hamza, ta-marbuta)."""
    return re.sub(r"\s+", " ", _fold_chars(value)).strip()


def fold_pattern(pattern: str) -> re.Pattern[str]:
    """Compile a doctrine regex against folded text.

    Patterns live in `doctrine.json` in ordinary Arabic spelling so a human can
    read them. Only the Arabic letters are folded — regex metacharacters and
    whitespace classes are left alone — so `قلبه بقى` still matches a page that
    spells it `قلبُه بقي`.
    """
    cached = _CACHE.setdefault("patterns", {})
    if pattern not in cached:
        cached[pattern] = re.compile(_fold_chars(pattern))
    return cached[pattern]


def load_doctrine(*, refresh: bool = False) -> dict[str, Any]:
    """Read and validate the doctrine, caching the parsed result."""
    if not refresh and "doctrine" in _CACHE:
        return _CACHE["doctrine"]
    if not DOCTRINE_PATH.is_file():
        raise DoctrineError(f"Doctrine file missing: {DOCTRINE_PATH}")
    try:
        payload = json.loads(DOCTRINE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DoctrineError(f"Doctrine file is not valid JSON: {DOCTRINE_PATH}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DoctrineError("Doctrine root must be an object")
    if payload.get("schemaVersion") != DOCTRINE_SCHEMA_VERSION:
        raise DoctrineError(
            f"Unsupported doctrine schemaVersion {payload.get('schemaVersion')!r}; "
            f"expected {DOCTRINE_SCHEMA_VERSION}"
        )
    _validate_doctrine(payload)
    _CACHE["doctrine"] = payload
    return payload


def _validate_doctrine(payload: Mapping[str, Any]) -> None:
    required = (
        "literalLanguage",
        "narrativeStructure",
        "culturalConstraints",
        "storyTypes",
        "dialect",
        "bookStructure",
        "imageTool",
        "printSafeColor",
        "gamePages",
    )
    for key in required:
        if not isinstance(payload.get(key), dict):
            raise DoctrineError(f"Doctrine section {key!r} must be an object")

    structure = payload["bookStructure"]
    if structure.get("id") != BOOK_STRUCTURE_ID:
        raise DoctrineError(f"bookStructure.id must be {BOOK_STRUCTURE_ID!r}")
    for key in ("pdfPageCount", "interiorPageCount", "storyPageCount"):
        value = structure.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise DoctrineError(f"bookStructure.{key} must be a positive integer")
    if structure["pdfPageCount"] != structure["interiorPageCount"] + 2:
        raise DoctrineError("bookStructure.pdfPageCount must be interiorPageCount + 2 covers")
    if structure["storyPageCount"] >= structure["interiorPageCount"]:
        raise DoctrineError("storyPageCount must leave room for dedication + other-stories")
    if "{{hero}}" not in str(structure.get("dedicationTemplateAr") or ""):
        raise DoctrineError("dedicationTemplateAr must contain the {{hero}} placeholder")
    icons = (structure.get("backCover") or {}).get("icons")
    if not isinstance(icons, list) or len(icons) != 5:
        raise DoctrineError("backCover.icons must list exactly the five mandatory icons")

    for group, label in (
        (payload["literalLanguage"].get("metaphorPatterns"), "literalLanguage.metaphorPatterns"),
        (payload["literalLanguage"].get("wisdomPatterns"), "literalLanguage.wisdomPatterns"),
        (
            payload["narrativeStructure"].get("unearnedRewardPatterns"),
            "narrativeStructure.unearnedRewardPatterns",
        ),
        (
            payload["culturalConstraints"].get("personalFoodSharingPatterns"),
            "culturalConstraints.personalFoodSharingPatterns",
        ),
    ):
        _validate_pattern_group(group, label)

    for type_id, entry in payload["storyTypes"].items():
        if type_id not in {"A", "B", "C"}:
            raise DoctrineError(f"Unknown story type {type_id!r}; expected A, B or C")
        if entry.get("storyGoalMode") not in {"educational", "entertainment"}:
            raise DoctrineError(f"storyTypes.{type_id}.storyGoalMode must be educational|entertainment")

    _validate_game_pages(payload)


def _validate_game_pages(payload: Mapping[str, Any]) -> None:
    """Every game kind must state what the author has to supply, and what to draw.

    A game page whose rules are missing is worse than one with no rules at all:
    the prompt still compiles, the image still renders, and nobody notices the
    maze has three exits until the book is printed.
    """
    section = payload["gamePages"]
    types = section.get("types")
    if not isinstance(types, dict) or not types:
        raise DoctrineError("gamePages.types must be a non-empty object")
    for kind, entry in types.items():
        if not isinstance(entry, dict):
            raise DoctrineError(f"gamePages.types.{kind} must be an object")
        for field in ("clauseEn", "shortClauseEn"):
            if not str(entry.get(field) or "").strip():
                raise DoctrineError(f"gamePages.types.{kind}.{field} is required")
        fields = entry.get("requiredFields")
        if not isinstance(fields, list) or not all(
            isinstance(name, str) and name.strip() for name in fields
        ):
            raise DoctrineError(
                f"gamePages.types.{kind}.requiredFields must list field names"
            )
    for field in ("sharedClauseEn", "sharedShortClauseEn"):
        if not str(section.get(field) or "").strip():
            raise DoctrineError(f"gamePages.{field} is required")


def _validate_pattern_group(group: Any, label: str) -> None:
    if not isinstance(group, list) or not group:
        raise DoctrineError(f"{label} must be a non-empty list")
    seen: set[str] = set()
    for index, entry in enumerate(group, start=1):
        if not isinstance(entry, dict):
            raise DoctrineError(f"{label}[{index}] must be an object")
        rule_id = entry.get("id")
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise DoctrineError(f"{label}[{index}].id must be non-empty text")
        if rule_id in seen:
            raise DoctrineError(f"{label} repeats id {rule_id!r}")
        seen.add(rule_id)
        if not isinstance(entry.get("messageAr"), str) or not entry["messageAr"].strip():
            raise DoctrineError(f"{label}[{index}].messageAr must be non-empty text")
        if entry.get("severity") not in {"high", "medium", "low"}:
            raise DoctrineError(f"{label}[{index}].severity must be high|medium|low")
        try:
            fold_pattern(str(entry.get("pattern") or ""))
        except re.error as exc:
            raise DoctrineError(f"{label}[{index}].pattern is not a valid regex: {exc}") from exc


def doctrine_section(name: str) -> Any:
    doctrine = load_doctrine()
    if name not in doctrine:
        available = ", ".join(sorted(k for k in doctrine if isinstance(doctrine[k], (dict, list))))
        raise DoctrineError(f"Unknown doctrine section {name!r}. Available: {available}")
    return doctrine[name]


# --------------------------------------------------------------------------
# Book structure (handoff §7)
# --------------------------------------------------------------------------


def book_structure() -> dict[str, Any]:
    return load_doctrine()["bookStructure"]


def doctrine_pdf_page_count() -> int:
    return int(book_structure()["pdfPageCount"])


def doctrine_story_page_count() -> int:
    return int(book_structure()["storyPageCount"])


def structure_slot_roles(pdf_page_count: int) -> dict[str, str]:
    """Map every asset id in a `hekayati-22` book to its structural role.

    Interior pages are `page-01`..`page-(N-2)`. The first interior page is the
    dedication, the last is the «قصص تانية» page, and everything between is a
    story page. That holds for any page count, so a shorter test book still has
    a coherent structure instead of silently losing the fixed pages.
    """
    interior = int(pdf_page_count) - 2
    if interior < 3:
        raise DoctrineError(
            "hekayati-22 needs at least 3 interior pages (dedication + story + other-stories)"
        )
    roles: dict[str, str] = {"cover": "cover", "back-cover": "back-cover"}
    for index in range(1, interior + 1):
        asset_id = f"page-{index:02d}"
        if index == 1:
            roles[asset_id] = "dedication"
        elif index == interior:
            roles[asset_id] = "other-stories"
        else:
            roles[asset_id] = _STORY_PAGE_ROLE
    return roles


def structure_slots(pdf_page_count: int) -> dict[str, Any]:
    roles = structure_slot_roles(pdf_page_count)
    story_pages = [asset_id for asset_id, role in roles.items() if role == _STORY_PAGE_ROLE]
    story_pages.sort(key=_page_index)
    return {
        "structureId": BOOK_STRUCTURE_ID,
        "pdfPageCount": int(pdf_page_count),
        "interiorPageCount": int(pdf_page_count) - 2,
        "cover": "cover",
        "dedication": "page-01",
        "storyPages": story_pages,
        "storyPageCount": len(story_pages),
        "otherStories": f"page-{int(pdf_page_count) - 2:02d}",
        "backCover": "back-cover",
        "roles": roles,
    }


def _page_index(asset_id: str) -> int:
    match = _PAGE_ID_RE.match(str(asset_id))
    return int(match.group(1)) if match else 0


def page_role(asset_id: str, pdf_page_count: int) -> str:
    return structure_slot_roles(pdf_page_count).get(str(asset_id), _STORY_PAGE_ROLE)


def is_story_page(asset_id: str, pdf_page_count: int) -> bool:
    return page_role(asset_id, pdf_page_count) == _STORY_PAGE_ROLE


def is_fixed_page(asset_id: str, pdf_page_count: int) -> bool:
    """Fixed pages carry doctrine-owned copy, not authored story text."""
    return page_role(asset_id, pdf_page_count) in {"dedication", "other-stories", "back-cover"}


def role_label_ar(role: str) -> str:
    labels = {
        "cover": "الغلاف الأمامي",
        "dedication": "الإهداء",
        "story": "صفحة قصة",
        "other-stories": "قصص تانية",
        "back-cover": "الغلاف الخلفي",
    }
    return labels.get(role, role)


def dedication_text(hero_name: str) -> str:
    """Render handoff §7's fixed dedication for one child."""
    name = " ".join(str(hero_name or "").split())
    if not name:
        raise DoctrineError("dedication_text needs the child's display name")
    template = str(book_structure()["dedicationTemplateAr"])
    return template.replace("{{hero}}", name)


def back_cover_text() -> str:
    return str(book_structure()["backCover"]["marketingCopyAr"])


def back_cover_icons() -> list[dict[str, str]]:
    return [dict(icon) for icon in book_structure()["backCover"]["icons"]]


def back_cover_icon_line() -> str:
    return " / ".join(f"{icon['emoji']} {icon['labelAr']}" for icon in back_cover_icons())


def other_stories_row_count() -> int:
    return int(book_structure()["otherStoriesPage"]["rows"])


# --------------------------------------------------------------------------
# Story types (handoff §5)
# --------------------------------------------------------------------------


def story_types() -> dict[str, Any]:
    return load_doctrine()["storyTypes"]


def story_type(type_id: Any) -> dict[str, Any]:
    types = story_types()
    key = str(type_id or "").strip().upper()
    if key not in types:
        raise DoctrineError(f"Unknown story type {type_id!r}; expected one of {', '.join(sorted(types))}")
    return types[key]


def story_types_for_mode(mode: Any) -> list[str]:
    normalized = str(mode or "").strip().lower()
    return sorted(
        type_id
        for type_id, entry in story_types().items()
        if entry.get("storyGoalMode") == normalized
    )


# --------------------------------------------------------------------------
# Prompt clauses (handoff §8 + §9)
# --------------------------------------------------------------------------


def print_safe_clause(language: str = "en") -> str:
    section = load_doctrine()["printSafeColor"]
    key = "promptClauseAr" if str(language).lower().startswith("ar") else "promptClauseEn"
    return str(section[key])


def game_types() -> dict[str, Any]:
    return load_doctrine()["gamePages"]["types"]


def game_kinds() -> list[str]:
    return sorted(game_types())


def game_type(kind: Any) -> dict[str, Any]:
    types = game_types()
    key = str(kind or "").strip().casefold()
    if key not in types:
        raise DoctrineError(
            f"Unknown game kind {kind!r}; expected one of {', '.join(sorted(types))}"
        )
    return types[key]


def game_shared_clause() -> str:
    return str(load_doctrine()["gamePages"]["sharedClauseEn"])


def game_clause(kind: Any) -> str:
    """The shared playability rule plus the one specific to this game kind."""
    return f"{game_shared_clause()} {game_type(kind)['clauseEn']}"


def game_short_clause(kind: Any) -> str:
    """The same contract, compressed for a length-bounded image prompt.

    The long form is the written rule; this is what actually reaches the model,
    because a game page also has to carry a scene, identity locks and the exact
    Arabic. What must never be dropped in the compression is the ban on drawing
    the answer — a maze printed with its route traced is a wasted page.
    """
    section = load_doctrine()["gamePages"]
    entry = game_type(kind)
    return f"{section['sharedShortClauseEn']} {entry['shortClauseEn']}"


def game_required_fields(kind: Any) -> list[str]:
    return list(game_type(kind)["requiredFields"])


def reference_sheet_clause() -> str:
    return str(load_doctrine()["imageTool"]["referenceSheetClauseAr"])


def arabic_text_clause() -> str:
    return str(load_doctrine()["imageTool"]["arabicTextClauseEn"])


def required_orientation() -> str:
    return str(load_doctrine()["imageTool"]["orientation"])


def required_aspect_ratio() -> str:
    return str(load_doctrine()["imageTool"]["aspectRatio"])


def character_sheet_angles() -> list[str]:
    return list(load_doctrine()["imageTool"]["characterSheetAngles"])


def register_replacements() -> list[dict[str, Any]]:
    """Dialect fixes from handoff §6, shaped like age-profiles registerReplacements."""
    return [dict(entry) for entry in load_doctrine()["dialect"]["registerReplacements"]]


# --------------------------------------------------------------------------
# Enforcement
# --------------------------------------------------------------------------


def _pattern_groups() -> list[tuple[str, list[dict[str, Any]]]]:
    doctrine = load_doctrine()
    return [
        ("literal-metaphor", doctrine["literalLanguage"]["metaphorPatterns"]),
        ("wisdom-quote", doctrine["literalLanguage"]["wisdomPatterns"]),
        ("unearned-reward", doctrine["narrativeStructure"]["unearnedRewardPatterns"]),
        ("personal-food-sharing", doctrine["culturalConstraints"]["personalFoodSharingPatterns"]),
    ]


def scan_text(text: Any) -> list[dict[str, Any]]:
    """Return every doctrine pattern hit in one page's visible text."""
    folded = fold(text)
    if not folded:
        return []
    hits: list[dict[str, Any]] = []
    for code, group in _pattern_groups():
        for entry in group:
            match = fold_pattern(entry["pattern"]).search(folded)
            if match is None:
                continue
            hit = {
                "code": code,
                "ruleId": entry["id"],
                "severity": entry["severity"],
                "match": match.group(0),
                "message": entry["messageAr"],
            }
            exception = entry.get("exceptionAr")
            if exception:
                hit["exceptionAr"] = exception
            hits.append(hit)
    return hits


def _visible_pages(pages: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [page for page in pages if isinstance(page, Mapping)]


def structure_errors(
    payload: Mapping[str, Any], pages: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Handoff §7 — 22 interior pages, exactly 20 of them story pages."""
    structure_id = str(payload.get("bookStructure") or BOOK_STRUCTURE_ID)
    if structure_id != BOOK_STRUCTURE_ID:
        return [
            {
                "code": "unknown-book-structure",
                "ruleId": "handoff-7",
                "message": (
                    f"story.bookStructure must be {BOOK_STRUCTURE_ID!r} (22 interior pages "
                    f"+ 2 separate covers); got {structure_id!r}"
                ),
            }
        ]

    page_list = _visible_pages(pages)
    page_ids = [str(page.get("id") or "").strip() for page in page_list]
    total = len(page_ids)
    expected_total = int(payload.get("pageCount") or total)
    errors: list[dict[str, Any]] = []
    if total != expected_total:
        errors.append(
            {
                "code": "page-count-mismatch",
                "ruleId": "handoff-7",
                "message": f"story.pageCount={expected_total} but pages[] holds {total} entries",
            }
        )
    required_total = doctrine_pdf_page_count()
    if total != required_total:
        errors.append(
            {
                "code": "wrong-book-length",
                "ruleId": "handoff-7",
                "found": total,
                "expected": required_total,
                "message": (
                    f"الكتاب لازم يكون {required_total} صفحة PDF "
                    f"(غلاف + إهداء + {doctrine_story_page_count()} صفحة قصة + قصص تانية + غلاف خلفي)؛ "
                    f"الموجود {total}."
                ),
            }
        )
    if total < 5:
        return errors

    roles = structure_slot_roles(total)
    for asset_id in ("cover", "page-01", f"page-{total - 2:02d}", "back-cover"):
        if asset_id not in page_ids:
            errors.append(
                {
                    "code": "missing-structural-page",
                    "ruleId": "handoff-7",
                    "pageId": asset_id,
                    "message": (
                        f"Missing {role_label_ar(roles.get(asset_id, 'story'))} page {asset_id}"
                    ),
                }
            )

    story_ids = [page_id for page_id in page_ids if roles.get(page_id) == _STORY_PAGE_ROLE]
    required_story_pages = doctrine_story_page_count()
    if total == required_total and len(story_ids) != required_story_pages:
        errors.append(
            {
                "code": "story-page-count",
                "ruleId": "handoff-7",
                "found": len(story_ids),
                "expected": required_story_pages,
                "message": (
                    f"محتوى القصة لازم يكون {required_story_pages} صفحة بالظبط "
                    f"(page-02 → page-{required_story_pages + 1:02d})؛ الموجود {len(story_ids)}. "
                    "طبّق قاعدة الدمج قبل أي برومبت صور."
                ),
            }
        )
    return errors


def fixed_page_errors(
    payload: Mapping[str, Any], pages: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Dedication and back-cover copy is doctrine-owned; it must match verbatim."""
    page_list = _visible_pages(pages)
    total = len(page_list)
    if total < 5:
        return []
    roles = structure_slot_roles(total)
    hero = _hero_display_name(payload)
    errors: list[dict[str, Any]] = []
    for page in page_list:
        page_id = str(page.get("id") or "").strip()
        role = roles.get(page_id)
        text = str(page.get("text") or "")
        if role == "dedication" and hero:
            if fold(text) != fold(dedication_text(hero)):
                errors.append(
                    {
                        "code": "dedication-text-drift",
                        "ruleId": "handoff-7",
                        "pageId": page_id,
                        "message": (
                            "نص الإهداء ثابت الصيغة — استخدم القالب زي ما هو مع اسم الطفل بس. "
                            "شغّل `apply-fixed-pages` عشان يتكتب صح."
                        ),
                    }
                )
        elif role == "back-cover":
            if fold(text) != fold(back_cover_text()):
                errors.append(
                    {
                        "code": "back-cover-text-drift",
                        "ruleId": "handoff-7",
                        "pageId": page_id,
                        "message": (
                            "نص الغلاف الخلفي التسويقي ثابت — ممنوع إعادة صياغته. "
                            "شغّل `apply-fixed-pages` عشان يتكتب صح."
                        ),
                    }
                )
    return errors


def _hero_display_name(payload: Mapping[str, Any]) -> str:
    personas = payload.get("personas")
    if not isinstance(personas, list):
        return ""
    for persona in personas:
        if isinstance(persona, Mapping) and str(persona.get("role") or "").strip() == "hero":
            return str(persona.get("displayName") or "").strip()
    for persona in personas:
        if isinstance(persona, Mapping):
            return str(persona.get("displayName") or "").strip()
    return ""


def story_type_errors(
    payload: Mapping[str, Any], pages: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Handoff §5 — the declared type constrains cast and beats."""
    declared = payload.get("storyType")
    if declared in (None, ""):
        return [
            {
                "code": "missing-story-type",
                "ruleId": "handoff-5",
                "message": (
                    "story.storyType لازم يكون A (تصحيح سلوك) أو B (تشجيع على مكان) "
                    "أو C (مغامرة خيالية) — handoff §5. "
                    "شغّل: set-story-type --project <ABS> --type A|B|C"
                ),
            }
        ]
    try:
        entry = story_type(declared)
    except DoctrineError as exc:
        return [{"code": "unknown-story-type", "ruleId": "handoff-5", "message": str(exc)}]

    errors: list[dict[str, Any]] = []
    mode = str(((payload.get("storyGoal") or {}) if isinstance(payload.get("storyGoal"), Mapping) else {}).get("mode") or "")
    if mode and mode != entry["storyGoalMode"]:
        errors.append(
            {
                "code": "story-type-goal-mismatch",
                "ruleId": "handoff-5",
                "message": (
                    f"Type {entry['id']} ({entry['labelAr']}) is a {entry['storyGoalMode']} book, "
                    f"but storyGoal.mode is {mode!r}"
                ),
            }
        )

    guests = payload.get("guestCharacters")
    has_companion = isinstance(guests, list) and len(guests) > 0
    if entry.get("requiresMagicalCompanion") and not has_companion:
        errors.append(
            {
                "code": "missing-magical-companion",
                "ruleId": "handoff-5",
                "message": "Type A لازم يكون فيه رفيق سحري في guestCharacters[] — handoff §5.",
            }
        )
    if entry.get("allowsMagicalCompanion") is False and has_companion:
        errors.append(
            {
                "code": "forbidden-magical-companion",
                "ruleId": "handoff-5",
                "message": (
                    "Type B بيشتغل بأصدقاء حقيقيين بس — شيل الرفيق السحري من "
                    "guestCharacters[] أو غيّر نوع القصة."
                ),
            }
        )
    if entry.get("requiresRelapseBeat"):
        arc = payload.get("narrativeArc")
        relapse_pages = []
        if isinstance(arc, Mapping):
            for stage in ("setback", "relapse"):
                value = arc.get(stage)
                if isinstance(value, list):
                    relapse_pages.extend(value)
        if not relapse_pages:
            errors.append(
                {
                    "code": "missing-relapse-beat",
                    "ruleId": "handoff-5",
                    "message": (
                        "Type A محتاج لحظة انتكاسة إلزامية قبل الحل — "
                        "خصّص صفحة على الأقل لمرحلة `setback` في narrativeArc."
                    ),
                }
            )
    return errors


def cultural_errors(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Handoff §4 C1 — side friends share the hero's gender."""
    personas = payload.get("personas")
    if not isinstance(personas, list):
        return []
    hero_gender = ""
    for persona in personas:
        if isinstance(persona, Mapping) and str(persona.get("role") or "") == "hero":
            hero_gender = str(persona.get("gender") or "").strip().lower()
            break
    if hero_gender not in {"boy", "girl"}:
        return []
    errors: list[dict[str, Any]] = []
    for persona in personas:
        if not isinstance(persona, Mapping):
            continue
        if str(persona.get("role") or "").strip() != "friend":
            continue
        gender = str(persona.get("gender") or "").strip().lower()
        if gender in {"boy", "girl"} and gender != hero_gender:
            errors.append(
                {
                    "code": "mixed-gender-friend-group",
                    "ruleId": "C1",
                    "personaId": str(persona.get("id") or ""),
                    "message": (
                        "مجموعة الأصدقاء الجانبية لازم تكون من نفس نوع البطل — handoff §4 C1."
                    ),
                }
            )
    return errors


def text_errors(pages: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Run every doctrine text pattern over the visible page text."""
    errors: list[dict[str, Any]] = []
    for page in _visible_pages(pages):
        page_id = str(page.get("id") or "").strip()
        for hit in scan_text(page.get("text")):
            if hit["severity"] != "high":
                continue
            errors.append(
                {
                    "code": f"doctrine-{hit['code']}",
                    "ruleId": hit["ruleId"],
                    "pageId": page_id,
                    "match": hit["match"],
                    "message": f"{page_id}: {hit['message']} (اللي اتلقط: «{hit['match']}»)",
                }
            )
    return errors


def text_warnings(pages: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for page in _visible_pages(pages):
        page_id = str(page.get("id") or "").strip()
        for hit in scan_text(page.get("text")):
            if hit["severity"] == "high":
                continue
            warnings.append(
                {
                    "code": f"doctrine-{hit['code']}",
                    "ruleId": hit["ruleId"],
                    "pageId": page_id,
                    "match": hit["match"],
                    "message": f"{page_id}: {hit['message']} (اللي اتلقط: «{hit['match']}»)",
                }
            )
    return warnings


def doctrine_errors(
    payload: Mapping[str, Any], pages: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Every blocking handoff violation in one story, in rulebook order."""
    page_list = _visible_pages(pages)
    return [
        *structure_errors(payload, page_list),
        *fixed_page_errors(payload, page_list),
        *story_type_errors(payload, page_list),
        *cultural_errors(payload),
        *text_errors(page_list),
    ]


def doctrine_warnings(
    payload: Mapping[str, Any], pages: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    return text_warnings(_visible_pages(pages))


def checklist() -> list[dict[str, Any]]:
    """Flat rule list for the vault checklist note and `show-doctrine`."""
    doctrine = load_doctrine()
    rows: list[dict[str, Any]] = []
    for section, key in (
        ("literalLanguage", "rules"),
        ("narrativeStructure", "rules"),
        ("culturalConstraints", "rules"),
        ("imageTool", "lessons"),
        ("printSafeColor", "rules"),
    ):
        for entry in doctrine[section].get(key) or []:
            rows.append(
                {
                    "section": section,
                    "id": entry.get("id"),
                    "ruleAr": entry.get("ruleAr"),
                }
            )
    return rows


# --------------------------------------------------------------------------
# Legacy → handoff structure migration
# --------------------------------------------------------------------------

_ARC_PAGE_CONTAINERS = ("narrativeArc",)
GAP_PAGE_MARKER = "needsAuthoring"


def shift_page_ids(value: Any, offset: int) -> Any:
    """Renumber every `page-NN` id inside an arbitrary story structure."""
    if isinstance(value, str):
        match = _PAGE_ID_RE.match(value)
        if match is None:
            return value
        return f"page-{int(match.group(1)) + offset:02d}"
    if isinstance(value, list):
        return [shift_page_ids(item, offset) for item in value]
    if isinstance(value, Mapping):
        return {key: shift_page_ids(item, offset) for key, item in value.items()}
    return value


def dedication_page(hero_name: str, location_id: str = "") -> dict[str, Any]:
    """The fixed page-01 (handoff §7). Text is doctrine-owned, never authored.

    It still names a location: the dedication is a decorative page from this
    book's world, so it draws from the same location bible as everything else
    rather than inventing a place with no reference sheet.
    """
    return {
        "id": "page-01",
        "role": "dedication",
        "locationId": location_id,
        "text": dedication_text(hero_name),
        "beat": "الإهداء — بابا وماما بيقولوا للطفل إن الكتاب ده ليه هو",
        "participants": [],
        "guests": [],
        "setting": "صفحة إهداء هادية بزخرفة بسيطة من عالم القصة، من غير شخصيات",
        "action": "صفحة نص هادية — من غير حركة، الشريط السفلي فاضي",
        "fixedByDoctrine": True,
    }


def other_stories_page(asset_id: str, location_id: str = "") -> dict[str, Any]:
    rows = other_stories_row_count()
    return {
        "id": asset_id,
        "role": "other-stories",
        "locationId": location_id,
        "text": "قصص تانية",
        "beat": "صفحة عرض قصص تانية من نفس السلسلة",
        "participants": [],
        "guests": [],
        "setting": (
            f"صفحة عرض بسيطة فيها {rows} صفوف، كل صف اسم قصة على اليمين ومكان "
            "صورة غلاف مصغرة على الشمال (RTL)، خلفية هادية من عالم القصة"
        ),
        "action": f"تخطيط {rows} صفوف متساوية، من غير شخصيات ومن غير حركة",
        "fixedByDoctrine": True,
    }


def gap_page(asset_id: str, position: int, location_id: str = "") -> dict[str, Any]:
    """A declared hole in the story, not filler.

    A legacy 18-page template is two story pages short of the handoff shape.
    Inventing those two pages automatically would be exactly the «مشهد حشو»
    handoff §3 N3 forbids, so the slot is created empty and loudly flagged; the
    gates below refuse to lock until a human writes it.
    """
    return {
        "id": asset_id,
        "role": _STORY_PAGE_ROLE,
        "text": "",
        "beat": f"CHANGE: صفحة قصة {position} لسه محتاجة كتابة — ممنوع حشو",
        "participants": [],
        "guests": [],
        "locationId": location_id,
        "setting": "CHANGE",
        "action": "CHANGE",
        GAP_PAGE_MARKER: True,
    }


def expand_to_handoff_structure(
    story: Mapping[str, Any], *, hero_name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reshape a legacy `cover + page-01..N + back-cover` story into `hekayati-22`.

    Returns the new story plus a report naming every slot that still needs a
    human. Nothing is invented: the dedication and «قصص تانية» pages come from
    the doctrine, and any missing story page is created as an explicit gap.
    """
    pages = [dict(page) for page in story.get("pages") or [] if isinstance(page, Mapping)]
    if not pages:
        raise DoctrineError("Cannot expand a story with no pages")

    cover = pages[0]
    back_cover = pages[-1]
    middle = pages[1:-1]
    if str(cover.get("id")) != "cover" or str(back_cover.get("id")) != "back-cover":
        raise DoctrineError("Expansion expects the first page to be `cover` and the last `back-cover`")

    # Every authored story page moves one slot right to make room for page-01.
    shifted = [shift_page_ids(page, 1) for page in middle]
    for page in shifted:
        page["role"] = _STORY_PAGE_ROLE

    # Fixed and gap pages borrow the cover's place so every page still names a
    # location from the bible and gets its reference sheet.
    default_location = str(cover.get("locationId") or "")
    target = doctrine_story_page_count()
    gaps: list[str] = []
    for index in range(len(shifted), target):
        asset_id = f"page-{index + 2:02d}"
        shifted.append(gap_page(asset_id, index + 1, default_location))
        gaps.append(asset_id)

    surplus = shifted[target:]
    shifted = shifted[:target]

    interior_last = target + 2  # dedication + story pages + other-stories
    other_stories_id = f"page-{interior_last:02d}"

    new_story = dict(story)
    new_story["bookStructure"] = BOOK_STRUCTURE_ID
    new_story["pageCount"] = doctrine_pdf_page_count()
    new_story["pages"] = [
        {**cover, "role": "cover"},
        dedication_page(hero_name, default_location),
        *shifted,
        other_stories_page(other_stories_id, default_location),
        {**back_cover, "role": "back-cover", "text": back_cover_text(), "fixedByDoctrine": True},
    ]

    arc = story.get("narrativeArc")
    if isinstance(arc, Mapping):
        new_story["narrativeArc"] = shift_page_ids(dict(arc), 1)
    personalization = story.get("personalization")
    if isinstance(personalization, Mapping):
        new_story["personalization"] = shift_page_ids(dict(personalization), 1)

    report = {
        "structureId": BOOK_STRUCTURE_ID,
        "pdfPageCount": doctrine_pdf_page_count(),
        "storyPageCount": target,
        "gapPages": gaps,
        "droppedPages": [str(page.get("id")) for page in surplus],
        "requiresStructureExpansion": bool(gaps),
        "messageAr": (
            f"القالب جه بـ{len(middle)} صفحة قصة، والهيكل محتاج {target}. "
            f"اتفتحت {len(gaps)} صفحة فاضية ({'، '.join(gaps)}) لازم تتكتب بإيد — "
            "ممنوع حشو (handoff §3 N3)."
        )
        if gaps
        else "الهيكل مظبوط.",
    }
    return new_story, report


def gap_page_errors(pages: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Block every gate while a declared story hole is still empty."""
    errors: list[dict[str, Any]] = []
    for page in _visible_pages(pages):
        if not page.get(GAP_PAGE_MARKER):
            continue
        errors.append(
            {
                "code": "unwritten-story-page",
                "ruleId": "handoff-7",
                "pageId": str(page.get("id") or ""),
                "message": (
                    f"{page.get('id')} لسه فاضية — اكتبها بإيدك وشيل علامة "
                    f"`{GAP_PAGE_MARKER}`. ممنوع حشو من قصة تانية."
                ),
            }
        )
    return errors
