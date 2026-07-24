#!/usr/bin/env python3
"""Durable state and PDF pipeline for Hekayati client projects.

Tools live in hekaytyworkflow/tools. ALL run data is saved inside the client
project folder only. Cursor skill `hekayati` orchestrates this script.

Images: Codex built-in $imagegen only (via codex-imagegen dispatch). No REST APIs.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
DEFAULT_PDF_PAGES = 24  # front cover + 22 story pages + back cover
MIN_PDF_PAGES = 3  # cover + >=1 story page + back cover
MAX_PDF_PAGES = 40
REVIEWER_ROLES = {"story", "arabic", "continuity", "pdf"}
MAX_ATTEMPTS = 3
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

# One shape for the whole book. The prompt JSON, the Codex dispatch, and the
# PDF page size all read this — they used to disagree, which produced mixed
# aspect ratios that then got stretched onto a single page size.
DEFAULT_ORIENTATION = "landscape"
ORIENTATION_RATIOS = {
    "landscape": 1536 / 1024,
    "portrait": 1024 / 1536,
    "square": 1.0,
}
# Generated images may differ slightly from the requested size; anything past
# this is a real orientation break, not rounding.
ASPECT_TOLERANCE = 0.08

# Banned in $imagegen prompts (describe look instead — see copyright-safe-guests.md).
# Short/ambiguous tokens use word-boundary matching.
FRANCHISE_NAME_BLOCKLIST = (
    "spider-man",
    "spiderman",
    "spider man",
    "batman",
    "superman",
    "wonder woman",
    "iron man",
    "ironman",
    "captain america",
    "mickey mouse",
    "minnie mouse",
    "disney princess",
    "harry potter",
    "hermione",
    "pikachu",
    "pokemon",
    "pokémon",
    "spongebob",
    "sponge bob",
    "cinderella",
    "rapunzel",
    "buzz lightyear",
    "marvel",
    "dc comics",
    "disney",
    "pixar",
    "dreamworks",
)
FRANCHISE_NAME_WORD_BOUNDARY = (
    "elsa",
    "moana",
    "anna",
    "ariel",
    "simba",
    "olaf",
    "woody",
    "shrek",
    "sonic",
    "naruto",
    "goku",
    "totoro",
    "ghibli",
    "barbie",
    "hulk",
    "thor",
    "venom",
    "batgirl",
    "supergirl",
)
# Arabic spellings block just as hard on the image side, and the old Latin-only
# list let every Arabic request straight through. Only distinctive franchise
# strings belong here — never a token that collides with ordinary Arabic
# (e.g. "أنا") or with a real child's name.
FRANCHISE_NAME_ARABIC = (
    "سبايدر مان",
    "سبايدرمان",
    "سبيدر مان",
    "الرجل العنكبوت",
    "رجل العنكبوت",
    "باتمان",
    "الرجل الوطواط",
    "سوبرمان",
    "سوبر مان",
    "الرجل الحديدي",
    "ايرون مان",
    "آيرون مان",
    "كابتن امريكا",
    "كابتن أمريكا",
    "الهالك",
    "مارفل",
    "ديزني",
    "بيكسار",
    "ميكي ماوس",
    "ميكي موس",
    "توم وجيري",
    "سبونج بوب",
    "بن تن",
    "السنافر",
    "هاري بوتر",
    "بوكيمون",
    "بيكاتشو",
    "فروزن",
    "إلسا",
    "الملكة إلسا",
    "سندريلا",
    "ياسمين وعلاء الدين",
    "الأميرة سندريلا",
    "سيمبا",
    "الأسد الملك",
    "ملك الغابة سيمبا",
    "سونيك",
    "ناروتو",
    "دراغون بول",
    "باربي",
)
STORY_TEMPLATE_SLOT_TOKENS = {"hero", "companions", "all"}
MAX_TEMPLATE_NOTE_CHARS = 4000

# Story language is selected by the child's exact target age. The catalog is
# deliberately data-driven: writers can grow the Egyptian-Arabic dictionaries
# without hiding language policy in Python.
STORY_LANGUAGE_SCHEMA_VERSION = 1
ARABIC_DIACRITICS_RE = re.compile(r"[\u064b-\u065f\u0670\u06d6-\u06ed]")
ARABIC_WORD_RE = re.compile(r"[\u0621-\u063a\u0641-\u064a\u0660-\u0669]+")
TANWEEN_MARKS = {"\u064b", "\u064c", "\u064d"}
PROTECTED_PHRASE_WORD_LIMITS = {
    "religious-quote": 25,
    "fixed-religious-phrase": 12,
    "scientific-term": 4,
}
CAUSAL_BRIDGE_TERMS = (
    "لأن",
    "عشان",
    "بعد",
    "لما",
    "وبعدين",
    "تاني يوم",
    "وقتها",
    "بسبب",
    "راح",
    "راحت",
    "راحوا",
    "رجع",
    "رجعت",
    "رجعوا",
    "وصل",
    "وصلت",
    "وصلوا",
    "خرج",
    "خرجت",
    "خرجوا",
    "دخل",
    "دخلت",
    "دخلوا",
    "طلع",
    "طلعت",
    "طلعوا",
    "نزل",
    "نزلت",
    "نزلوا",
    "جرى",
    "جريت",
    "جروا",
    "ركب",
    "ركبت",
    "ركبوا",
    "مشي",
    "مشت",
    "مشوا",
    "عدى",
    "عدت",
    "عدوا",
    "اتحرك",
    "اتحركت",
    "اتحركوا",
    "تحرك",
    "تحركت",
    "تحركوا",
)

# Personalization mode. Families describe the child, not a plot: a habit to
# soften, things that must appear, what the kid loves. One book carries one
# habit arc — books that chase three habits at once turn into a lecture.
HABIT_TYPES = {"reduce", "build"}
HABIT_ARC_STAGES = ("setup", "challenge", "turn", "reinforce")
MIN_HABIT_ARC_PAGES = 4
# "يبطل قضم ضوافره" is not drawable. The replacement behaviour is.
MIN_HABIT_TARGET_CHARS = 12
MAX_SECONDARY_HABITS = 3
MAX_TRAITS = 8
MAX_REQUESTS = 12
MAX_PERSONALIZATION_TEXT_CHARS = 400
REQUEST_KINDS = {"place", "thing", "person", "activity", "moment"}
# Generated entries are tagged so a later edit replaces them instead of stacking.
PERSONALIZATION_TAG = "تخصيص:"
PERSONALIZATION_NOTE_TAG = "[تخصيص]"

# A book reuses a small set of places. Each one gets its own locked reference
# sheet, so page 3 and page 17 in the same room actually look like the same
# room. Free-text `setting` per page was why places drifted every page.
MIN_LOCATIONS = 1
MAX_LOCATIONS = 8
MIN_LOCATION_DEFINITION_CHARS = 120

# A thin guest description is the main reason the image model falls back on a
# franchise character it already knows — and then refuses the job.
MIN_GUEST_DESCRIPTION_CHARS = 120

# Mirrors MAX_REFS in codex-imagegen dispatch.py — refs past this are dropped
# by Codex, so identity/place locks must be ordered ahead of style refs.
MAX_CODEX_REFS = 8

# Concurrency ceiling for Codex image sessions. Measured: 20 parallel ref-heavy
# page jobs timed out 20/22; a smaller pool completes the same queue faster.
MAX_CODEX_WORKERS = 6
CODEX_TIMEOUT_BASE_SEC = 900
CODEX_TIMEOUT_CEILING_SEC = 3600

# Covers are generated after the interior so they can match the art that
# actually shipped, instead of setting a look the pages then drift from.
COVER_ASSET_IDS = ("cover", "back-cover")
# How many finished interior pages to show the cover job as look reference.
COVER_SAMPLE_REFS = 2

# Image models weight the head of a prompt heavily and drop the tail. Prompts
# are compiled from structured fields and bounded so nothing important falls
# off the end.
MIN_COMPILED_PROMPT_CHARS = 320
MAX_COMPILED_PROMPT_CHARS = 3600


class WorkflowError(RuntimeError):
    pass


def build_pdf_asset_ids(total_pages: int) -> list[str]:
    """front cover + page-01..page-N + back cover, where total = 2 + N.

    Both covers are generated last (see generation_order) so they can match the
    finished interior instead of setting a look the pages then drift from.
    """
    if total_pages < MIN_PDF_PAGES:
        raise WorkflowError(
            f"pdfPageCount must be >= {MIN_PDF_PAGES} (cover + story + back cover)"
        )
    if total_pages > MAX_PDF_PAGES:
        raise WorkflowError(f"pdfPageCount must be <= {MAX_PDF_PAGES}")
    middle = total_pages - 2
    return ["cover", *[f"page-{i:02d}" for i in range(1, middle + 1)], "back-cover"]


def pdf_ids(book: dict[str, Any]) -> list[str]:
    count = int((book.get("settings") or {}).get("pdfPageCount") or DEFAULT_PDF_PAGES)
    return build_pdf_asset_ids(count)


def location_asset_ids(book: dict[str, Any]) -> list[str]:
    """Location reference sheets registered on this book (empty before lock)."""
    return [
        asset["id"]
        for asset in book.get("assets") or []
        if isinstance(asset, dict)
        and isinstance(asset.get("id"), str)
        and asset["id"].startswith("location-sheet-")
    ]


def location_asset_id(index: int) -> str:
    return f"location-sheet-{index:02d}"


def all_asset_ids(book: dict[str, Any]) -> list[str]:
    return ["character-sheet", *location_asset_ids(book), *pdf_ids(book)]


def require_asset_id(book: dict[str, Any], asset_id: str) -> str:
    allowed = set(all_asset_ids(book))
    if asset_id not in allowed:
        raise WorkflowError(
            f"Unknown asset id {asset_id!r}. Allowed: {', '.join(sorted(allowed))}"
        )
    return asset_id


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def require_absolute(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise WorkflowError(f"{label} must be an absolute path: {path}")
    return path.resolve()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkflowError(f"Expected JSON object in {path}")
    return payload


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_dir(project: Path) -> Path:
    return project / "input"


def output_dir(project: Path) -> Path:
    return project / "output"


def prompts_dir(project: Path) -> Path:
    return input_dir(project) / "prompts"


def style_dir(project: Path) -> Path:
    return input_dir(project) / "style"


def tools_root() -> Path:
    return Path(__file__).resolve().parent.parent


def themes_catalog_path() -> Path:
    return tools_root() / "references" / "themes" / "catalog.json"


def load_themes_catalog() -> dict[str, Any]:
    path = themes_catalog_path()
    catalog = read_json(path)
    themes = catalog.get("themes")
    if not isinstance(themes, dict) or not themes:
        raise WorkflowError(f"Invalid themes catalog (empty themes): {path}")
    return catalog


def get_theme(theme_id: str) -> dict[str, Any]:
    catalog = load_themes_catalog()
    themes = catalog["themes"]
    if theme_id not in themes:
        allowed = ", ".join(sorted(themes))
        raise WorkflowError(f"Unknown themeId {theme_id!r}. Allowed: {allowed}")
    theme = themes[theme_id]
    if not isinstance(theme, dict):
        raise WorkflowError(f"Invalid theme entry for {theme_id!r}")
    return theme


def theme_summary(theme: dict[str, Any]) -> dict[str, Any]:
    """Compact theme row for list-themes / start menus."""
    return {
        "themeId": theme.get("themeId"),
        "label": theme.get("label"),
        "labelAr": theme.get("labelAr"),
        "fingerprint": theme.get("fingerprint"),
        "visualStyle": theme.get("visualStyle"),
        "hasStyleRefs": bool(theme.get("styleRefDir")),
    }


def command_list_themes(args: argparse.Namespace) -> dict[str, Any]:
    """List every art theme from themes/catalog.json for the book-start menu."""
    catalog = load_themes_catalog()
    themes = catalog["themes"]
    rows = [theme_summary(theme) for theme in themes.values() if isinstance(theme, dict)]
    default_id = catalog.get("defaultThemeId")
    return {
        "schemaVersion": catalog.get("schemaVersion"),
        "defaultThemeId": default_id,
        "count": len(rows),
        "themes": rows,
        "nextAction": (
            "Show all themes to the family, then run "
            "apply-theme --project <ABS_CLIENT> --theme <themeId>."
        ),
    }


def guests_catalog_path() -> Path:
    return tools_root() / "references" / "guests" / "catalog.json"


def command_list_guests(args: argparse.Namespace) -> dict[str, Any]:
    """Vetted original guest characters that stand in for franchise requests."""
    catalog = read_json(guests_catalog_path())
    guests = catalog.get("guests")
    if not isinstance(guests, dict) or not guests:
        raise WorkflowError(f"Invalid guests catalog: {guests_catalog_path()}")
    rows = [
        {
            "key": key,
            "id": entry.get("id"),
            "displayName": entry.get("displayName"),
            "wishItSatisfies": entry.get("wishItSatisfies"),
        }
        for key, entry in guests.items()
        if isinstance(entry, dict)
    ]
    return {
        "count": len(rows),
        "guests": rows,
        "nextAction": (
            "When a family asks for a famous character, pick the matching wish "
            "and paste that entry's appearanceNotes verbatim into story.json "
            "guestCharacters[] — never the franchise name."
        ),
    }


def command_show_guest(args: argparse.Namespace) -> dict[str, Any]:
    catalog = read_json(guests_catalog_path())
    guests = catalog.get("guests") or {}
    key = str(args.guest).strip()
    entry = guests.get(key)
    if not isinstance(entry, dict):
        raise WorkflowError(
            f"Unknown guest {key!r}. Known: {', '.join(sorted(guests))}"
        )
    return {"key": key, "guest": entry}


def story_templates_catalog_path() -> Path:
    return tools_root() / "references" / "story-templates" / "catalog.json"


def story_language_catalog_path() -> Path:
    return tools_root() / "references" / "story-language" / "age-profiles.json"


def _validate_language_replacements(entries: Any, label: str) -> None:
    if not isinstance(entries, list):
        raise WorkflowError(f"{label} must be a list")
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise WorkflowError(f"{label}[{index}] must be an object")
        for field in ("term", "useInstead", "reason", "severity"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise WorkflowError(f"{label}[{index}].{field} must be non-empty text")
        term = entry["term"].strip()
        if term in seen:
            raise WorkflowError(f"{label} repeats term {term!r}")
        seen.add(term)
        if entry["severity"] not in {"high", "medium", "low"}:
            raise WorkflowError(
                f"{label}[{index}].severity must be high|medium|low"
            )
        forms = entry.get("forms")
        if forms is not None and (
            not isinstance(forms, list)
            or not forms
            or any(not isinstance(value, str) or not value.strip() for value in forms)
            or len(forms) != len(set(forms))
            or term in forms
        ):
            raise WorkflowError(
                f"{label}[{index}].forms must be unique explicit inflections"
            )


def load_story_language_catalog() -> dict[str, Any]:
    """Load the age-specific Egyptian-Arabic writing contract."""
    path = story_language_catalog_path()
    catalog = read_json(path)
    if catalog.get("schemaVersion") != STORY_LANGUAGE_SCHEMA_VERSION:
        raise WorkflowError(
            f"Unsupported story-language schemaVersion in {path}: "
            f"{catalog.get('schemaVersion')!r}"
        )
    if catalog.get("dialect") != "ar-EG":
        raise WorkflowError(f"story-language dialect must be ar-EG: {path}")
    protected_registry = catalog.get("protectedPhraseRegistry")
    if not isinstance(protected_registry, dict):
        raise WorkflowError("story-language protectedPhraseRegistry must be an object")
    protected_texts: set[str] = set()
    for registry_id, entry in protected_registry.items():
        if (
            not isinstance(registry_id, str)
            or re.fullmatch(r"[a-z0-9][a-z0-9-]*", registry_id) is None
            or not isinstance(entry, dict)
        ):
            raise WorkflowError("Invalid protectedPhraseRegistry entry")
        phrase = entry.get("text")
        kind = entry.get("kind")
        source = entry.get("source")
        limit = PROTECTED_PHRASE_WORD_LIMITS.get(str(kind))
        word_count = len(
            re.findall(
                r"[A-Za-z0-9\u0621-\u063a\u0641-\u064a]+",
                _fold_story_text(phrase),
            )
        )
        if (
            not isinstance(phrase, str)
            or not phrase.strip()
            or phrase in protected_texts
            or limit is None
            or not isinstance(source, str)
            or len(source.strip()) < 12
            or word_count > limit
            or len(phrase) > 200
        ):
            raise WorkflowError(
                f"Invalid protectedPhraseRegistry entry: {registry_id}"
            )
        protected_texts.add(phrase)
    profiles = catalog.get("profiles")
    order = catalog.get("profileOrder")
    stage_order = catalog.get("arcStageOrder")
    if not isinstance(profiles, dict) or not profiles:
        raise WorkflowError(f"story-language catalog has no profiles: {path}")
    if (
        not isinstance(order, list)
        or any(not isinstance(profile_id, str) for profile_id in order)
        or set(order) != set(profiles)
        or len(order) != len(profiles)
    ):
        raise WorkflowError("story-language profileOrder must list every profile once")
    if (
        not isinstance(stage_order, list)
        or not stage_order
        or any(not isinstance(stage, str) or not stage.strip() for stage in stage_order)
        or len(stage_order) != len(set(stage_order))
    ):
        raise WorkflowError("story-language arcStageOrder must be a unique string list")

    shared = catalog.get("sharedEgyptian")
    if not isinstance(shared, dict):
        raise WorkflowError("story-language sharedEgyptian must be an object")
    for field in ("canonicalSpellings", "registerRules"):
        values = shared.get(field)
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value.strip() for value in values)
            or len(values) != len(set(values))
        ):
            raise WorkflowError(f"sharedEgyptian.{field} must be unique text")
    lexicalized_tanween = shared.get("lexicalizedTanweenWords")
    if (
        not isinstance(lexicalized_tanween, list)
        or not lexicalized_tanween
        or any(
            not isinstance(value, str)
            or not value.strip()
            or _arabic_word_count(value) != 1
            or not any(mark in value for mark in TANWEEN_MARKS)
            for value in lexicalized_tanween
        )
        or len(lexicalized_tanween) != len(set(lexicalized_tanween))
    ):
        raise WorkflowError(
            "sharedEgyptian.lexicalizedTanweenWords must be unique "
            "one-word lexicalized Egyptian forms"
        )
    _validate_language_replacements(
        shared.get("registerReplacements"),
        "sharedEgyptian.registerReplacements",
    )

    covered_ages: set[int] = set()
    previous_profile: dict[str, Any] | None = None
    for profile_id in order:
        profile = profiles.get(profile_id)
        if not isinstance(profile, dict) or profile.get("id") != profile_id:
            raise WorkflowError(f"Invalid story-language profile: {profile_id}")
        if not isinstance(profile.get("labelAr"), str) or not profile["labelAr"].strip():
            raise WorkflowError(f"{profile_id}.labelAr must be non-empty text")
        min_age = profile.get("minAge")
        max_age = profile.get("maxAge")
        if (
            not isinstance(min_age, int)
            or isinstance(min_age, bool)
            or not isinstance(max_age, int)
            or isinstance(max_age, bool)
            or min_age < 1
            or max_age < min_age
        ):
            raise WorkflowError(f"Invalid age range for story-language {profile_id}")
        if previous_profile is not None and min_age != previous_profile["maxAge"] + 1:
            raise WorkflowError("story-language profileOrder must be age-contiguous")
        ages = set(range(min_age, max_age + 1))
        overlap = covered_ages & ages
        if overlap:
            raise WorkflowError(
                f"Overlapping story-language profiles at ages: "
                f"{', '.join(str(age) for age in sorted(overlap))}"
            )
        covered_ages |= ages
        budget = profile.get("pageBudget")
        if not isinstance(budget, dict):
            raise WorkflowError(f"{profile_id}.pageBudget must be an object")
        for key in (
            "targetMinWords",
            "targetMaxWords",
            "hardMaxWords",
            "recommendedTotalMin",
            "recommendedTotalMax",
        ):
            value = budget.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise WorkflowError(f"{profile_id}.pageBudget.{key} must be >= 0")
        if not (
            budget["targetMinWords"]
            <= budget["targetMaxWords"]
            <= budget["hardMaxWords"]
        ):
            raise WorkflowError(f"Invalid page word budgets for {profile_id}")
        if budget["recommendedTotalMin"] > budget["recommendedTotalMax"]:
            raise WorkflowError(f"Invalid total word budgets for {profile_id}")
        if previous_profile is not None:
            previous_budget = previous_profile["pageBudget"]
            if (
                budget["targetMinWords"] <= previous_budget["targetMinWords"]
                or budget["targetMaxWords"] <= previous_budget["targetMaxWords"]
                or budget["recommendedTotalMin"]
                <= previous_budget["recommendedTotalMin"]
            ):
                raise WorkflowError(
                    "Older story-language profiles must increase normal text density"
                )
        sentence_budget = profile.get("sentenceBudget")
        if not isinstance(sentence_budget, dict):
            raise WorkflowError(f"{profile_id}.sentenceBudget must be an object")
        for key in ("maxSentencesPerPage", "hardMaxWordsPerSentence"):
            value = sentence_budget.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise WorkflowError(
                    f"{profile_id}.sentenceBudget.{key} must be a positive integer"
                )
        required_stages = profile.get("requiredArcStages")
        if (
            not isinstance(required_stages, list)
            or not required_stages
            or any(stage not in stage_order for stage in required_stages)
            or len(required_stages) != len(set(required_stages))
        ):
            raise WorkflowError(f"Invalid requiredArcStages for {profile_id}")
        required_indexes = [stage_order.index(stage) for stage in required_stages]
        if required_indexes != sorted(required_indexes):
            raise WorkflowError(f"Unordered requiredArcStages for {profile_id}")
        style = profile.get("narrativeStyle")
        if not isinstance(style, dict):
            raise WorkflowError(f"{profile_id}.narrativeStyle must be an object")
        for field in ("voice", "pageBeat", "dialogue", "continuity", "ending", "safety"):
            if not isinstance(style.get(field), str) or not style[field].strip():
                raise WorkflowError(
                    f"{profile_id}.narrativeStyle.{field} must be non-empty text"
                )
        lexicon = profile.get("lexicon")
        if not isinstance(lexicon, dict):
            raise WorkflowError(f"{profile_id}.lexicon must be an object")
        preferred = lexicon.get("preferred")
        if (
            not isinstance(preferred, list)
            or not preferred
            or any(not isinstance(value, str) or not value.strip() for value in preferred)
            or len(preferred) != len(set(preferred))
        ):
            raise WorkflowError(f"{profile_id}.lexicon.preferred must be unique text")
        teaching = lexicon.get("teachWithContext")
        if not isinstance(teaching, list):
            raise WorkflowError(f"{profile_id}.lexicon.teachWithContext must be a list")
        teaching_terms: set[str] = set()
        for index, entry in enumerate(teaching, start=1):
            if (
                not isinstance(entry, dict)
                or not isinstance(entry.get("term"), str)
                or not entry["term"].strip()
                or not isinstance(entry.get("contextRule"), str)
                or not entry["contextRule"].strip()
                or entry["term"].strip() in teaching_terms
            ):
                raise WorkflowError(
                    f"{profile_id}.lexicon.teachWithContext[{index}] is invalid"
                )
            teaching_terms.add(entry["term"].strip())
        _validate_language_replacements(
            lexicon.get("avoidOrReplace"),
            f"{profile_id}.lexicon.avoidOrReplace",
        )
        previous_profile = profile
    if covered_ages != set(range(1, 9)):
        raise WorkflowError("story-language profiles must cover every age from 1 to 8")
    return catalog


def get_story_language_profile(target_age: Any) -> dict[str, Any]:
    """Resolve one non-overlapping profile from a concrete age."""
    if isinstance(target_age, bool):
        raise WorkflowError("targetAge must be an integer, not a boolean")
    if isinstance(target_age, int):
        age = target_age
    elif isinstance(target_age, str) and re.fullmatch(r"[0-9]+", target_age.strip()):
        age = int(target_age.strip())
    else:
        raise WorkflowError(f"targetAge must be an integer: {target_age!r}")
    catalog = load_story_language_catalog()
    matches = [
        catalog["profiles"][profile_id]
        for profile_id in catalog["profileOrder"]
        if catalog["profiles"][profile_id]["minAge"]
        <= age
        <= catalog["profiles"][profile_id]["maxAge"]
    ]
    if len(matches) != 1:
        known = ", ".join(
            f"{p['minAge']}-{p['maxAge']}"
            for p in (catalog["profiles"][key] for key in catalog["profileOrder"])
        )
        raise WorkflowError(f"targetAge {age} is outside supported ranges: {known}")
    return matches[0]


def story_language_profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": profile["id"],
        "labelAr": profile.get("labelAr"),
        "minAge": profile["minAge"],
        "maxAge": profile["maxAge"],
        "pageBudget": copy.deepcopy(profile.get("pageBudget") or {}),
        "sentenceBudget": copy.deepcopy(profile.get("sentenceBudget") or {}),
        "requiredArcStages": list(profile.get("requiredArcStages") or []),
        "narrativeStyle": copy.deepcopy(profile.get("narrativeStyle") or {}),
    }


def command_list_age_profiles(_args: argparse.Namespace) -> dict[str, Any]:
    catalog = load_story_language_catalog()
    return {
        "dialect": catalog.get("dialect"),
        "profiles": [
            story_language_profile_summary(catalog["profiles"][profile_id])
            for profile_id in catalog["profileOrder"]
        ],
    }


def command_show_age_profile(args: argparse.Namespace) -> dict[str, Any]:
    profile = get_story_language_profile(args.age)
    return {
        "age": int(args.age),
        "profile": copy.deepcopy(profile),
        "source": str(story_language_catalog_path()),
    }


def load_story_templates_catalog() -> dict[str, Any]:
    """Load and validate the ready-made story-template catalog."""
    path = story_templates_catalog_path()
    catalog = read_json(path)
    if catalog.get("schemaVersion") != 1:
        raise WorkflowError(
            f"Unsupported story-template schemaVersion in {path}: "
            f"{catalog.get('schemaVersion')!r}"
        )
    templates = catalog.get("templates")
    if not isinstance(templates, dict) or not templates:
        raise WorkflowError(f"Invalid story-template catalog (empty templates): {path}")
    if not isinstance(catalog.get("catalogVersion"), int):
        raise WorkflowError(f"Invalid story-template catalogVersion in {path}")
    if catalog.get("defaultTemplateId") not in templates:
        raise WorkflowError(f"Invalid defaultTemplateId in {path}")
    language_catalog = load_story_language_catalog()
    language_profiles = language_catalog["profiles"]
    arc_stage_order = language_catalog["arcStageOrder"]
    if catalog.get("defaultLanguageProfileId") not in language_profiles:
        raise WorkflowError(f"Invalid defaultLanguageProfileId in {path}")
    default_arc = catalog.get("defaultNarrativeArc")
    if not isinstance(default_arc, dict) or not default_arc:
        raise WorkflowError(
            f"story-template catalog needs defaultNarrativeArc: {path}"
        )

    for template_id, template in templates.items():
        if not isinstance(template_id, str) or not template_id.strip():
            raise WorkflowError(f"Invalid story-template id in {path}")
        if not isinstance(template, dict):
            raise WorkflowError(f"Invalid story-template entry {template_id!r}")
        if template.get("templateId") != template_id:
            raise WorkflowError(
                f"story-template key/id mismatch: {template_id!r} != "
                f"{template.get('templateId')!r}"
            )
        for field in ("titleAr", "titleEn", "category", "summaryAr", "purpose"):
            value = template.get(field)
            if not isinstance(value, str) or not value.strip():
                raise WorkflowError(
                    f"story-template {template_id!r} missing non-empty {field}"
                )
        age_range = template.get("ageRange")
        if (
            not isinstance(age_range, dict)
            or not isinstance(age_range.get("min"), int)
            or not isinstance(age_range.get("max"), int)
            or age_range["min"] < 1
            or age_range["max"] < age_range["min"]
        ):
            raise WorkflowError(
                f"story-template {template_id!r} has invalid ageRange"
            )
        source_profile_id = (
            template.get("languageProfileId")
            or catalog.get("defaultLanguageProfileId")
        )
        if source_profile_id not in language_profiles:
            raise WorkflowError(
                f"story-template {template_id!r} has unknown languageProfileId"
            )
        page_count = template.get("pageCount")
        if not isinstance(page_count, int):
            raise WorkflowError(f"story-template {template_id!r} has invalid pageCount")
        expected_ids = build_pdf_asset_ids(page_count)
        pages = template.get("pages")
        if not isinstance(pages, list) or len(pages) != page_count:
            raise WorkflowError(
                f"story-template {template_id!r} must contain exactly "
                f"{page_count} pages"
            )
        actual_ids = [page.get("id") for page in pages if isinstance(page, dict)]
        if actual_ids != expected_ids:
            raise WorkflowError(
                f"story-template {template_id!r} page IDs/order must be: "
                f"{', '.join(expected_ids)}"
            )
        arc = template.get("narrativeArc") or default_arc
        if not isinstance(arc, dict) or not arc:
            raise WorkflowError(
                f"story-template {template_id!r} needs narrativeArc"
            )
        unknown_stages = set(arc) - set(arc_stage_order)
        if unknown_stages:
            raise WorkflowError(
                f"story-template {template_id!r} has unknown narrative stages: "
                f"{', '.join(sorted(unknown_stages))}"
            )
        arc_ids: list[str] = []
        arc_owners: dict[str, list[str]] = {}
        arc_ranges: list[tuple[str, int, int]] = []
        page_positions = {page_id: index for index, page_id in enumerate(expected_ids)}
        for stage, values in arc.items():
            if (
                not isinstance(stage, str)
                or not isinstance(values, list)
                or not values
                or any(not isinstance(value, str) for value in values)
            ):
                raise WorkflowError(
                    f"story-template {template_id!r} has invalid narrativeArc.{stage}"
                )
            if len(values) != len(set(values)):
                raise WorkflowError(
                    f"story-template {template_id!r} repeats a page in "
                    f"narrativeArc.{stage}"
                )
            arc_ids.extend(values)
            for value in values:
                arc_owners.setdefault(value, []).append(stage)
        missing_arc_pages = set(expected_ids[1:]) - set(arc_ids)
        unknown_arc_pages = set(arc_ids) - set(expected_ids[1:])
        if missing_arc_pages or unknown_arc_pages:
            raise WorkflowError(
                f"story-template {template_id!r} narrativeArc mismatch; missing="
                f"{sorted(missing_arc_pages)}, unknown={sorted(unknown_arc_pages)}"
            )
        pages_by_id = {page["id"]: page for page in pages if isinstance(page, dict)}
        for page_id, page in pages_by_id.items():
            owners = [
                stage for stage in arc_stage_order if stage in arc_owners.get(page_id, [])
            ]
            has_declaration = "combinedArcStages" in page
            declared = page.get("combinedArcStages")
            ordered_owners = [stage for stage in arc_stage_order if stage in owners]
            adjacent_pair = (
                len(ordered_owners) == 2
                and arc_stage_order.index(ordered_owners[1])
                == arc_stage_order.index(ordered_owners[0]) + 1
            )
            if len(ordered_owners) <= 1 and has_declaration:
                raise WorkflowError(
                    f"story-template {template_id!r}/{page_id} has unused "
                    "combinedArcStages"
                )
            if len(ordered_owners) > 1 and (
                not adjacent_pair
                or not isinstance(declared, list)
                or declared != ordered_owners
                or len(declared) != len(set(declared))
            ):
                raise WorkflowError(
                    f"story-template {template_id!r}/{page_id} belongs to "
                    "multiple narrative stages without an explicit adjacent pair"
                )
        for stage in arc_stage_order:
            values = arc.get(stage)
            if not values:
                continue
            indexes = [page_positions[value] for value in values]
            if indexes != sorted(indexes):
                raise WorkflowError(
                    f"story-template {template_id!r} has unordered narrativeArc.{stage}"
                )
            arc_ranges.append((stage, min(indexes), max(indexes)))
        for previous_range, current_range in zip(arc_ranges, arc_ranges[1:]):
            if previous_range[2] > current_range[1]:
                raise WorkflowError(
                    f"story-template {template_id!r} narrative stage order breaks "
                    f"between {previous_range[0]} and {current_range[0]}"
                )
        locations = template.get("locations")
        if not isinstance(locations, list) or not MIN_LOCATIONS <= len(locations) <= MAX_LOCATIONS:
            raise WorkflowError(
                f"story-template {template_id!r} needs {MIN_LOCATIONS}-{MAX_LOCATIONS} locations"
            )
        location_ids: set[str] = set()
        for location in locations:
            if not isinstance(location, dict):
                raise WorkflowError(
                    f"story-template {template_id!r} has invalid location entry"
                )
            loc_id = str(location.get("id") or "").strip()
            if not loc_id or loc_id in location_ids:
                raise WorkflowError(
                    f"story-template {template_id!r} has empty/duplicate location id"
                )
            location_ids.add(loc_id)
            if not str(location.get("nameAr") or "").strip():
                raise WorkflowError(
                    f"story-template {template_id!r}/{loc_id} needs nameAr"
                )
            definition = str(location.get("visualDefinition") or "").strip()
            if len(definition) < MIN_LOCATION_DEFINITION_CHARS:
                raise WorkflowError(
                    f"story-template {template_id!r}/{loc_id} visualDefinition "
                    f"needs {MIN_LOCATION_DEFINITION_CHARS}+ chars"
                )
        guests = template.get("guestCharacters") or []
        if not isinstance(guests, list):
            raise WorkflowError(
                f"story-template {template_id!r}.guestCharacters must be a list"
            )
        guest_ids = {
            guest.get("id")
            for guest in guests
            if isinstance(guest, dict) and isinstance(guest.get("id"), str)
        }
        if len(guest_ids) != len(guests):
            raise WorkflowError(
                f"story-template {template_id!r} has invalid/duplicate guest ids"
            )
        for guest in guests:
            for field in ("id", "displayName", "appearanceNotes"):
                value = guest.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise WorkflowError(
                        f"story-template {template_id!r} guest missing "
                        f"non-empty {field}"
                    )
        continuity = template.get("continuity")
        if not isinstance(continuity, dict):
            raise WorkflowError(
                f"story-template {template_id!r}.continuity must be an object"
            )
        for field in ("recurringProps", "avoid"):
            values = continuity.get(field)
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise WorkflowError(
                    f"story-template {template_id!r}.continuity.{field} "
                    "must be a string list"
                )
        palette = continuity.get("palette")
        if not isinstance(palette, str) or not palette.strip():
            raise WorkflowError(
                f"story-template {template_id!r}.continuity.palette must be text"
            )
        for field in ("tagsAr", "mustShow", "avoid"):
            values = template.get(field)
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise WorkflowError(
                    f"story-template {template_id!r}.{field} must be a string list"
                )
        for page in pages:
            if not isinstance(page, dict):
                raise WorkflowError(f"story-template {template_id!r} has invalid page")
            for field in ("text", "beat", "setting", "action"):
                value = page.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise WorkflowError(
                        f"story-template {template_id!r}/{page.get('id')} "
                        f"missing non-empty {field}"
                    )
            slots = page.get("participantSlots")
            if (
                not isinstance(slots, list)
                or not slots
                or any(
                    not isinstance(slot, str) or not slot.strip() for slot in slots
                )
            ):
                raise WorkflowError(
                    f"story-template {template_id!r}/{page.get('id')} "
                    "participantSlots must be a non-empty string list"
                )
            unknown_slots = set(slots) - STORY_TEMPLATE_SLOT_TOKENS
            if unknown_slots:
                raise WorkflowError(
                    f"story-template {template_id!r}/{page.get('id')} has unknown "
                    f"participant slots: {', '.join(sorted(unknown_slots))}"
                )
            page_guests = page.get("guests") or []
            if (
                not isinstance(page_guests, list)
                or any(
                    not isinstance(guest_id, str) or not guest_id.strip()
                    for guest_id in page_guests
                )
                or not set(page_guests) <= guest_ids
            ):
                raise WorkflowError(
                    f"story-template {template_id!r}/{page.get('id')} references "
                    "unknown guests"
                )
            if page.get("locationId") not in location_ids:
                raise WorkflowError(
                    f"story-template {template_id!r}/{page.get('id')} references "
                    f"unknown locationId {page.get('locationId')!r}"
                )
    return catalog


def get_story_template(template_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog = load_story_templates_catalog()
    templates = catalog["templates"]
    if template_id not in templates:
        allowed = ", ".join(templates)
        raise WorkflowError(
            f"Unknown story template {template_id!r}. Allowed: {allowed}"
        )
    return catalog, templates[template_id]


def story_template_summary(template: dict[str, Any]) -> dict[str, Any]:
    return {
        "templateId": template["templateId"],
        "titleAr": resolve_template_text(template["titleAr"], "بطلك"),
        "titleEn": template["titleEn"],
        "category": template["category"],
        "ageRange": template.get("ageRange"),
        "summaryAr": resolve_template_text(template["summaryAr"], "بطلك"),
        "purpose": template["purpose"],
        "tagsAr": template.get("tagsAr") or [],
        "pageCount": template["pageCount"],
    }


def resolve_template_text(value: str, hero_name: str) -> str:
    resolved = value.replace("{{hero}}", hero_name)
    if "{{" in resolved or "}}" in resolved:
        raise WorkflowError(f"Unresolved story-template placeholder in: {value!r}")
    return resolved


def resolve_participant_slots(
    slots: list[str], hero_id: str, companion_ids: list[str], all_ids: list[str]
) -> list[str]:
    resolved: list[str] = []
    for slot in slots:
        ids: list[str]
        if slot == "hero":
            ids = [hero_id]
        elif slot == "companions":
            ids = companion_ids
        elif slot == "all":
            ids = all_ids
        else:  # catalog validation should make this unreachable
            raise WorkflowError(f"Unknown participant slot: {slot}")
        for persona_id in ids:
            if persona_id not in resolved:
                resolved.append(persona_id)
    return resolved or [hero_id]


def normalize_template_note(note: Any) -> str | None:
    if note is None:
        return None
    if not isinstance(note, str):
        raise WorkflowError("Template note must be text")
    value = note.strip()
    if not value:
        return None
    if len(value) > MAX_TEMPLATE_NOTE_CHARS:
        raise WorkflowError(
            f"Template note must be <= {MAX_TEMPLATE_NOTE_CHARS} characters"
        )
    return value


TEMPLATE_SELECTION_STATE_FIELDS = (
    "templateId",
    "titleAr",
    "catalogVersion",
    "appliedAt",
    "customizationNote",
    "targetAge",
    "sourceLanguageProfileId",
    "targetLanguageProfileId",
    "requiresAgeAdaptation",
    "requiresRevision",
    "ageAdaptedAt",
    "customizedAt",
)


def validate_template_selection_integrity(
    story: dict[str, Any],
    book: dict[str, Any],
    brief: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Keep workflow-owned template gates canonical across all three state files."""
    candidates: list[tuple[str, Any]] = [
        ("story.json", story.get("templateSelection")),
        ("book.json", book.get("templateSelection")),
    ]
    if brief is not None:
        candidates.append(("brief.json", brief.get("templateSelection")))
    if not any(isinstance(value, dict) and value.get("templateId") for _, value in candidates):
        return None
    for label, value in candidates:
        if not isinstance(value, dict) or not value.get("templateId"):
            raise WorkflowError(
                f"Template selection state drift: {label} is missing templateSelection"
            )
    canonical = candidates[1][1]
    assert isinstance(canonical, dict)
    for label, value in candidates:
        assert isinstance(value, dict)
        missing = [field for field in TEMPLATE_SELECTION_STATE_FIELDS if field not in value]
        if missing:
            raise WorkflowError(
                "Template selection state drift in "
                f"{label}: missing {', '.join(missing)}. Reapply the template "
                "with --force to repair workflow-owned state."
            )
        mismatched = [
            field
            for field in TEMPLATE_SELECTION_STATE_FIELDS
            if value.get(field) != canonical.get(field)
        ]
        if mismatched:
            raise WorkflowError(
                "Template selection state drift in "
                f"{label}: {', '.join(mismatched)}. Reapply the template or use "
                "the template workflow commands; do not edit gate fields by hand."
            )
    text_fields = (
        "templateId",
        "titleAr",
        "appliedAt",
        "sourceLanguageProfileId",
        "targetLanguageProfileId",
    )
    if any(
        not isinstance(canonical.get(field), str) or not canonical[field].strip()
        for field in text_fields
    ):
        raise WorkflowError("Template selection state has invalid required text")
    if (
        not isinstance(canonical.get("catalogVersion"), int)
        or isinstance(canonical.get("catalogVersion"), bool)
        or canonical["catalogVersion"] < 1
        or not isinstance(canonical.get("targetAge"), int)
        or isinstance(canonical.get("targetAge"), bool)
    ):
        raise WorkflowError("Template selection state has invalid version or targetAge")
    if any(
        not isinstance(canonical.get(field), bool)
        for field in ("requiresAgeAdaptation", "requiresRevision")
    ):
        raise WorkflowError("Template selection revision flags must be booleans")
    note = canonical.get("customizationNote")
    if note is not None and (
        not isinstance(note, str)
        or not note.strip()
        or len(note.strip()) > MAX_TEMPLATE_NOTE_CHARS
    ):
        raise WorkflowError("Template selection customizationNote is invalid")
    for field in ("ageAdaptedAt", "customizedAt"):
        timestamp = canonical.get(field)
        if timestamp is not None and (
            not isinstance(timestamp, str) or not timestamp.strip()
        ):
            raise WorkflowError(f"Template selection {field} is invalid")
    return copy.deepcopy(canonical)


def validate_template_language_target(
    story: dict[str, Any],
    selection: dict[str, Any],
    book: dict[str, Any],
    brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind exact age and resolved profile to immutable template provenance."""
    story_profile = get_story_language_profile(story.get("targetAge"))
    expected_profile_id = selection.get("targetLanguageProfileId")
    source_profile_id = selection.get("sourceLanguageProfileId")
    if not isinstance(expected_profile_id, str) or not expected_profile_id:
        raise WorkflowError("templateSelection missing targetLanguageProfileId")
    if not isinstance(source_profile_id, str) or not source_profile_id:
        raise WorkflowError("templateSelection missing sourceLanguageProfileId")
    known_profiles = load_story_language_catalog()["profiles"]
    if expected_profile_id not in known_profiles or source_profile_id not in known_profiles:
        raise WorkflowError("templateSelection references an unknown language profile")
    if story_profile["id"] != expected_profile_id:
        raise WorkflowError(
            "Template target drift: story.targetAge resolves to "
            f"{story_profile['id']}, expected {expected_profile_id}"
        )
    if story.get("languageProfileId") != expected_profile_id:
        raise WorkflowError(
            "Template target drift: story.languageProfileId must be "
            f"{expected_profile_id}"
        )
    story_age = int(str(story.get("targetAge")).strip())
    if selection.get("targetAge") != story_age:
        raise WorkflowError(
            f"Template target drift: expected exact age {selection.get('targetAge')}, "
            f"found {story_age}"
        )
    if brief is not None:
        brief_profile = get_story_language_profile(brief.get("targetAge"))
        brief_age = int(str(brief.get("targetAge")).strip())
        if brief_age != story_age or brief_profile["id"] != expected_profile_id:
            raise WorkflowError("Template target drift between brief.json and story.json")
        if brief.get("languageProfileId") != expected_profile_id:
            raise WorkflowError(
                f"brief.languageProfileId must be {expected_profile_id}"
            )
    book_profile_id = (book.get("settings") or {}).get("languageProfileId")
    if book_profile_id != expected_profile_id:
        raise WorkflowError(
            f"book.settings.languageProfileId must be {expected_profile_id}"
        )
    adapted = source_profile_id != expected_profile_id
    if not adapted and selection.get("requiresAgeAdaptation"):
        raise WorkflowError("Template incorrectly requests adaptation to its source profile")
    if selection.get("requiresAgeAdaptation") and not selection.get("requiresRevision"):
        raise WorkflowError(
            "Template age adaptation is pending but requiresRevision is false"
        )
    if (
        adapted
        and not selection.get("requiresAgeAdaptation")
        and not selection.get("ageAdaptedAt")
    ):
        raise WorkflowError(
            "Template age adaptation has no durable ageAdaptedAt completion record"
        )
    return story_profile


def load_validated_template_state_if_present(
    project: Path,
    book: dict[str, Any],
    brief: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Guard every pre-lock mutator from canonizing drifted template state."""
    story_path = input_dir(project) / "story.json"
    state_present = any(
        isinstance(value, dict) and value.get("templateId")
        for value in (
            book.get("templateSelection"),
            brief.get("templateSelection"),
        )
    )
    if not state_present:
        if story_path.is_file():
            story = read_json(story_path)
            story_selection = story.get("templateSelection") if isinstance(story, dict) else None
            if isinstance(story_selection, dict) and story_selection.get("templateId"):
                raise WorkflowError(
                    "Template selection state drift: story.json has template state "
                    "that book.json and brief.json do not have"
                )
            return None, story if isinstance(story, dict) else None
        return None, None
    if not story_path.is_file():
        raise WorkflowError(
            "Template selection state drift: input/story.json is missing. "
            "Reapply the template with --force to repair the project."
        )
    story = read_json(story_path)
    if not isinstance(story, dict):
        raise WorkflowError("Template story root must be an object")
    selection = validate_template_selection_integrity(story, book, brief)
    if selection is None:
        raise WorkflowError("Template selection state is missing from story.json")
    validate_template_language_target(story, selection, book, brief)
    return selection, story


def integer_value(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise WorkflowError(f"{label} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise WorkflowError(f"{label} must be an integer: {value!r}") from exc


def template_next_action(book: dict[str, Any], brief: dict[str, Any]) -> str:
    """Describe every remaining gate for an unlocked template story."""
    steps: list[str] = []
    raw_personas = brief.get("personas") or []
    missing_outfits = [
        str(persona.get("displayName") or persona.get("id") or "unknown")
        for persona in raw_personas
        if isinstance(persona, dict) and not persona.get("fixedOutfit")
    ]
    if missing_outfits:
        steps.append(f"confirm fixed outfits for {', '.join(missing_outfits)}")
    selection = book.get("templateSelection") or brief.get("templateSelection") or {}
    if isinstance(selection, dict) and selection.get("requiresRevision"):
        revision_parts: list[str] = []
        if selection.get("customizationNote"):
            revision_parts.append("tailor pages affected by customizationNote")
        if selection.get("requiresAgeAdaptation"):
            revision_parts.append(
                "adapt page copy to "
                f"{selection.get('targetLanguageProfileId')} and run review-story"
            )
        steps.append(
            " and ".join(revision_parts or ["finish the pending template revision"])
            + ", then run complete-template-customization"
        )
    steps.append("run lock-story")
    return "Ready-made story written. " + "; then ".join(steps) + "."


def merge_unique_strings(*groups: Any) -> list[str]:
    merged: list[str] = []
    for group in groups:
        if not isinstance(group, list):
            continue
        for value in group:
            if isinstance(value, str) and value.strip() and value not in merged:
                merged.append(value)
    return merged


def without_strings(group: Any, removals: Any) -> list[str]:
    blocked = {
        value
        for value in removals or []
        if isinstance(value, str) and value.strip()
    }
    return [
        value
        for value in group or []
        if isinstance(value, str) and value.strip() and value not in blocked
    ]


def upsert_template_requirements(
    project: Path, selection: dict[str, Any], *, story_path: str = "input/story.json"
) -> None:
    path = input_dir(project) / "requirements.md"
    existing = path.read_text(encoding="utf-8") if path.is_file() else "# Requirements\n"
    start = "<!-- hekayati-story-template:start -->"
    end = "<!-- hekayati-story-template:end -->"
    note = selection.get("customizationNote")
    note_lines = (
        "\n".join(f"> {line}" for line in str(note).splitlines())
        if note
        else "> مفيش ملاحظة إضافية."
    )
    block = (
        f"{start}\n"
        "## Story template\n\n"
        f"- id: `{selection['templateId']}`\n"
        f"- title: {selection['titleAr']}\n"
        f"- catalogVersion: {selection['catalogVersion']}\n"
        f"- sourceLanguageProfileId: {selection.get('sourceLanguageProfileId')}\n"
        f"- targetLanguageProfileId: {selection.get('targetLanguageProfileId')}\n"
        f"- requiresAgeAdaptation: {str(bool(selection.get('requiresAgeAdaptation'))).lower()}\n"
        f"- requiresRevision: {str(bool(selection.get('requiresRevision'))).lower()}\n"
        f"- readyStory: `{story_path}`\n"
        "- customizationNote:\n\n"
        f"{note_lines}\n"
        f"{end}"
    )
    start_index = existing.find(start)
    end_index = existing.find(end)
    if start_index >= 0 and end_index >= start_index:
        end_index += len(end)
        updated = existing[:start_index].rstrip() + "\n\n" + block + existing[end_index:]
    else:
        updated = existing.rstrip() + "\n\n" + block + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated.rstrip() + "\n", encoding="utf-8")


def update_requirements_page_count(project: Path, page_count: int) -> None:
    path = input_dir(project) / "requirements.md"
    if not path.is_file():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    replaced = False
    updated: list[str] = []
    for line in lines:
        if line.strip().startswith("- pageCount:"):
            updated.append(f"- pageCount: {page_count}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.insert(1 if updated else 0, f"- pageCount: {page_count}")
    path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")


def _persona_ids_for_asset(
    project: Path, book: dict[str, Any], asset_id: str
) -> list[str]:
    """Smart persona selection for refs.

    character-sheet → all personas.
    pages → on-page participants from prompt JSON (fallback: story page /
    all personas if missing).
    """
    personas = book.get("personas") or []
    all_ids = [
        p["id"]
        for p in personas
        if isinstance(p, dict) and isinstance(p.get("id"), str)
    ]
    if not all_ids:
        raise WorkflowError("book.json has no personas — cannot generate with face refs")
    if asset_id == "character-sheet":
        return all_ids
    if asset_id.startswith("location-sheet-"):
        # Empty place, no people — a person here would leak into every page.
        return []

    selected: list[str] = []
    declared = False
    try:
        asset = asset_by_id(book, asset_id)
        path = prompt_file(project, asset)
        if path.is_file():
            payload = load_prompt_payload(path)
            declared = isinstance(payload.get("participants"), list)
            for entry in payload.get("participants") or []:
                if not isinstance(entry, dict):
                    continue
                pid = entry.get("id")
                if not isinstance(pid, str) or pid not in all_ids:
                    continue
                if entry.get("onPage", True) is False:
                    continue
                if pid not in selected:
                    selected.append(pid)
            # Also honor explicit persona-identity inputImages order
            if not selected:
                for entry in payload.get("inputImages") or []:
                    if not isinstance(entry, dict):
                        continue
                    if entry.get("role") != "persona-identity":
                        continue
                    pid = entry.get("personaId")
                    if isinstance(pid, str) and pid in all_ids and pid not in selected:
                        selected.append(pid)
    except WorkflowError:
        selected = []
        declared = False

    # A page that deliberately shows nobody (an empty street, a storm) must not
    # receive persona photos — that is an invitation to paint people into it.
    if declared and not selected:
        return []

    if not selected:
        story_path = book.get("storyPath")
        if isinstance(story_path, str) and story_path.strip():
            story_file = project / story_path
            if story_file.is_file():
                story = read_json(story_file)
                for page in story.get("pages") or []:
                    if not isinstance(page, dict) or page.get("id") != asset_id:
                        continue
                    for pid in page.get("participants") or []:
                        if isinstance(pid, str) and pid in all_ids and pid not in selected:
                            selected.append(pid)
                    break

    return selected or all_ids


def page_location_asset(
    project: Path, book: dict[str, Any], asset_id: str
) -> str | None:
    """Map a story page to its location-sheet asset id via story.json."""
    mapping = book.get("locationAssets")
    if not isinstance(mapping, dict) or not mapping:
        return None
    story_path = book.get("storyPath")
    if not isinstance(story_path, str) or not story_path.strip():
        return None
    story_file = project / story_path
    if not story_file.is_file():
        return None
    story = read_json(story_file)
    for page in story.get("pages") or []:
        if isinstance(page, dict) and page.get("id") == asset_id:
            loc_id = page.get("locationId")
            if isinstance(loc_id, str):
                return mapping.get(loc_id.strip())
            return None
    return None


def collect_asset_refs(
    project: Path, book: dict[str, Any], asset_id: str
) -> list[Path]:
    """Attach persona photos (smart subset) + character-sheet (pages) + style refs.

    Order for story pages: on-page persona photos first (face likeness), then
    accepted character-sheet (illustrated identity / outfit lock), then style refs.
    character-sheet jobs get ALL persona photos.
    Hard-fails if required photos or character-sheet missing for pages.
    """
    refs: list[Path] = []
    seen: set[str] = set()

    def add(path: Path, *, required: bool, label: str) -> None:
        resolved = path.expanduser()
        if not resolved.is_absolute():
            resolved = (project / resolved).resolve()
        else:
            resolved = resolved.resolve()
        key = str(resolved)
        if key in seen:
            return
        if not resolved.is_file():
            if required:
                raise WorkflowError(f"Missing required reference ({label}): {resolved}")
            return
        seen.add(key)
        refs.append(resolved)

    personas = book.get("personas") or []
    if not personas:
        raise WorkflowError("book.json has no personas — cannot generate with face refs")
    by_id = {
        p["id"]: p
        for p in personas
        if isinstance(p, dict) and isinstance(p.get("id"), str)
    }
    needed_ids = _persona_ids_for_asset(project, book, asset_id)
    for pid in needed_ids:
        persona = by_id.get(pid)
        if not persona:
            raise WorkflowError(f"Unknown persona id in prompt/story: {pid}")
        raw = persona.get("imagePath")
        name = persona.get("displayName") or pid
        if not isinstance(raw, str) or not raw.strip():
            raise WorkflowError(f"Persona {name!r} missing imagePath")
        add(Path(raw.strip()), required=True, label=f"persona {name}")

    # Story pages MUST carry the identity + place locks. Order matters: Codex
    # only accepts the first MAX_CODEX_REFS images, so locks come before style.
    is_page = asset_id != "character-sheet" and not asset_id.startswith(
        "location-sheet-"
    )
    if is_page:
        sheet = asset_by_id(book, "character-sheet")
        rel = sheet.get("imagePath")
        if not isinstance(rel, str) or not rel.strip():
            raise WorkflowError(
                "character-sheet image required before generating pages "
                "(pages always use on-page photo(s) + character-sheet as refs)"
            )
        if sheet.get("status") not in {
            "accepted",
            "generated",
            "awaiting_review",
            "complete",
        }:
            raise WorkflowError(
                "character-sheet must be generated/accepted before page refs "
                f"(status={sheet.get('status')!r})"
            )
        add(project / rel, required=True, label="character-sheet")

        location_asset_id_for_page = page_location_asset(project, book, asset_id)
        if location_asset_id_for_page:
            location_asset = asset_by_id(book, location_asset_id_for_page)
            loc_rel = location_asset.get("imagePath")
            if not isinstance(loc_rel, str) or not loc_rel.strip():
                raise WorkflowError(
                    f"{location_asset_id_for_page} image required before generating "
                    f"{asset_id} — generate location sheets first so the place "
                    "stays identical across pages"
                )
            add(
                project / loc_rel,
                required=True,
                label=f"location-sheet ({location_asset_id_for_page})",
            )

        if asset_id in COVER_ASSET_IDS:
            # Covers run last: show them real interior pages so the cover matches
            # the finished book rather than the other way round.
            samples = 0
            for page_id in pdf_ids(book):
                if samples >= COVER_SAMPLE_REFS:
                    break
                if page_id in COVER_ASSET_IDS:
                    continue
                page_rel = asset_by_id(book, page_id).get("imagePath")
                if isinstance(page_rel, str) and page_rel.strip():
                    add(project / page_rel, required=False, label=f"page sample {page_id}")
                    samples += 1

    # Style quality refs (user-provided look target)
    style_root = style_dir(project)
    if style_root.is_dir():
        for path in sorted(style_root.iterdir()):
            if path.suffix.lower() in IMAGE_SUFFIXES and not path.name.startswith("."):
                add(path, required=False, label="style")
    for raw in (book.get("settings") or {}).get("styleRefs") or []:
        if isinstance(raw, str) and raw.strip():
            add(Path(raw.strip()), required=True, label="styleRef")

    if len(refs) < len(needed_ids):
        raise WorkflowError(
            f"Expected at least {len(needed_ids)} persona refs for {asset_id}, "
            f"got {len(refs)}"
        )
    if len(refs) > MAX_CODEX_REFS:
        # Codex silently ignores refs past its cap. Identity and place locks are
        # already first in `refs`, so only style refs get trimmed here.
        locks = len(needed_ids) + (2 if is_page else 0)
        if locks > MAX_CODEX_REFS:
            raise WorkflowError(
                f"{asset_id} needs {locks} identity/place refs but Codex accepts "
                f"only {MAX_CODEX_REFS}. Reduce personas on this page."
            )
        refs = refs[:MAX_CODEX_REFS]
    return refs


def book_orientation(book: dict[str, Any]) -> str:
    raw = (book.get("settings") or {}).get("orientation")
    if isinstance(raw, str) and raw.strip().lower() in ORIENTATION_RATIOS:
        return raw.strip().lower()
    return DEFAULT_ORIENTATION


class ProjectLock:
    """Exclusive lock for commands that generate images into a project.

    Two concurrent runs share book.json and the .tmp-<asset>.png paths, so they
    reconcile each other's half-written outputs. That is how a story page ended
    up holding the cover's artwork.
    """

    def __init__(self, project: Path, label: str) -> None:
        self.path = output_dir(project) / ".pipeline.lock"
        self.label = label
        self.acquired = False

    def __enter__(self) -> "ProjectLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder = "unknown"
            try:
                holder = self.path.read_text(encoding="utf-8").strip()
            except OSError:
                pass
            if not lock_holder_alive(holder):
                self.path.unlink(missing_ok=True)
                return self.__enter__()
            raise WorkflowError(
                f"Another Hekayati run is already working on this project "
                f"({holder}). Wait for it to finish, or delete {self.path} if "
                "you are sure it died."
            ) from None
        with os.fdopen(handle, "w") as fh:
            fh.write(f"pid={os.getpid()} command={self.label} started={now_iso()}")
        self.acquired = True
        return self

    def __exit__(self, *exc: Any) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)


def lock_holder_alive(holder: str) -> bool:
    """True if the pid recorded in a lock file still exists."""
    match = re.search(r"pid=(\d+)", holder or "")
    if not match:
        return False
    try:
        os.kill(int(match.group(1)), 0)
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        return True
    return True


def manifest_path(project: Path) -> Path:
    return output_dir(project) / "book.json"


def load_book(project: Path) -> dict[str, Any]:
    project = require_absolute(project, "project")
    book = read_json(manifest_path(project))
    if book.get("schemaVersion") != SCHEMA_VERSION:
        raise WorkflowError(
            f"Unsupported schemaVersion: {book.get('schemaVersion')!r}"
        )
    return book


def save_book(project: Path, book: dict[str, Any]) -> None:
    book["updatedAt"] = now_iso()
    atomic_json(manifest_path(project), book)


def import_pillow() -> tuple[Any, Any, Any]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise WorkflowError("Pillow is required: python3 -m pip install pillow") from exc
    return Image, ImageDraw, ImageFont


def validate_image(path: Path) -> tuple[int, int, str]:
    Image, _, _ = import_pillow()
    if not path.is_file():
        raise WorkflowError(f"Missing image: {path}")
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        raise WorkflowError(f"Unsupported image extension: {path.suffix}")
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
            image_format = image.format or path.suffix.lstrip(".").upper()
    except Exception as exc:
        raise WorkflowError(f"Invalid image {path}: {exc}") from exc
    if width < 512 or height < 512:
        raise WorkflowError(f"Image is too small ({width}x{height}): {path}")
    return width, height, image_format


def discover_personas(project: Path) -> list[dict[str, Any]]:
    personas_root = project / "personas"
    search_roots = [personas_root] if personas_root.is_dir() else [project]
    found: list[dict[str, Any]] = []
    index = 1
    for root in search_roots:
        for path in sorted(root.iterdir()):
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            if path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            # Skip anything already under input/output if scanning project root
            if root == project and path.name in {"input", "output"}:
                continue
            stem = path.stem.replace("_", " ").replace("-", " ").strip()
            found.append(
                {
                    "id": f"persona-{index:02d}",
                    "displayName": stem.title() if stem.isascii() else stem,
                    "imagePath": str(path.resolve()),
                    "role": "hero" if index == 1 else "companion",
                }
            )
            index += 1
    if not found:
        raise WorkflowError(
            f"No persona images found in {project}/personas or project root"
        )
    return found


def make_asset(asset_id: str, pdf_order: int | None, *, include_in_pdf: bool) -> dict[str, Any]:
    return {
        "id": asset_id,
        "includeInPdf": include_in_pdf,
        "pdfOrder": pdf_order,
        "status": "planned",
        "attempt": 0,
        "promptVersion": 1,
        "promptPath": f"input/prompts/{asset_id}.v01.json",
        "imagePath": None,
        "storyText": None,
        "versions": [],
    }


def rebuild_assets(book: dict[str, Any]) -> list[dict[str, Any]]:
    """Rebuild planned assets for current pdfPageCount (keeps character-sheet if present)."""
    existing = {a["id"]: a for a in book.get("assets", []) if isinstance(a, dict)}
    sheet = existing.get("character-sheet") or make_asset(
        "character-sheet", None, include_in_pdf=False
    )
    assets = [sheet]
    for index, asset_id in enumerate(pdf_ids(book)):
        prev = existing.get(asset_id)
        if prev and prev.get("imagePath"):
            # keep progress if same id still exists
            assets.append(prev)
        else:
            assets.append(make_asset(asset_id, index, include_in_pdf=True))
    return assets


def asset_by_id(book: dict[str, Any], asset_id: str) -> dict[str, Any]:
    for asset in book["assets"]:
        if asset["id"] == asset_id:
            return asset
    raise WorkflowError(f"Unknown asset id: {asset_id}")


def interior_ids(book: dict[str, Any]) -> list[str]:
    return [asset_id for asset_id in pdf_ids(book) if asset_id not in COVER_ASSET_IDS]


def cover_ids(book: dict[str, Any]) -> list[str]:
    return [asset_id for asset_id in pdf_ids(book) if asset_id in COVER_ASSET_IDS]


def generation_order(book: dict[str, Any]) -> list[str]:
    """Interior pages first, covers last — not PDF reading order."""
    return [*interior_ids(book), *cover_ids(book)]


def next_first_pass_asset(book: dict[str, Any]) -> str | None:
    for asset_id in generation_order(book):
        asset = asset_by_id(book, asset_id)
        if not asset.get("imagePath"):
            return asset_id
    return None


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    if not project.is_dir():
        raise WorkflowError(f"Project folder does not exist: {project}")
    if manifest_path(project).exists():
        raise WorkflowError(f"Project already initialized: {project}")

    page_count = int(getattr(args, "pages", DEFAULT_PDF_PAGES) or DEFAULT_PDF_PAGES)
    pdf_asset_ids = build_pdf_asset_ids(page_count)
    story_page_count = page_count - 2

    for path in (
        input_dir(project),
        prompts_dir(project),
        style_dir(project),
        output_dir(project),
        output_dir(project) / "images",
        output_dir(project) / "pdf",
        output_dir(project) / "renders",
        output_dir(project) / "reviews",
        output_dir(project) / "contact-sheets",
    ):
        path.mkdir(parents=True, exist_ok=True)

    personas = discover_personas(project)
    assets = [make_asset("character-sheet", None, include_in_pdf=False)]
    assets.extend(
        make_asset(asset_id, index, include_in_pdf=True)
        for index, asset_id in enumerate(pdf_asset_ids)
    )

    default_target_age = 5
    language_profile = get_story_language_profile(default_target_age)
    brief = {
        "project": str(project),
        "language": "natural Egyptian Arabic",
        "targetAge": default_target_age,
        "languageProfileId": language_profile["id"],
        "purpose": "adventure",
        "pageCount": page_count,
        "title": None,
        "outline": None,
        "personas": [
            {
                **persona,
                "fixedOutfit": None,
            }
            for persona in personas
        ],
        "guestCharacters": [],
        "mustShow": [],
        "avoid": [],
        "personalization": empty_personalization(),
        "themeId": "storybook",
        "visualStyle": "premium whimsical children's storybook digital illustration, magical realism, cinematic lighting",
        "consent": {"confirmed": False, "statement": None},
    }
    atomic_json(input_dir(project) / "brief.json", brief)
    # human-readable interview log lives in the CLIENT project only
    interview_path = input_dir(project) / "interview.md"
    if not interview_path.exists():
        interview_path.write_text(
            "# Interview log\n\n"
            "Agent asks questions here. User answers. When user says ابدأ/start, "
            "fill remaining gaps and continue.\n\n",
            encoding="utf-8",
        )
    requirements_path = input_dir(project) / "requirements.md"
    if not requirements_path.exists():
        requirements_path.write_text(
            "# Requirements\n\n"
            f"- pageCount: {page_count}\n"
            f"- targetAge: {default_target_age}\n"
            f"- languageProfileId: {language_profile['id']}\n"
            "- language: natural Egyptian Arabic\n"
            "- All artifacts stay in this client project (input/ + output/).\n",
            encoding="utf-8",
        )

    book = {
        "schemaVersion": SCHEMA_VERSION,
        "project": str(project),
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
        "status": "interview",
        "settings": {
            "pdfPageCount": page_count,
            "storyPageCount": story_page_count,
            "textInPixels": True,
            "maxAttemptsPerAsset": MAX_ATTEMPTS,
            "promptsAreJson": True,
            "imageProvider": "codex",
            "imageModel": "gpt-image-2",
            "imageBackend": "codex-imagegen",
            "autoReviewAfterDraft": True,
            "parallelPageGeneration": True,
            "orientation": DEFAULT_ORIENTATION,
            "languageProfileId": language_profile["id"],
        },
        "consent": {"confirmed": False, "statement": None, "confirmedAt": None},
        "personas": personas,
        "briefPath": "input/brief.json",
        "interviewPath": "input/interview.md",
        "requirementsPath": "input/requirements.md",
        "storyPath": None,
        "templateSelection": None,
        "assets": assets,
        "review": {
            "status": "not_started",
            "pass": 0,
            "mergedReviewPaths": [],
            "fixQueue": [],
            "manualReview": [],
        },
        "pdf": {
            "draft": {"status": "planned", "path": None, "sha256": None},
            "final": {"status": "planned", "path": None, "sha256": None},
        },
        "nextAsset": None,
        "nextAction": (
            "Choose a ready-made story with list-templates/apply-template, or "
            "interview the user for a custom story (log Q&A in input/interview.md). "
            "Then write/review input/story.json and lock-story."
        ),
    }
    save_book(project, book)
    return {
        "project": str(project),
        "personas": personas,
        "pageCount": page_count,
        "pdfAssetIds": pdf_asset_ids,
        "brief": str(input_dir(project) / "brief.json"),
        "interview": str(interview_path),
        "requirements": str(requirements_path),
        "nextAction": book["nextAction"],
    }


def command_set_pages(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    if book.get("storyPath"):
        raise WorkflowError("Cannot change pageCount after story is locked")
    brief_path = input_dir(project) / "brief.json"
    brief = read_json(brief_path) if brief_path.is_file() else {}
    selection, _story = load_validated_template_state_if_present(
        project, book, brief
    )
    if selection is not None or book.get("status") == "story_template_selected":
        raise WorkflowError(
            "Cannot change pageCount after applying a ready-made template. "
            "Templates own their complete 20-page plan; choose another template "
            "or start a custom story."
        )
    page_count = int(args.pages)
    ids = build_pdf_asset_ids(page_count)
    book["settings"]["pdfPageCount"] = page_count
    book["settings"]["storyPageCount"] = page_count - 2
    book["assets"] = rebuild_assets(book)
    if brief_path.is_file():
        brief["pageCount"] = page_count
        atomic_json(brief_path, brief)
    req_path = input_dir(project) / "requirements.md"
    if req_path.is_file():
        text = req_path.read_text(encoding="utf-8")
        if "- pageCount:" in text:
            lines = []
            for line in text.splitlines():
                if line.strip().startswith("- pageCount:"):
                    lines.append(f"- pageCount: {page_count}")
                else:
                    lines.append(line)
            req_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    book["nextAction"] = (
        f"Page count set to {page_count}. Continue interview or write story.json "
        f"with ids: {', '.join(ids)}"
    )
    save_book(project, book)
    return {
        "pageCount": page_count,
        "pdfAssetIds": ids,
        "nextAction": book["nextAction"],
    }


def command_confirm_consent(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    statement = args.statement.strip()
    if len(statement) < 8:
        raise WorkflowError("Consent statement is too short")
    book["consent"] = {
        "confirmed": True,
        "statement": statement,
        "confirmedAt": now_iso(),
    }
    brief_path = input_dir(project) / "brief.json"
    if not brief_path.is_file():
        raise WorkflowError(f"Missing brief.json: {brief_path}")
    brief = read_json(brief_path)
    load_validated_template_state_if_present(project, book, brief)
    brief["consent"] = {
        "confirmed": True,
        "statement": statement,
    }
    atomic_json(brief_path, brief)
    if book.get("status") == "story_template_selected" and not book.get("storyPath"):
        book["nextAction"] = template_next_action(book, brief)
    else:
        book["nextAction"] = "Finish brief, write input/story.json, then lock-story"
    save_book(project, book)
    return {"consent": "confirmed", "nextAction": book["nextAction"]}


def command_apply_theme(args: argparse.Namespace) -> dict[str, Any]:
    """Set brief/story themeId + visualStyle from catalog; copy theme style refs."""
    project = require_absolute(args.project, "project")
    theme_id = str(args.theme).strip()
    theme = get_theme(theme_id)
    visual_style = theme.get("visualStyle")
    if not isinstance(visual_style, str) or not visual_style.strip():
        raise WorkflowError(f"Theme {theme_id!r} missing visualStyle in catalog")

    brief_path = input_dir(project) / "brief.json"
    if not brief_path.is_file():
        raise WorkflowError(f"Missing brief.json — run init first: {brief_path}")
    brief = read_json(brief_path)
    book_path = output_dir(project) / "book.json"
    book = load_book(project) if book_path.is_file() else None
    validated_story: dict[str, Any] | None = None
    if book is not None:
        _selection, validated_story = load_validated_template_state_if_present(
            project, book, brief
        )
    brief["themeId"] = theme_id
    brief["visualStyle"] = visual_style
    atomic_json(brief_path, brief)

    story_updated = False
    story_path = input_dir(project) / "story.json"
    if story_path.is_file():
        story = validated_story if validated_story is not None else read_json(story_path)
        if not isinstance(story, dict):
            raise WorkflowError("Story root must be an object")
        story["themeId"] = theme_id
        story["visualStyle"] = visual_style
        atomic_json(story_path, story)
        story_updated = True

    copied: list[str] = []
    style_ref_dir = theme.get("styleRefDir")
    style_ref_glob = theme.get("styleRefGlob") or "ref-*"
    if isinstance(style_ref_dir, str) and style_ref_dir.strip():
        src_root = (
            tools_root() / "references" / "themes" / style_ref_dir.strip()
        )
        if not src_root.is_dir():
            raise WorkflowError(f"Theme style ref dir missing: {src_root}")
        dest = style_dir(project)
        dest.mkdir(parents=True, exist_ok=True)
        for src in sorted(src_root.glob(str(style_ref_glob))):
            if not src.is_file() or src.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            target = dest / src.name
            shutil.copy2(src, target)
            copied.append(str(target))

    next_action = (
        f"Paste themes/catalog.json[{theme_id}].style into every prompt; "
        "then validate-prompts"
    )
    if book is not None:
        if book.get("status") == "story_template_selected" and not book.get("storyPath"):
            book["nextAction"] = template_next_action(book, brief)
        else:
            book["nextAction"] = (
                f"Theme {theme_id} applied. Write/update prompts with catalog "
                f"style.medium/finish, then validate-prompts"
            )
        next_action = book["nextAction"]
        save_book(project, book)

    return {
        "themeId": theme_id,
        "visualStyle": visual_style,
        "briefUpdated": True,
        "storyUpdated": story_updated,
        "styleRefsCopied": copied,
        "nextAction": next_action,
    }


def command_list_templates(args: argparse.Namespace) -> dict[str, Any]:
    catalog = load_story_templates_catalog()
    category = str(getattr(args, "category", "") or "").strip().lower()
    templates = [
        story_template_summary(template)
        for template in catalog["templates"].values()
        if not category or str(template.get("category", "")).lower() == category
    ]
    if category and not templates:
        categories = sorted(
            {
                str(template.get("category"))
                for template in catalog["templates"].values()
                if template.get("category")
            }
        )
        raise WorkflowError(
            f"No story templates in category {category!r}. "
            f"Allowed: {', '.join(categories)}"
        )
    return {
        "catalogVersion": catalog.get("catalogVersion"),
        "count": len(templates),
        "templates": templates,
        "nextAction": "Pick a templateId, then run apply-template on an initialized client project.",
    }


def command_show_template(args: argparse.Namespace) -> dict[str, Any]:
    catalog, template = get_story_template(str(args.template).strip())
    return {
        "catalogVersion": catalog.get("catalogVersion"),
        "template": copy.deepcopy(template),
        "nextAction": (
            "Run apply-template --project <ABS_CLIENT> --template "
            f"{template['templateId']} [--note '...']"
        ),
    }


def template_personas(
    brief: dict[str, Any], book: dict[str, Any]
) -> tuple[list[dict[str, Any]], str, list[str]]:
    raw_personas = brief.get("personas") or book.get("personas") or []
    if not isinstance(raw_personas, list) or not raw_personas:
        raise WorkflowError("At least one persona is required before applying a template")
    personas: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_personas, start=1):
        if not isinstance(raw, dict):
            raise WorkflowError("brief.json personas must be objects")
        persona_id = raw.get("id")
        display_name = raw.get("displayName")
        if not isinstance(persona_id, str) or not persona_id.strip():
            raise WorkflowError(f"Persona {index} missing id")
        if persona_id in seen_ids:
            raise WorkflowError(f"Duplicate persona id in brief.json: {persona_id}")
        seen_ids.add(persona_id)
        if not isinstance(display_name, str) or not display_name.strip():
            raise WorkflowError(f"Persona {persona_id!r} missing displayName")
        personas.append(
            {
                "id": persona_id,
                "displayName": display_name.strip(),
                "role": raw.get("role") or ("hero" if index == 1 else "companion"),
                "fixedOutfit": raw.get("fixedOutfit"),
            }
        )
    hero = next((p for p in personas if p.get("role") == "hero"), personas[0])
    companion_ids = [p["id"] for p in personas if p["id"] != hero["id"]]
    return personas, hero["id"], companion_ids


def build_story_from_template(
    *,
    template: dict[str, Any],
    catalog: dict[str, Any],
    brief: dict[str, Any],
    book: dict[str, Any],
    note: str | None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    personas, hero_id, companion_ids = template_personas(brief, book)
    all_ids = [persona["id"] for persona in personas]
    hero = next(persona for persona in personas if persona["id"] == hero_id)
    hero_name = hero["displayName"]
    applied_at = now_iso()
    raw_target_age = brief.get("targetAge")
    if raw_target_age is None or raw_target_age == "":
        raw_target_age = 5
    language_profile = get_story_language_profile(raw_target_age)
    target_age = int(str(raw_target_age).strip())
    age_range = template["ageRange"]
    if not age_range["min"] <= target_age <= age_range["max"]:
        raise WorkflowError(
            f"Template {template['templateId']} supports ages "
            f"{age_range['min']}-{age_range['max']}, not {target_age}. "
            "Choose another template or use the custom-story route."
        )
    source_profile_id = str(
        template.get("languageProfileId")
        or catalog.get("defaultLanguageProfileId")
        or "age-3-5"
    )
    requires_age_adaptation = source_profile_id != language_profile["id"]
    selection = {
        "templateId": template["templateId"],
        "titleAr": resolve_template_text(template["titleAr"], hero_name),
        "catalogVersion": int(catalog.get("catalogVersion") or 1),
        "appliedAt": applied_at,
        "customizationNote": note,
        "targetAge": target_age,
        "sourceLanguageProfileId": source_profile_id,
        "targetLanguageProfileId": language_profile["id"],
        "requiresAgeAdaptation": requires_age_adaptation,
        "requiresRevision": bool(note) or requires_age_adaptation,
        "ageAdaptedAt": None,
        "customizedAt": None,
    }

    guest_characters = copy.deepcopy(template.get("guestCharacters") or [])
    pages: list[dict[str, Any]] = []
    for source_page in template["pages"]:
        page = {
                "id": source_page["id"],
                "text": resolve_template_text(source_page["text"], hero_name),
                "beat": resolve_template_text(source_page["beat"], hero_name),
                "participants": resolve_participant_slots(
                    source_page["participantSlots"],
                    hero_id,
                    companion_ids,
                    all_ids,
                ),
                "guests": list(source_page.get("guests") or []),
                "locationId": source_page.get("locationId"),
                "setting": resolve_template_text(source_page["setting"], hero_name),
                "action": resolve_template_text(source_page["action"], hero_name),
            }
        transition = source_page.get("transitionFromPrevious")
        if isinstance(transition, str) and transition.strip():
            page["transitionFromPrevious"] = resolve_template_text(
                transition, hero_name
            )
        pages.append(page)

    locations = [
        {
            **copy.deepcopy(entry),
            "nameAr": resolve_template_text(str(entry.get("nameAr") or ""), hero_name),
        }
        for entry in template.get("locations") or []
        if isinstance(entry, dict)
    ]

    theme_id = brief.get("themeId") or "storybook"
    theme = get_theme(str(theme_id))
    visual_style = brief.get("visualStyle") or theme["visualStyle"]
    page_count = int(template["pageCount"])
    story = {
        "title": selection["titleAr"],
        "targetAge": target_age,
        "languageProfileId": language_profile["id"],
        "language": brief.get("language") or "natural Egyptian Arabic",
        "themeId": theme_id,
        "visualStyle": visual_style,
        "purpose": template["purpose"],
        "pageCount": page_count,
        "outline": resolve_template_text(template["summaryAr"], hero_name),
        "templateSelection": copy.deepcopy(selection),
        "customizationNote": note,
        "personas": personas,
        "guestCharacters": guest_characters,
        "locations": locations,
        "continuity": copy.deepcopy(template.get("continuity") or {}),
        "narrativeArc": copy.deepcopy(
            template.get("narrativeArc") or catalog.get("defaultNarrativeArc") or {}
        ),
        "pages": pages,
    }
    story["continuity"]["avoid"] = merge_unique_strings(
        story["continuity"].get("avoid"),
        brief.get("avoid"),
        template.get("avoid"),
    )
    # A template writes 20 finished pages; personalization is what makes them
    # this child's pages. Carry it over and reopen the revision gate.
    personalization = brief.get("personalization")
    if not personalization_is_empty(personalization):
        sync_personalization_into_story(story, personalization)
        note = compose_template_note(note, personalization)
        selection["customizationNote"] = note
        selection["requiresRevision"] = True
        story["templateSelection"] = copy.deepcopy(selection)
        story["customizationNote"] = note
    missing_outfits = [
        persona["displayName"] for persona in personas if not persona.get("fixedOutfit")
    ]
    return story, selection, missing_outfits


def command_apply_template(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    catalog, template = get_story_template(str(args.template).strip())
    note = normalize_template_note(getattr(args, "note", None))
    story_path = input_dir(project) / "story.json"

    replacing = story_path.exists() or bool(book.get("storyPath"))
    if replacing and not bool(getattr(args, "force", False)):
        raise WorkflowError(
            f"Story already exists: {story_path}. Use --force only if you intend "
            "to replace the pre-prompt story draft."
        )
    if replacing:
        has_images = any(asset.get("imagePath") for asset in book.get("assets") or [])
        has_prompts = prompts_dir(project).is_dir() and any(
            prompts_dir(project).glob("*.json")
        )
        if has_images or has_prompts:
            raise WorkflowError(
                "Cannot replace a story after prompts/images exist. Start a new client "
                "project or remove those artifacts manually after review."
            )

    brief_path = input_dir(project) / "brief.json"
    if not brief_path.is_file():
        raise WorkflowError(f"Missing brief.json — run init first: {brief_path}")
    brief = read_json(brief_path)
    base_must_show = brief.get("mustShow") or []
    base_avoid = brief.get("avoid") or []
    previous_selection = brief.get("templateSelection")
    if isinstance(previous_selection, dict) and previous_selection.get("templateId"):
        previous_id = str(previous_selection["templateId"])
        try:
            _, previous_template = get_story_template(previous_id)
        except WorkflowError:
            previous_template = {}
        base_must_show = without_strings(
            base_must_show, previous_template.get("mustShow")
        )
        base_avoid = without_strings(base_avoid, previous_template.get("avoid"))
    story, selection, missing_outfits = build_story_from_template(
        template=template,
        catalog=catalog,
        brief=brief,
        book=book,
        note=note,
    )
    source_quality = review_story_quality(story)
    if source_quality["errors"]:
        messages = [issue["message"] for issue in source_quality["errors"][:6]]
        raise WorkflowError(
            f"Story template {template['templateId']} failed its built-in quality "
            "contract: " + "; ".join(messages)
        )

    page_count = int(template["pageCount"])
    previous_page_count = integer_value(
        (book.get("settings") or {}).get("pdfPageCount") or DEFAULT_PDF_PAGES,
        "book.settings.pdfPageCount",
    )
    book["settings"]["pdfPageCount"] = page_count
    book["settings"]["storyPageCount"] = page_count - 2
    book["settings"]["languageProfileId"] = story["languageProfileId"]
    book["assets"] = [make_asset("character-sheet", None, include_in_pdf=False)]
    book["assets"].extend(
        make_asset(asset_id, index, include_in_pdf=True)
        for index, asset_id in enumerate(build_pdf_asset_ids(page_count))
    )
    book["review"] = {
        "status": "not_started",
        "pass": 0,
        "mergedReviewPaths": [],
        "fixQueue": [],
        "manualReview": [],
    }
    book["pdf"] = {
        "draft": {"status": "planned", "path": None, "sha256": None},
        "final": {"status": "planned", "path": None, "sha256": None},
    }

    brief["pageCount"] = page_count
    brief["languageProfileId"] = story["languageProfileId"]
    brief["title"] = story["title"]
    brief["purpose"] = template["purpose"]
    brief["outline"] = story["outline"]
    note = selection.get("customizationNote")
    brief["templateSelection"] = copy.deepcopy(selection)
    brief["customizationNote"] = note
    brief["guestCharacters"] = copy.deepcopy(story["guestCharacters"])
    brief["mustShow"] = merge_unique_strings(
        base_must_show, template.get("mustShow")
    )
    brief["avoid"] = merge_unique_strings(base_avoid, template.get("avoid"))

    atomic_json(brief_path, brief)
    atomic_json(story_path, story)
    update_requirements_page_count(project, page_count)
    upsert_template_requirements(project, selection)

    book_personas = {
        persona.get("id"): persona
        for persona in book.get("personas") or []
        if isinstance(persona, dict)
    }
    for persona in story["personas"]:
        current = book_personas.get(persona["id"])
        if current:
            current["displayName"] = persona["displayName"]
            current["role"] = persona["role"]
    book["storyPath"] = None
    book["templateSelection"] = copy.deepcopy(selection)
    book["status"] = "story_template_selected"
    book["nextAsset"] = None
    book["nextAction"] = template_next_action(book, brief)
    save_book(project, book)
    return {
        "template": story_template_summary(template),
        "story": str(story_path),
        "pageCount": page_count,
        "pageCountChanged": previous_page_count != page_count,
        "customizationNote": note,
        "sourceLanguageProfileId": selection.get("sourceLanguageProfileId"),
        "targetLanguageProfileId": selection.get("targetLanguageProfileId"),
        "requiresAgeAdaptation": bool(selection.get("requiresAgeAdaptation")),
        "storyQuality": source_quality,
        "missingFixedOutfits": missing_outfits,
        "readyToLock": not missing_outfits and not selection.get("requiresRevision"),
        "nextAction": book["nextAction"],
    }


def command_set_template_note(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    if book.get("storyPath"):
        raise WorkflowError(
            "Cannot change a template note after lock-story. Add revision feedback "
            "through the normal review loop instead."
        )
    note = normalize_template_note(args.note)
    story_path = input_dir(project) / "story.json"
    brief_path = input_dir(project) / "brief.json"
    story = read_json(story_path)
    brief = read_json(brief_path)
    selection = validate_template_selection_integrity(story, book, brief)
    if selection is None:
        raise WorkflowError("Current story was not created from a ready-made template")
    validate_template_language_target(story, selection, book, brief)
    selection["customizationNote"] = note
    selection["requiresRevision"] = bool(note) or bool(
        selection.get("requiresAgeAdaptation")
    )
    selection["customizedAt"] = None
    story["templateSelection"] = copy.deepcopy(selection)
    story["customizationNote"] = note
    brief["templateSelection"] = copy.deepcopy(selection)
    brief["customizationNote"] = note
    atomic_json(story_path, story)
    atomic_json(brief_path, brief)
    upsert_template_requirements(project, selection)
    book["templateSelection"] = copy.deepcopy(selection)
    book["nextAction"] = template_next_action(book, brief)
    save_book(project, book)
    return {
        "templateId": selection["templateId"],
        "customizationNote": note,
        "story": str(story_path),
        "nextAction": book["nextAction"],
    }


def command_complete_template_customization(args: argparse.Namespace) -> dict[str, Any]:
    """Mark a template note incorporated after the agent edits affected pages."""
    project = require_absolute(args.project, "project")
    book = load_book(project)
    if book.get("storyPath"):
        raise WorkflowError("Template customization is already locked")
    story_path = input_dir(project) / "story.json"
    brief_path = input_dir(project) / "brief.json"
    story = read_json(story_path)
    brief = read_json(brief_path)
    selection = validate_template_selection_integrity(story, book, brief)
    if selection is None:
        raise WorkflowError("Current story was not created from a ready-made template")
    validate_template_language_target(story, selection, book, brief)
    if not selection.get("requiresRevision"):
        raise WorkflowError("No pending template revision needs completion")
    quality = review_story_quality(story)
    cross_profile = (
        selection.get("sourceLanguageProfileId")
        != selection.get("targetLanguageProfileId")
    )
    strict_age_issues = strict_template_age_issues(quality) if cross_profile else []
    if quality["errors"] or strict_age_issues:
        reasons = [issue["message"] for issue in quality["errors"][:4]]
        reasons.extend(issue["message"] for issue in strict_age_issues[:4])
        raise WorkflowError(
            "Template revision is not complete: " + "; ".join(reasons)
        )
    if selection.get("requiresAgeAdaptation"):
        selection["requiresAgeAdaptation"] = False
        selection["ageAdaptedAt"] = now_iso()
    selection["requiresRevision"] = False
    selection["customizedAt"] = now_iso()
    story["templateSelection"] = copy.deepcopy(selection)
    brief["templateSelection"] = copy.deepcopy(selection)
    atomic_json(story_path, story)
    atomic_json(brief_path, brief)
    upsert_template_requirements(project, selection)
    book["templateSelection"] = copy.deepcopy(selection)
    book["nextAction"] = template_next_action(book, brief)
    save_book(project, book)
    return {
        "templateId": selection["templateId"],
        "customizationNote": selection["customizationNote"],
        "customizedAt": selection["customizedAt"],
        "ageAdaptedAt": selection.get("ageAdaptedAt"),
        "story": str(story_path),
        "nextAction": book["nextAction"],
    }


# ---------------------------------------------------------------------------
# Personalization mode
#
# Families rarely hand over a plot. They hand over a child: "بيقضم ضوافره لما
# يتوتر", "بيحب الديناصورات", "لازم بيت جدته يظهر". Those were previously dropped
# into a free-text note that nothing enforced, so half of them never reached the
# pages. This block captures them structurally and makes lock-story prove the
# story actually used them.
# ---------------------------------------------------------------------------


def empty_personalization() -> dict[str, Any]:
    return {
        "habitFocus": None,
        "secondaryHabits": [],
        "traits": [],
        "requests": [],
        "updatedAt": None,
    }


def _required_text(value: Any, label: str, minimum: int) -> str:
    if not isinstance(value, str):
        raise WorkflowError(f"{label} must be text")
    text = value.strip()
    if len(text) < minimum:
        raise WorkflowError(
            f"{label} is too thin ({len(text)} chars, need {minimum}+): {text!r}"
        )
    if len(text) > MAX_PERSONALIZATION_TEXT_CHARS:
        raise WorkflowError(
            f"{label} must be <= {MAX_PERSONALIZATION_TEXT_CHARS} characters"
        )
    return text


def _persona_id(value: Any, known: dict[str, str], label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f"{label} must name a persona id")
    persona_id = value.strip()
    if persona_id not in known:
        raise WorkflowError(
            f"{label} {persona_id!r} is not a persona in brief.json. "
            f"Known: {', '.join(sorted(known)) or 'none'}"
        )
    return persona_id


def normalize_habit(value: Any, known: dict[str, str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError(f"{label} must be an object")
    habit_type = str(value.get("type") or "reduce").strip().lower()
    if habit_type not in HABIT_TYPES:
        raise WorkflowError(
            f"{label}.type must be one of {', '.join(sorted(HABIT_TYPES))}"
        )
    habit = {
        "personaId": _persona_id(value.get("personaId"), known, f"{label}.personaId"),
        "habitAr": _required_text(value.get("habitAr"), f"{label}.habitAr", 6),
        "type": habit_type,
        # A book cannot draw "stop biting nails". It can draw the thing the child
        # does instead — so the replacement behaviour is required, not optional.
        "targetBehaviorAr": _required_text(
            value.get("targetBehaviorAr"),
            f"{label}.targetBehaviorAr",
            MIN_HABIT_TARGET_CHARS,
        ),
        "triggerAr": None,
    }
    trigger = value.get("triggerAr")
    if isinstance(trigger, str) and trigger.strip():
        habit["triggerAr"] = _required_text(trigger, f"{label}.triggerAr", 3)
    return habit


def normalize_personalization(
    payload: Any, personas: list[dict[str, Any]]
) -> dict[str, Any]:
    """Validate a raw personalization payload against the project's personas."""
    if not isinstance(payload, dict):
        raise WorkflowError("personalization payload must be a JSON object")
    known = {
        str(persona.get("id")): str(persona.get("displayName") or persona.get("id"))
        for persona in personas
        if isinstance(persona, dict) and persona.get("id")
    }
    if not known:
        raise WorkflowError("No personas in brief.json — run init first")

    result = empty_personalization()

    focus = payload.get("habitFocus")
    if focus not in (None, {}):
        result["habitFocus"] = normalize_habit(focus, known, "habitFocus")

    secondary = payload.get("secondaryHabits") or []
    if not isinstance(secondary, list):
        raise WorkflowError("secondaryHabits must be a list")
    if len(secondary) > MAX_SECONDARY_HABITS:
        raise WorkflowError(
            f"At most {MAX_SECONDARY_HABITS} secondaryHabits. One book changes one "
            "habit well; the rest become background colour, not story arcs."
        )
    if secondary and not result["habitFocus"]:
        raise WorkflowError(
            "secondaryHabits given without a habitFocus. Pick the habit that "
            "matters most as habitFocus — it owns the story arc."
        )
    result["secondaryHabits"] = [
        normalize_habit(entry, known, f"secondaryHabits[{index}]")
        for index, entry in enumerate(secondary)
    ]

    traits = payload.get("traits") or []
    if not isinstance(traits, list):
        raise WorkflowError("traits must be a list")
    if len(traits) > MAX_TRAITS:
        raise WorkflowError(f"At most {MAX_TRAITS} traits")
    for index, entry in enumerate(traits):
        if not isinstance(entry, dict):
            raise WorkflowError(f"traits[{index}] must be an object")
        result["traits"].append(
            {
                "personaId": _persona_id(
                    entry.get("personaId"), known, f"traits[{index}].personaId"
                ),
                "textAr": _required_text(entry.get("textAr"), f"traits[{index}].textAr", 3),
            }
        )

    requests = payload.get("requests") or []
    if not isinstance(requests, list):
        raise WorkflowError("requests must be a list")
    if len(requests) > MAX_REQUESTS:
        raise WorkflowError(
            f"At most {MAX_REQUESTS} requests. Beyond that the book is a checklist, "
            "not a story."
        )
    for index, entry in enumerate(requests):
        if not isinstance(entry, dict):
            raise WorkflowError(f"requests[{index}] must be an object")
        kind = str(entry.get("kind") or "").strip().lower()
        if kind not in REQUEST_KINDS:
            raise WorkflowError(
                f"requests[{index}].kind must be one of {', '.join(sorted(REQUEST_KINDS))}"
            )
        request = {
            "id": f"req-{index + 1:02d}",
            "kind": kind,
            "textAr": _required_text(entry.get("textAr"), f"requests[{index}].textAr", 3),
            "required": entry.get("required", True) is not False,
            "notesAr": None,
        }
        notes = entry.get("notesAr")
        if isinstance(notes, str) and notes.strip():
            request["notesAr"] = _required_text(notes, f"requests[{index}].notesAr", 3)
        result["requests"].append(request)

    result["updatedAt"] = now_iso()
    return result


def personalization_is_empty(value: Any) -> bool:
    if not isinstance(value, dict):
        return True
    return not (
        value.get("habitFocus")
        or value.get("secondaryHabits")
        or value.get("traits")
        or value.get("requests")
    )


def merge_personalization(
    current: Any, incoming: dict[str, Any]
) -> dict[str, Any]:
    """Additive update: incoming habitFocus wins, lists append without duplicates."""
    if personalization_is_empty(current):
        return copy.deepcopy(incoming)
    merged = copy.deepcopy(current)
    merged["habitFocus"] = incoming.get("habitFocus") or merged.get("habitFocus")

    def _extend(key: str, signature) -> None:
        seen = {signature(entry) for entry in merged.get(key) or []}
        combined = list(merged.get(key) or [])
        for entry in incoming.get(key) or []:
            if signature(entry) not in seen:
                seen.add(signature(entry))
                combined.append(entry)
        merged[key] = combined

    _extend("secondaryHabits", lambda e: (e.get("personaId"), e.get("habitAr")))
    _extend("traits", lambda e: (e.get("personaId"), e.get("textAr")))
    _extend("requests", lambda e: (e.get("kind"), e.get("textAr")))

    if len(merged["secondaryHabits"]) > MAX_SECONDARY_HABITS:
        raise WorkflowError(
            f"Merged secondaryHabits exceed {MAX_SECONDARY_HABITS}. "
            "Use --replace to rewrite the block instead."
        )
    if len(merged["requests"]) > MAX_REQUESTS:
        raise WorkflowError(
            f"Merged requests exceed {MAX_REQUESTS}. Use --replace to rewrite the block."
        )
    # Ids are positional, so renumber after any merge.
    for index, request in enumerate(merged["requests"]):
        request["id"] = f"req-{index + 1:02d}"
    merged["updatedAt"] = now_iso()
    return merged


def personalization_must_show(personalization: dict[str, Any]) -> list[str]:
    """Story-side obligations, tagged so a later edit can replace them cleanly."""
    lines: list[str] = []
    focus = personalization.get("habitFocus")
    if focus:
        lines.append(
            f"{PERSONALIZATION_TAG} قوس العادة: {focus['habitAr']} → "
            f"{focus['targetBehaviorAr']} (البطل هو اللي بياخد القرار)"
        )
    for habit in personalization.get("secondaryHabits") or []:
        lines.append(
            f"{PERSONALIZATION_TAG} عادة جانبية تظهر مرة على الأقل: {habit['habitAr']}"
        )
    for trait in personalization.get("traits") or []:
        lines.append(f"{PERSONALIZATION_TAG} صفة الشخصية: {trait['textAr']}")
    for request in personalization.get("requests") or []:
        state = "لازم" if request["required"] else "لو ظبط"
        lines.append(
            f"{PERSONALIZATION_TAG} طلب {request['id']} ({request['kind']}, {state}): "
            f"{request['textAr']}"
        )
    return lines


def personalization_avoid(personalization: dict[str, Any]) -> list[str]:
    if personalization_is_empty(personalization):
        return []
    if not personalization.get("habitFocus") and not personalization.get(
        "secondaryHabits"
    ):
        return []
    # A habit book that shames the child is worse than no book. These bans ride
    # along with any habit work and reach the prompts through continuity.avoid.
    return [
        f"{PERSONALIZATION_TAG} وصف البطل بصفة سلبية (شقي / وحش / كسول)",
        f"{PERSONALIZATION_TAG} عقاب أو تخويف أو سخرية كحل للعادة",
        f"{PERSONALIZATION_TAG} شخص كبير يحل المشكلة بدل البطل",
        f"{PERSONALIZATION_TAG} صفحة وعظ مباشر بدل ما العادة تتحل بالحدث",
    ]


def strip_personalization_strings(group: Any) -> list[str]:
    return [
        value
        for value in group or []
        if isinstance(value, str)
        and value.strip()
        and not value.startswith(PERSONALIZATION_TAG)
    ]


def personalization_note_block(personalization: dict[str, Any]) -> str | None:
    """One Arabic paragraph a template revision pass can act on directly."""
    if personalization_is_empty(personalization):
        return None
    parts: list[str] = []
    focus = personalization.get("habitFocus")
    if focus:
        trigger = f" (بيحصل {focus['triggerAr']})" if focus.get("triggerAr") else ""
        parts.append(
            f"العادة الأساسية: {focus['habitAr']}{trigger}؛ البطل يوصل بنفسه لـ "
            f"{focus['targetBehaviorAr']} على مدار setup → challenge → turn → reinforce."
        )
    for habit in personalization.get("secondaryHabits") or []:
        parts.append(f"عادة جانبية: {habit['habitAr']} → {habit['targetBehaviorAr']}.")
    traits = [trait["textAr"] for trait in personalization.get("traits") or []]
    if traits:
        parts.append("صفات تظهر في التصرفات: " + "، ".join(traits) + ".")
    for request in personalization.get("requests") or []:
        state = "لازم يظهر" if request["required"] else "يظهر لو ظبط"
        note = f" — {request['notesAr']}" if request.get("notesAr") else ""
        parts.append(f"{request['id']} {state}: {request['textAr']}{note}")
    return f"{PERSONALIZATION_NOTE_TAG} " + " ".join(parts)


def compose_template_note(
    existing: str | None, personalization: dict[str, Any]
) -> str | None:
    """Keep the family's own note, refresh only the generated personalization part."""
    manual_lines = [
        line
        for line in str(existing or "").splitlines()
        if not line.strip().startswith(PERSONALIZATION_NOTE_TAG)
    ]
    manual = "\n".join(manual_lines).strip()
    generated = personalization_note_block(personalization)
    combined = "\n".join(part for part in (manual, generated) if part).strip()
    if not combined:
        return None
    if len(combined) > MAX_TEMPLATE_NOTE_CHARS:
        raise WorkflowError(
            f"Template note + personalization exceed {MAX_TEMPLATE_NOTE_CHARS} "
            "characters. Shorten the family note or drop optional requests."
        )
    return combined


def sync_personalization_into_brief(
    brief: dict[str, Any], personalization: dict[str, Any]
) -> None:
    brief["personalization"] = copy.deepcopy(personalization)
    brief["mustShow"] = merge_unique_strings(
        strip_personalization_strings(brief.get("mustShow")),
        personalization_must_show(personalization),
    )
    brief["avoid"] = merge_unique_strings(
        strip_personalization_strings(brief.get("avoid")),
        personalization_avoid(personalization),
    )


def sync_personalization_into_story(
    story: dict[str, Any], personalization: dict[str, Any]
) -> None:
    existing = story.get("personalization")
    arc = existing.get("habitArc") if isinstance(existing, dict) else None
    coverage = existing.get("requestCoverage") if isinstance(existing, dict) else None
    block = copy.deepcopy(personalization)
    block["habitArc"] = arc if isinstance(arc, dict) else None
    block["requestCoverage"] = coverage if isinstance(coverage, dict) else {}
    story["personalization"] = block
    continuity = story.get("continuity")
    if not isinstance(continuity, dict):
        continuity = {}
        story["continuity"] = continuity
    continuity["avoid"] = merge_unique_strings(
        strip_personalization_strings(continuity.get("avoid")),
        personalization_avoid(personalization),
    )


def command_set_personalization(args: argparse.Namespace) -> dict[str, Any]:
    """Record the child's habits, traits, and must-appear requests."""
    project = require_absolute(args.project, "project")
    book = load_book(project)
    if book.get("storyPath"):
        raise WorkflowError(
            "Cannot change personalization after lock-story. Send behaviour fixes "
            "through the review loop instead."
        )
    raw = getattr(args, "json", None)
    file_arg = getattr(args, "file", None)
    if bool(raw) == bool(file_arg):
        raise WorkflowError("Pass exactly one of --json or --file")
    if file_arg:
        payload = read_json(require_absolute(Path(file_arg), "file"))
    else:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"--json is not valid JSON: {exc}") from exc

    brief_path = input_dir(project) / "brief.json"
    if not brief_path.is_file():
        raise WorkflowError(f"Missing brief.json — run init first: {brief_path}")
    brief = read_json(brief_path)
    canonical_selection, validated_story = load_validated_template_state_if_present(
        project, book, brief
    )
    incoming = normalize_personalization(payload, brief.get("personas") or [])
    personalization = (
        incoming
        if getattr(args, "replace", False)
        else merge_personalization(brief.get("personalization"), incoming)
    )
    sync_personalization_into_brief(brief, personalization)

    story_path = input_dir(project) / "story.json"
    selection_out: dict[str, Any] | None = None
    if story_path.is_file():
        story = validated_story if validated_story is not None else read_json(story_path)
        if not isinstance(story, dict):
            raise WorkflowError("Story root must be an object")
        sync_personalization_into_story(story, personalization)
        selection = canonical_selection
        if selection is not None:
            note = compose_template_note(
                selection.get("customizationNote"), personalization
            )
            selection["customizationNote"] = note
            # New personalization means the pre-written template pages no longer
            # match the child. Reuse the existing revision gate.
            selection["requiresRevision"] = True
            selection["customizedAt"] = None
            story["templateSelection"] = copy.deepcopy(selection)
            story["customizationNote"] = note
            brief["templateSelection"] = copy.deepcopy(selection)
            brief["customizationNote"] = note
            book["templateSelection"] = copy.deepcopy(selection)
            upsert_template_requirements(project, selection)
            selection_out = selection
        atomic_json(story_path, story)
    atomic_json(brief_path, brief)

    book["personalization"] = copy.deepcopy(personalization)
    book["nextAction"] = personalization_next_action(book, brief, personalization)
    save_book(project, book)
    return {
        "personalization": personalization,
        "mustShow": brief["mustShow"],
        "avoid": brief["avoid"],
        "templateSelection": selection_out,
        "nextAction": book["nextAction"],
    }


def personalization_next_action(
    book: dict[str, Any], brief: dict[str, Any], personalization: dict[str, Any]
) -> str:
    selection = book.get("templateSelection") or brief.get("templateSelection") or {}
    steps: list[str] = []
    if personalization.get("habitFocus"):
        steps.append(
            "write story.personalization.habitArc with page ids for setup, "
            "challenge, turn, reinforce"
        )
    required = [r for r in personalization.get("requests") or [] if r.get("required")]
    if required:
        steps.append(
            "map every required request in story.personalization.requestCoverage "
            f"({', '.join(r['id'] for r in required)})"
        )
    if isinstance(selection, dict) and selection.get("requiresRevision"):
        steps.append(
            "tailor the affected template pages then run complete-template-customization"
        )
    steps.append("run lock-story")
    return "Personalization saved. " + "; then ".join(steps) + "."


def command_show_personalization(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    brief_path = input_dir(project) / "brief.json"
    if not brief_path.is_file():
        raise WorkflowError(f"Missing brief.json — run init first: {brief_path}")
    brief = read_json(brief_path)
    personalization = brief.get("personalization") or empty_personalization()
    story_path = input_dir(project) / "story.json"
    story_block = None
    if story_path.is_file():
        story_block = (read_json(story_path) or {}).get("personalization")
    return {
        "personalization": personalization,
        "storyPersonalization": story_block,
        "mustShow": brief.get("mustShow") or [],
        "avoid": brief.get("avoid") or [],
    }


def _arabic_contains(haystack: str, needle: str) -> bool:
    left = normalize_arabic(haystack)
    right = normalize_arabic(needle)
    if not left or not right:
        return False
    return right in left or left in right


def validate_personalization_coverage(
    payload: dict[str, Any], pages: list[dict[str, Any]]
) -> dict[str, Any]:
    """Prove the story actually spent pages on what the family asked for."""
    block = payload.get("personalization")
    if block is not None and not isinstance(block, dict):
        raise WorkflowError("story.personalization must be an object or null")
    if personalization_is_empty(block):
        return {"habitArc": None, "coveredRequests": []}

    page_ids = [str(page["id"]) for page in pages]
    order = {page_id: index for index, page_id in enumerate(page_ids)}
    participants = {
        str(page["id"]): [str(p) for p in page.get("participants") or []]
        for page in pages
    }
    page_locations = {
        str(page["id"]): str(page.get("locationId") or "").strip() for page in pages
    }
    location_ids = {
        str(entry.get("id") or "").strip()
        for entry in payload.get("locations") or []
        if isinstance(entry, dict)
    }

    focus = block.get("habitFocus")
    arc_out: dict[str, list[str]] | None = None
    if focus:
        arc = block.get("habitArc")
        if not isinstance(arc, dict):
            raise WorkflowError(
                "personalization.habitFocus is set but story.personalization.habitArc "
                "is missing. Add {setup, challenge, turn, reinforce} — each a list of "
                "page ids that carries that stage of the habit."
            )
        hero = str(focus["personaId"])
        resolved: dict[str, list[str]] = {}
        for stage in HABIT_ARC_STAGES:
            stage_pages = arc.get(stage)
            if not isinstance(stage_pages, list) or not stage_pages:
                raise WorkflowError(
                    f"habitArc.{stage} needs at least one page id. Stages: "
                    f"{', '.join(HABIT_ARC_STAGES)}."
                )
            cleaned: list[str] = []
            for page_id in stage_pages:
                page_id = str(page_id).strip()
                if page_id not in order:
                    raise WorkflowError(
                        f"habitArc.{stage} references unknown page {page_id!r}"
                    )
                if page_id == "cover":
                    raise WorkflowError(
                        "habitArc cannot use the cover. The cover promises the "
                        "adventure; the habit is worked out on story pages."
                    )
                if hero not in participants.get(page_id, []):
                    raise WorkflowError(
                        f"habitArc.{stage} page {page_id} does not include "
                        f"{hero} in participants — the habit belongs to that child."
                    )
                cleaned.append(page_id)
            resolved[stage] = cleaned

        for earlier, later in zip(HABIT_ARC_STAGES, HABIT_ARC_STAGES[1:]):
            last_earlier = max(order[p] for p in resolved[earlier])
            first_later = min(order[p] for p in resolved[later])
            if last_earlier >= first_later:
                raise WorkflowError(
                    f"habitArc.{earlier} must finish before habitArc.{later} starts "
                    f"({earlier} ends on {page_ids[last_earlier]}, {later} starts on "
                    f"{page_ids[first_later]}). A habit changes in order: shown, "
                    "costs something, the child chooses, it holds."
                )
        used = {page_id for stage_pages in resolved.values() for page_id in stage_pages}
        if len(used) < MIN_HABIT_ARC_PAGES:
            raise WorkflowError(
                f"habitArc covers {len(used)} pages; give it at least "
                f"{MIN_HABIT_ARC_PAGES} so the change is earned, not announced."
            )
        arc_out = resolved

    coverage = block.get("requestCoverage")
    coverage = coverage if isinstance(coverage, dict) else {}
    recurring = [
        str(prop)
        for prop in (payload.get("continuity") or {}).get("recurringProps") or []
    ]
    covered: list[str] = []
    for request in block.get("requests") or []:
        request_id = str(request.get("id"))
        entry = coverage.get(request_id)
        if not request.get("required") and not entry:
            continue
        if not isinstance(entry, dict):
            raise WorkflowError(
                f"story.personalization.requestCoverage[{request_id}] is missing. "
                f"The family asked for {request.get('textAr')!r} — name the pages "
                "that show it: {\"pages\": [\"page-04\"]}."
            )
        entry_pages = [str(p).strip() for p in entry.get("pages") or []]
        unknown = [p for p in entry_pages if p not in order]
        if unknown:
            raise WorkflowError(
                f"requestCoverage[{request_id}].pages has unknown ids: "
                f"{', '.join(unknown)}"
            )
        if not entry_pages:
            raise WorkflowError(
                f"requestCoverage[{request_id}].pages is empty — a request that "
                "appears on no page did not make it into the book."
            )
        if request.get("kind") == "place":
            location_id = str(entry.get("locationId") or "").strip()
            if location_id not in location_ids:
                raise WorkflowError(
                    f"requestCoverage[{request_id}] is a place request "
                    f"({request.get('textAr')!r}) so it needs a locationId from "
                    "locations[] — the place needs its own reference sheet."
                )
            mismatched = [
                page_id
                for page_id in entry_pages
                if page_locations.get(page_id) != location_id
            ]
            if mismatched:
                raise WorkflowError(
                    f"requestCoverage[{request_id}] claims {', '.join(mismatched)} "
                    f"show {location_id}, but those pages are set elsewhere."
                )
        if request.get("kind") == "thing" and request.get("required"):
            if not any(_arabic_contains(prop, str(request["textAr"])) for prop in recurring):
                raise WorkflowError(
                    f"Required thing {request['textAr']!r} is not in "
                    "continuity.recurringProps. A keepsake that changes shape "
                    "between pages reads as a different object."
                )
        covered.append(request_id)
    return {"habitArc": arc_out, "coveredRequests": covered}


def validate_story_locations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Every place the book visits must be defined once and reused by id.

    Returns the locations in declaration order. Raises with a fixable message
    when the bible is missing, thin, or out of sync with the pages.
    """
    raw = payload.get("locations")
    if not isinstance(raw, list) or not raw:
        raise WorkflowError(
            "story.json needs a non-empty locations[] bible. Each entry: "
            "{id, nameAr, visualDefinition}. Pages reference them by locationId "
            "so the same place looks the same on every page."
        )
    if not MIN_LOCATIONS <= len(raw) <= MAX_LOCATIONS:
        raise WorkflowError(
            f"locations[] must hold {MIN_LOCATIONS}-{MAX_LOCATIONS} places, got {len(raw)}. "
            "A picture book reuses a few well-defined places; a new place every "
            "page is what makes the art look disconnected."
        )
    locations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise WorkflowError("Each locations[] entry must be an object")
        loc_id = entry.get("id")
        if not isinstance(loc_id, str) or not loc_id.strip():
            raise WorkflowError("Each locations[] entry needs a string id")
        loc_id = loc_id.strip()
        if loc_id in seen:
            raise WorkflowError(f"Duplicate location id: {loc_id}")
        seen.add(loc_id)
        if not str(entry.get("nameAr") or "").strip():
            raise WorkflowError(f"Location {loc_id} needs an Arabic nameAr")
        definition = str(entry.get("visualDefinition") or "").strip()
        if len(definition) < MIN_LOCATION_DEFINITION_CHARS:
            raise WorkflowError(
                f"Location {loc_id}.visualDefinition is too thin "
                f"({len(definition)} chars, need {MIN_LOCATION_DEFINITION_CHARS}+). "
                "Describe architecture, materials, colors, and 2-3 fixed landmarks "
                "concretely enough to redraw from any angle."
            )
        locations.append(entry)
    return locations


def _fold_story_text(value: Any) -> str:
    text = ARABIC_DIACRITICS_RE.sub("", str(value or ""))
    return (
        text.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ٱ", "ا")
        .replace("ى", "ي")
        .replace("ؤ", "و")
        .replace("ئ", "ي")
    )


def _fold_lexical_text(value: Any) -> str:
    """Fold alef/diacritics while preserving lexical ى/ي/ئ distinctions."""
    text = ARABIC_DIACRITICS_RE.sub("", str(value or ""))
    return (
        text.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ٱ", "ا")
    )


def _arabic_word_count(value: Any) -> int:
    return len(ARABIC_WORD_RE.findall(_fold_story_text(value)))


def _sentence_segments(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in re.split(r"[.!؟?…]+", text) if part.strip()]


def _sentence_count(value: Any) -> int:
    return len(_sentence_segments(value))


def _validated_protected_phrases(
    page: dict[str, Any], catalog: dict[str, Any]
) -> tuple[list[str], list[dict[str, Any]]]:
    """Resolve only centrally reviewed phrases—not arbitrary page-owned bypasses."""
    if "protectedPhrases" not in page or page.get("protectedPhrases") is None:
        return [], []
    raw = page.get("protectedPhrases")
    page_id = str(page.get("id") or "unknown")
    page_text = str(page.get("text") or "")
    if not isinstance(raw, list):
        return [], [
            {
                "code": "invalid-protected-phrase",
                "pageId": page_id,
                "message": f"{page_id}.protectedPhrases must be a list of objects",
            }
        ]
    validated: list[str] = []
    errors: list[dict[str, Any]] = []
    registry = catalog.get("protectedPhraseRegistry") or {}
    for index, entry in enumerate(raw, start=1):
        if (
            not isinstance(entry, dict)
            or set(entry) != {"registryId"}
            or not isinstance(entry.get("registryId"), str)
            or entry["registryId"] not in registry
        ):
            errors.append(
                {
                    "code": "invalid-protected-phrase",
                    "pageId": page_id,
                    "message": (
                        f"{page_id}.protectedPhrases[{index}] needs one approved "
                        "registryId"
                    ),
                }
            )
            continue
        phrase = registry[entry["registryId"]]["text"]
        if (
            page_text.count(phrase) != 1
            or phrase in validated
        ):
            errors.append(
                {
                    "code": "invalid-protected-phrase",
                    "pageId": page_id,
                    "message": (
                        f"{page_id}.protectedPhrases[{index}] does not appear "
                        "exactly once in visible page text"
                    ),
                }
            )
            continue
        validated.append(phrase)
    return validated, errors


def _without_protected_phrases(page: dict[str, Any], protected: list[str]) -> str:
    text = str(page.get("text") or "")
    for phrase in protected:
        text = text.replace(phrase, " ")
    return text


def _without_lexicalized_tanween(
    text: str, catalog: dict[str, Any]
) -> str:
    """Remove only reviewed spoken forms; grammatical case endings still fail."""
    allowed = (
        (catalog.get("sharedEgyptian") or {}).get("lexicalizedTanweenWords") or []
    )
    for word in sorted(allowed, key=len, reverse=True):
        text = re.sub(
            rf"(?<![\u0621-\u063a\u0641-\u064a])"
            rf"[وفبلك]?{re.escape(word)}"
            rf"(?![\u0621-\u063a\u0641-\u064a])",
            " ",
            text,
        )
    return text


def _story_term_present(
    text: str, term: str, *, forms: Iterable[str] | None = None
) -> bool:
    folded_text = _fold_lexical_text(text)
    targets = {
        _fold_lexical_text(value).strip()
        for value in [term, *(forms or [])]
        if isinstance(value, str) and value.strip()
    }
    for target in targets:
        pattern = (
            rf"(?<![\u0621-\u063a\u0641-\u064a])"
            rf"[وفبلك]?{re.escape(target)}"
            rf"(?![\u0621-\u063a\u0641-\u064a])"
        )
        if re.search(pattern, folded_text) is not None:
            return True
    single_targets = {target for target in targets if " " not in target}
    for token in re.findall(r"[\u0621-\u063a\u0641-\u064a]+", folded_text):
        candidate = token
        for _ in range(3):
            if candidate in single_targets:
                return True
            if candidate and candidate[0] in "وفبكل" and len(candidate) > 2:
                candidate = candidate[1:]
            else:
                break
    return False


def _story_term_count(text: str, term: str) -> int:
    folded_text = _fold_lexical_text(text)
    folded_term = _fold_lexical_text(term).strip()
    if not folded_term:
        return 0
    pattern = (
        rf"(?<![\u0621-\u063a\u0641-\u064a])"
        rf"[وفبلك]?{re.escape(folded_term)}"
        rf"(?![\u0621-\u063a\u0641-\u064a])"
    )
    return len(re.findall(pattern, folded_text))


def _language_entries(
    catalog: dict[str, Any], profile: dict[str, Any]
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    shared = catalog.get("sharedEgyptian") or {}
    lexicon = profile.get("lexicon") or {}
    for group in (shared.get("registerReplacements"), lexicon.get("avoidOrReplace")):
        if not isinstance(group, list):
            continue
        for entry in group:
            if isinstance(entry, dict) and str(entry.get("term") or "").strip():
                entries.append(entry)
    return entries


def _story_cast_errors(
    payload: dict[str, Any], pages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Validate declared people and every page reference without throwing TypeError."""
    errors: list[dict[str, Any]] = []
    raw_personas = payload.get("personas")
    personas = raw_personas if isinstance(raw_personas, list) else []
    persona_ids = [
        entry.get("id")
        for entry in personas
        if isinstance(entry, dict)
        and isinstance(entry.get("id"), str)
        and entry.get("id").strip()
    ]
    if len(persona_ids) != len(personas) or len(persona_ids) != len(set(persona_ids)):
        errors.append(
            {
                "code": "invalid-story-personas",
                "message": "story.personas needs unique non-empty string ids",
            }
        )
    heroes = [
        entry
        for entry in personas
        if isinstance(entry, dict) and entry.get("role") == "hero"
    ]
    if len(heroes) != 1:
        errors.append(
            {
                "code": "invalid-story-hero",
                "message": "story.personas needs exactly one role=hero",
            }
        )

    raw_guests = payload.get("guestCharacters") or []
    guests = raw_guests if isinstance(raw_guests, list) else []
    guest_ids = [
        entry.get("id")
        for entry in guests
        if isinstance(entry, dict)
        and isinstance(entry.get("id"), str)
        and entry.get("id").strip()
    ]
    if len(guest_ids) != len(guests) or len(guest_ids) != len(set(guest_ids)):
        errors.append(
            {
                "code": "invalid-story-guests",
                "message": "story.guestCharacters needs unique non-empty string ids",
            }
        )

    known_personas = set(persona_ids)
    known_guests = set(guest_ids)
    for page in pages:
        page_id = str(page.get("id") or "unknown")
        for field, known in (
            ("participants", known_personas),
            ("guests", known_guests),
        ):
            raw_ids = page.get(field) or []
            if (
                not isinstance(raw_ids, list)
                or any(
                    not isinstance(value, str) or not value.strip()
                    for value in raw_ids
                )
                or len(raw_ids) != len(set(raw_ids))
            ):
                errors.append(
                    {
                        "code": f"invalid-page-{field}",
                        "pageId": page_id,
                        "message": (
                            f"{page_id}.{field} must be a unique string-id list"
                        ),
                    }
                )
                continue
            unknown = sorted(set(raw_ids) - known)
            if unknown:
                errors.append(
                    {
                        "code": f"unknown-page-{field}",
                        "pageId": page_id,
                        "ids": unknown,
                        "message": (
                            f"{page_id}.{field} references undeclared ids: "
                            + ", ".join(unknown)
                        ),
                    }
                )
    return errors


def _normalized_beat(value: Any) -> str:
    return " ".join(re.findall(r"[\w]+", _fold_story_text(value), flags=re.UNICODE))


def _normalized_phrase_present(text: str, phrase: str) -> bool:
    text_tokens = text.split()
    phrase_tokens = phrase.split()
    if not phrase_tokens or len(phrase_tokens) > len(text_tokens):
        return False
    width = len(phrase_tokens)
    return any(
        text_tokens[index : index + width] == phrase_tokens
        for index in range(len(text_tokens) - width + 1)
    )


def validate_narrative_arc(
    payload: dict[str, Any],
    pages: list[dict[str, Any]],
    profile: dict[str, Any],
    catalog: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate chronological coverage and the hero-owned causal spine."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    arc = payload.get("narrativeArc")
    if not isinstance(arc, dict):
        return (
            [
                {
                    "code": "missing-narrative-arc",
                    "message": (
                        "story.json needs narrativeArc. Assign every non-cover page "
                        "to ordered stages so disconnected beats cannot hide."
                    ),
                }
            ],
            warnings,
        )

    stage_order = catalog["arcStageOrder"]
    required_stages = profile.get("requiredArcStages") or []
    page_order = {
        str(page.get("id")): index
        for index, page in enumerate(pages)
        if isinstance(page, dict) and page.get("id")
    }
    by_id = {
        str(page.get("id")): page
        for page in pages
        if isinstance(page, dict) and page.get("id") is not None
    }
    cover_id = str(pages[0].get("id")) if pages else "cover"
    story_page_ids = set(page_order) - {cover_id}
    covered: set[str] = set()
    stage_ranges: list[tuple[str, int, int]] = []
    page_owners: dict[str, list[str]] = {}

    unknown_stages = set(arc) - set(stage_order)
    if unknown_stages:
        errors.append(
            {
                "code": "unknown-arc-stage",
                "stages": sorted(unknown_stages),
                "message": f"Unknown narrativeArc stages: {', '.join(sorted(unknown_stages))}",
            }
        )
    for stage in required_stages:
        values = arc.get(stage)
        if not isinstance(values, list) or not values:
            errors.append(
                {
                    "code": "missing-arc-stage",
                    "stage": stage,
                    "message": f"narrativeArc.{stage} needs at least one page id",
                }
            )

    for stage in stage_order:
        values = arc.get(stage)
        if values is None:
            continue
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value.strip() for value in values)
        ):
            errors.append(
                {
                    "code": "invalid-arc-stage",
                    "stage": stage,
                    "message": f"narrativeArc.{stage} must be a non-empty page-id list",
                }
            )
            continue
        if len(values) != len(set(values)):
            errors.append(
                {
                    "code": "duplicate-page-in-arc-stage",
                    "stage": stage,
                    "message": f"narrativeArc.{stage} repeats a page id",
                }
            )
        invalid = [value for value in values if value not in page_order or value == cover_id]
        if invalid:
            errors.append(
                {
                    "code": "invalid-arc-page",
                    "stage": stage,
                    "pageIds": invalid,
                    "message": (
                        f"narrativeArc.{stage} uses missing/cover ids: "
                        f"{', '.join(invalid)}"
                    ),
                }
            )
            continue
        indexes = [page_order[value] for value in values]
        if indexes != sorted(indexes):
            errors.append(
                {
                    "code": "unordered-arc-stage",
                    "stage": stage,
                    "message": f"narrativeArc.{stage} page ids are out of story order",
                }
            )
        covered.update(values)
        for value in values:
            page_owners.setdefault(value, []).append(stage)
        stage_ranges.append((stage, min(indexes), max(indexes)))

    for page_id, page in by_id.items():
        owners = page_owners.get(str(page_id), [])
        has_declaration = "combinedArcStages" in page
        declared = page.get("combinedArcStages")
        adjacent_pair = (
            len(owners) == 2
            and stage_order.index(owners[1]) == stage_order.index(owners[0]) + 1
        )
        if len(owners) <= 1 and has_declaration:
            errors.append(
                {
                    "code": "unused-combined-arc-stages",
                    "pageId": page_id,
                    "message": (
                        f"{page_id}.combinedArcStages is only allowed when that "
                        "page deliberately owns two adjacent stages"
                    ),
                }
            )
        elif len(owners) > 1 and (
            not adjacent_pair
            or not isinstance(declared, list)
            or declared != owners
            or len(declared) != len(set(declared))
        ):
            errors.append(
                {
                    "code": "page-owned-by-multiple-stages",
                    "pageId": page_id,
                    "stages": owners,
                    "message": (
                        f"{page_id} belongs to multiple arc stages: "
                        f"{', '.join(owners)}. Split them, or declare exactly two "
                        "adjacent owners in combinedArcStages."
                    ),
                }
            )

    for previous, current in zip(stage_ranges, stage_ranges[1:]):
        if previous[2] > current[1]:
            errors.append(
                {
                    "code": "arc-stage-overlap",
                    "fromStage": previous[0],
                    "toStage": current[0],
                    "message": (
                        f"narrativeArc order breaks between {previous[0]} and "
                        f"{current[0]}"
                    ),
                }
            )
    missing_pages = sorted(story_page_ids - covered, key=page_order.get)
    if missing_pages:
        errors.append(
            {
                "code": "unassigned-story-pages",
                "pageIds": missing_pages,
                "message": (
                    "Every non-cover page must belong to the causal arc; missing: "
                    + ", ".join(missing_pages)
                ),
            }
        )

    beat_pages: dict[str, list[str]] = {}
    for page in pages:
        page_id = str(page.get("id") or "")
        if not page_id or page_id == cover_id:
            continue
        normalized = _normalized_beat(page.get("beat"))
        if normalized:
            beat_pages.setdefault(normalized, []).append(page_id)
    for duplicate_ids in beat_pages.values():
        if len(duplicate_ids) > 1:
            errors.append(
                {
                    "code": "repeated-story-beat",
                    "pageIds": duplicate_ids,
                    "message": (
                        "Every page needs a distinct causal job; repeated beat on: "
                        + ", ".join(duplicate_ids)
                    ),
                }
            )

    has_refrain_field = (
        "refrainPhrases" in payload and payload.get("refrainPhrases") is not None
    )
    raw_refrains = payload.get("refrainPhrases") if has_refrain_field else []
    allowed_refrain_count = 2 if profile.get("id") == "age-1-2" else 1
    valid_refrains: set[str] = set()
    visible_rows: list[tuple[str, str]] = []
    visible_text_pages: dict[str, list[str]] = {}
    for page in pages:
        page_id = str(page.get("id") or "")
        if not page_id or page_id == cover_id:
            continue
        normalized = _normalized_beat(page.get("text"))
        if normalized:
            visible_rows.append((page_id, normalized))
            visible_text_pages.setdefault(normalized, []).append(page_id)
    if (
        not isinstance(raw_refrains, list)
        or (has_refrain_field and not raw_refrains)
        or len(raw_refrains) > allowed_refrain_count
        or any(not isinstance(value, str) or not value.strip() for value in raw_refrains)
        or len(raw_refrains) != len(set(raw_refrains))
        or (
            all(isinstance(value, str) for value in raw_refrains)
            and len({_normalized_beat(value) for value in raw_refrains})
            != len(raw_refrains)
        )
        or any(
            not 1 <= _arabic_word_count(value) <= 8
            for value in raw_refrains
            if isinstance(value, str)
        )
        or any(
            not _normalized_beat(value)
            for value in raw_refrains
            if isinstance(value, str)
        )
    ):
        errors.append(
            {
                "code": "invalid-refrain-list",
                "message": (
                    f"refrainPhrases allows {allowed_refrain_count} short "
                    "declared phrase(s), each at most 8 words"
                ),
            }
        )
    else:
        valid_refrains = {_normalized_beat(value) for value in raw_refrains}
        max_occurrences = 18 if profile.get("id") == "age-1-2" else 4
        for refrain in valid_refrains:
            matching_pages = [
                page_id
                for page_id, normalized in visible_rows
                if _normalized_phrase_present(normalized, refrain)
            ]
            if not 2 <= len(matching_pages) <= max_occurrences:
                errors.append(
                    {
                        "code": "invalid-refrain-use",
                        "phrase": refrain,
                        "pageIds": matching_pages,
                        "message": (
                            "Every declared refrain must appear inside visible text "
                            f"on 2-{max_occurrences} distinct pages"
                        ),
                    }
                )
    for normalized, duplicate_ids in visible_text_pages.items():
        age_one_refrain = (
            profile.get("id") == "age-1-2" and normalized in valid_refrains
        )
        if len(duplicate_ids) > 1 and not age_one_refrain:
            duplicate_message = (
                "Age 1-2 full-page repetition must exactly equal a valid "
                "declared refrain: "
                if profile.get("id") == "age-1-2"
                else "Ages 3-8 cannot repeat full visible page text, even when "
                "a short refrain is declared: "
            )
            errors.append(
                {
                    "code": "repeated-visible-text",
                    "pageIds": duplicate_ids,
                    "message": duplicate_message + ", ".join(duplicate_ids),
                }
            )
    if profile.get("id") != "age-1-2":
        for index, (left_id, left_text) in enumerate(visible_rows):
            left_words = left_text.split()
            if len(left_words) < 5:
                continue
            for right_id, right_text in visible_rows[index + 1 :]:
                right_words = right_text.split()
                if len(right_words) < 5 or abs(len(left_words) - len(right_words)) > 2:
                    continue
                shorter, longer = sorted(
                    (left_text, right_text), key=lambda value: len(value.split())
                )
                if shorter != longer and _normalized_phrase_present(longer, shorter):
                    errors.append(
                        {
                            "code": "near-duplicate-visible-text",
                            "pageIds": [left_id, right_id],
                            "message": (
                                "Visible page text repeats the same full event with "
                                f"only a tiny wrapper: {left_id}, {right_id}"
                            ),
                        }
                    )

    raw_personas = payload.get("personas")
    personas = [
        p
        for p in (raw_personas if isinstance(raw_personas, list) else [])
        if isinstance(p, dict)
    ]
    hero = next((p for p in personas if p.get("role") == "hero"), {})
    hero_id = hero.get("id")
    for stage in ("choice", "decisiveAction"):
        raw_stage_ids = arc.get(stage)
        stage_ids = raw_stage_ids if isinstance(raw_stage_ids, list) else []
        if stage in required_stages and hero_id and not any(
            hero_id
            in (
                by_id.get(page_id, {}).get("participants")
                if isinstance(by_id.get(page_id, {}).get("participants"), list)
                else []
            )
            for page_id in stage_ids
        ):
            errors.append(
                {
                    "code": "hero-does-not-own-stage",
                    "stage": stage,
                    "heroId": hero_id,
                    "message": f"Hero {hero_id} must act in narrativeArc.{stage}",
                }
            )

    # Any new place or full cast replacement needs a meaningful causal/time
    # bridge. Keeping the hero in frame does not make a home-to-moon teleport
    # coherent by itself.
    for previous, current in zip(pages, pages[1:]):
        if previous.get("id") == cover_id:
            continue
        previous_visible = {
            value
            for field in ("participants", "guests")
            for value in (
                previous.get(field)
                if isinstance(previous.get(field), list)
                else []
            )
            if isinstance(value, str) and value.strip()
        }
        current_visible = {
            value
            for field in ("participants", "guests")
            for value in (
                current.get(field)
                if isinstance(current.get(field), list)
                else []
            )
            if isinstance(value, str) and value.strip()
        }
        changed_place = previous.get("locationId") != current.get("locationId")
        replaced_cast = not previous_visible.intersection(current_visible)
        if not changed_place and not replaced_cast:
            continue
        visible_text = str(current.get("text") or "").strip()
        declared_bridge = str(current.get("transitionFromPrevious") or "").strip()
        bridge = declared_bridge or visible_text
        declared_is_visible = (
            not declared_bridge
            or _normalized_beat(declared_bridge) in _normalized_beat(visible_text)
        )
        bridge_is_meaningful = (
            declared_is_visible
            and
            _arabic_word_count(bridge) >= 3
            and any(
                _story_term_present(bridge, term)
                for term in CAUSAL_BRIDGE_TERMS
            )
        )
        if not bridge_is_meaningful:
            errors.append(
                {
                    "code": "unbridged-scene-cut",
                    "fromPage": previous.get("id"),
                    "toPage": current.get("id"),
                    "message": (
                        f"{current.get('id')} changes place or fully replaces the "
                        "cast; put a real time/cause/movement bridge in the visible "
                        "page text. transitionFromPrevious can only point to words "
                        "that are actually visible."
                    ),
                }
            )
    return errors, warnings


def review_story_quality(
    payload: dict[str, Any], pages: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Age, Egyptian-register, clarity, and narrative continuity review."""
    if not isinstance(payload, dict):
        raise WorkflowError("story.json root must be an object")
    pages = pages if pages is not None else payload.get("pages")
    if not isinstance(pages, list) or not pages:
        raise WorkflowError("story.json needs pages[] before story review")
    if any(not isinstance(page, dict) for page in pages):
        raise WorkflowError("story.json pages[] entries must be objects")
    catalog = load_story_language_catalog()
    profile = get_story_language_profile(payload.get("targetAge"))
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    raw_page_ids = [page.get("id") for page in pages]
    for index, page_id in enumerate(raw_page_ids, start=1):
        if not isinstance(page_id, str) or not page_id.strip():
            errors.append(
                {
                    "code": "invalid-page-id",
                    "pageIndex": index,
                    "message": f"pages[{index}] needs a non-empty string id",
                }
            )
    string_page_ids = [
        page_id for page_id in raw_page_ids if isinstance(page_id, str) and page_id.strip()
    ]
    if len(string_page_ids) != len(set(string_page_ids)):
        errors.append(
            {
                "code": "duplicate-page-id",
                "message": "story.json page ids must be unique",
            }
        )
    errors.extend(_story_cast_errors(payload, pages))

    declared_profile = payload.get("languageProfileId")
    if declared_profile and declared_profile != profile["id"]:
        errors.append(
            {
                "code": "wrong-language-profile",
                "declared": declared_profile,
                "expected": profile["id"],
                "message": (
                    f"targetAge selects {profile['id']}, not {declared_profile}"
                ),
            }
        )
    language = " ".join(str(payload.get("language") or "").split()).lower()
    allowed_languages = {
        "natural egyptian arabic",
        "egyptian arabic",
        "عامية مصرية طبيعية",
        "العامية المصرية الطبيعية",
    }
    if language not in allowed_languages:
        errors.append(
            {
                "code": "wrong-language-register",
                "message": "story.language must explicitly be natural Egyptian Arabic",
            }
        )

    budget = profile.get("pageBudget") or {}
    sentence_budget = profile.get("sentenceBudget") or {}
    hard_words = int(budget.get("hardMaxWords") or 0)
    target_min_words = int(budget.get("targetMinWords") or 0)
    target_max_words = int(budget.get("targetMaxWords") or 0)
    max_sentences_per_page = int(
        sentence_budget.get("maxSentencesPerPage") or 0
    )
    hard_words_per_sentence = int(
        sentence_budget.get("hardMaxWordsPerSentence") or 0
    )
    language_entries = _language_entries(catalog, profile)
    page_stats: list[dict[str, Any]] = []
    total_words = 0
    interior_words = 0
    interior_page_count = 0
    suddenly_pages: list[str] = []

    for page in pages:
        page_id = str(page.get("id") or "unknown")
        raw_text = str(page.get("text") or "")
        protected_phrases, protected_errors = _validated_protected_phrases(
            page, catalog
        )
        errors.extend(protected_errors)
        checked_text = _without_protected_phrases(page, protected_phrases)
        suddenly_pages.extend(
            [page_id] * _story_term_count(checked_text, "فجأة")
        )
        words = _arabic_word_count(raw_text)
        sentence_word_counts = [
            _arabic_word_count(segment) for segment in _sentence_segments(raw_text)
        ]
        sentences = len(sentence_word_counts)
        total_words += words
        is_interior = re.fullmatch(r"page-[0-9]{2}", page_id) is not None
        if is_interior:
            interior_words += words
            interior_page_count += 1
        page_stats.append(
            {
                "pageId": page_id,
                "words": words,
                "sentences": sentences,
                "sentenceWords": sentence_word_counts,
            }
        )
        if is_interior and target_min_words and words < target_min_words:
            warnings.append(
                {
                    "code": "page-below-target",
                    "pageId": page_id,
                    "words": words,
                    "targetMinWords": target_min_words,
                    "message": (
                        f"{page_id} has {words} words; normal target starts at "
                        f"{target_min_words}"
                    ),
                }
            )
        if is_interior and target_max_words and words > target_max_words:
            warnings.append(
                {
                    "code": "page-above-target",
                    "pageId": page_id,
                    "words": words,
                    "targetMaxWords": target_max_words,
                    "message": (
                        f"{page_id} has {words} words; normal target ends at "
                        f"{target_max_words}"
                    ),
                }
            )
        if is_interior and hard_words and words > hard_words:
            errors.append(
                {
                    "code": "page-too-long",
                    "pageId": page_id,
                    "words": words,
                    "hardMaxWords": hard_words,
                    "message": f"{page_id} has {words} words; hard max is {hard_words}",
                }
            )
        if (
            is_interior
            and max_sentences_per_page
            and sentences > max_sentences_per_page
        ):
            errors.append(
                {
                    "code": "too-many-sentences",
                    "pageId": page_id,
                    "sentences": sentences,
                    "hardMax": max_sentences_per_page,
                    "message": (
                        f"{page_id} has {sentences} sentences; hard max is "
                        f"{max_sentences_per_page}"
                    ),
                }
            )
        for sentence_index, sentence_words in enumerate(sentence_word_counts, start=1):
            if (
                is_interior
                and hard_words_per_sentence
                and sentence_words > hard_words_per_sentence
            ):
                errors.append(
                    {
                        "code": "sentence-too-long",
                        "pageId": page_id,
                        "sentence": sentence_index,
                        "words": sentence_words,
                        "hardMaxWords": hard_words_per_sentence,
                        "message": (
                            f"{page_id} sentence {sentence_index} has "
                            f"{sentence_words} words; hard max is "
                            f"{hard_words_per_sentence}"
                        ),
                    }
                )
        tanween_checked_text = _without_lexicalized_tanween(
            checked_text, catalog
        )
        if any(mark in tanween_checked_text for mark in TANWEEN_MARKS):
            errors.append(
                {
                    "code": "formal-case-ending",
                    "pageId": page_id,
                    "message": (
                        f"{page_id} uses tanween case endings in Egyptian narration; "
                        "rewrite naturally or protect an exact quotation"
                    ),
                }
            )
        if re.search(r"[A-Za-z]", checked_text):
            errors.append(
                {
                    "code": "latin-in-story-text",
                    "pageId": page_id,
                    "message": f"{page_id} contains Latin text inside Arabic story copy",
                }
            )
        if ".." in raw_text:
            warnings.append(
                {
                    "code": "loose-ellipsis",
                    "pageId": page_id,
                    "message": f"{page_id} uses repeated dots; use one full stop or …",
                }
            )
        for entry in language_entries:
            term = str(entry.get("term") or "").strip()
            if not _story_term_present(
                checked_text,
                term,
                forms=entry.get("forms") or [],
            ):
                continue
            issue = {
                "code": "age-language-term",
                "pageId": page_id,
                "term": term,
                "useInstead": entry.get("useInstead"),
                "message": (
                    f"{page_id}: replace {term!r} with "
                    f"{entry.get('useInstead') or 'a concrete Egyptian phrase'}"
                ),
            }
            if entry.get("severity") in {"error", "high"}:
                errors.append(issue)
            else:
                warnings.append(issue)

    if len(suddenly_pages) > 1:
        errors.append(
            {
                "code": "suddenly-as-story-glue",
                "pageIds": suddenly_pages,
                "message": (
                    "Use فجأة at most once for a real surprise. Repeated use hides "
                    "missing causal transitions: " + ", ".join(suddenly_pages)
                ),
            }
        )

    recommended_min = int(budget.get("recommendedTotalMin") or 0)
    recommended_max = int(budget.get("recommendedTotalMax") or 0)
    if recommended_min and interior_words < recommended_min:
        warnings.append(
            {
                "code": "story-thinner-than-profile",
                "words": interior_words,
                "recommendedMin": recommended_min,
                "message": (
                    f"Interior story pages have {interior_words} words; "
                    f"{profile['id']} normally starts around {recommended_min}. "
                    "Add only useful action/dialogue, not filler."
                ),
            }
        )
    if recommended_max and interior_words > recommended_max:
        warnings.append(
            {
                "code": "story-denser-than-profile",
                "words": interior_words,
                "recommendedMax": recommended_max,
                "message": (
                    f"Interior story pages have {interior_words} words; "
                    f"{profile['id']} normally tops out around {recommended_max}."
                ),
            }
        )

    arc_errors, arc_warnings = validate_narrative_arc(
        payload, pages, profile, catalog
    )
    errors.extend(arc_errors)
    warnings.extend(arc_warnings)
    return {
        "decision": "pass" if not errors else "revise",
        "targetAge": int(payload.get("targetAge")),
        "languageProfileId": profile["id"],
        "source": str(story_language_catalog_path()),
        "stats": {
            "pages": len(pages),
            "totalWords": total_words,
            "averageWordsPerPage": round(total_words / len(pages), 2),
            "interiorPages": interior_page_count,
            "interiorWords": interior_words,
            "averageWordsPerInteriorPage": (
                round(interior_words / interior_page_count, 2)
                if interior_page_count
                else 0
            ),
            "pageStats": page_stats,
        },
        "errors": errors,
        "warnings": warnings,
    }


def command_review_story(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    source = (
        require_absolute(args.story, "story")
        if getattr(args, "story", None)
        else input_dir(project) / "story.json"
    )
    payload = read_json(source)
    report = review_story_quality(payload)
    report["story"] = str(source)
    return report


STRICT_TEMPLATE_AGE_WARNING_CODES = {
    "page-below-target",
    "page-above-target",
    "story-thinner-than-profile",
    "story-denser-than-profile",
}


def strict_template_age_issues(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Template copy must sit inside the selected profile, not merely under hard caps."""
    return [
        issue
        for issue in report.get("warnings") or []
        if issue.get("code") in STRICT_TEMPLATE_AGE_WARNING_CODES
    ]


def validate_story_persona_sources(
    payload: dict[str, Any], book: dict[str, Any]
) -> None:
    """Every story persona must come from a discovered client image reference."""
    book_ids = {
        entry.get("id")
        for entry in book.get("personas") or []
        if isinstance(entry, dict)
        and isinstance(entry.get("id"), str)
        and entry.get("id").strip()
    }
    story_ids = {
        entry.get("id")
        for entry in payload.get("personas") or []
        if isinstance(entry, dict)
        and isinstance(entry.get("id"), str)
        and entry.get("id").strip()
    }
    unknown = sorted(story_ids - book_ids)
    if unknown:
        raise WorkflowError(
            "story.personas references ids without client image sources: "
            + ", ".join(unknown)
        )


def validate_story_payload(
    payload: dict[str, Any], expected_ids: list[str]
) -> list[dict[str, Any]]:
    required = ("title", "targetAge", "language", "visualStyle", "pages")
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise WorkflowError(f"story.json missing fields: {', '.join(missing)}")
    pages = payload.get("pages")
    if not isinstance(pages, list) or len(pages) != len(expected_ids):
        raise WorkflowError(
            f"story.json must contain exactly {len(expected_ids)} pages "
            f"(pdfPageCount={len(expected_ids)})"
        )
    actual_ids = [page.get("id") for page in pages if isinstance(page, dict)]
    if actual_ids != expected_ids:
        raise WorkflowError(f"Page IDs/order must be: {', '.join(expected_ids)}")
    locations = validate_story_locations(payload)
    location_ids = {str(entry["id"]).strip() for entry in locations}
    used_locations: set[str] = set()
    for page in pages:
        for key in (
            "id",
            "text",
            "beat",
            "participants",
            "guests",
            "locationId",
            "setting",
            "action",
        ):
            if key not in page:
                raise WorkflowError(f"{page.get('id', 'unknown')} missing {key}")
        text = page["text"]
        if not isinstance(text, str) or not text.strip():
            raise WorkflowError(f"{page['id']} must have non-empty in-image Arabic text")
        for field in ("participants", "guests"):
            values = page[field]
            if (
                not isinstance(values, list)
                or any(not isinstance(value, str) or not value.strip() for value in values)
                or len(values) != len(set(values))
            ):
                raise WorkflowError(
                    f"{page['id']}.{field} must be a unique string-id list"
                )
        for key in ("beat", "setting", "action"):
            if not isinstance(page[key], str) or not page[key].strip():
                raise WorkflowError(f"{page['id']}.{key} must be non-empty text")
        loc_id = page["locationId"]
        if not isinstance(loc_id, str) or loc_id.strip() not in location_ids:
            raise WorkflowError(
                f"{page['id']}.locationId {loc_id!r} is not in locations[]. "
                f"Known: {', '.join(sorted(location_ids))}"
            )
        used_locations.add(loc_id.strip())

    unused = location_ids - used_locations
    if unused:
        raise WorkflowError(
            f"locations[] declares places no page uses: {', '.join(sorted(unused))}. "
            "Remove them or assign pages — each one costs a reference-sheet image."
        )
    return pages


def command_lock_story(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    expected_ids = pdf_ids(book)
    source = (
        require_absolute(args.story, "story")
        if args.story
        else input_dir(project) / "story.json"
    )
    payload = read_json(source)
    brief_path = input_dir(project) / "brief.json"
    brief = read_json(brief_path) if brief_path.is_file() else None
    selection = validate_template_selection_integrity(payload, book, brief)
    if selection is not None:
        validate_template_language_target(payload, selection, book, brief)
        template_gates: list[str] = []
        if selection.get("requiresRevision"):
            template_gates.append(
                "revise the customization note and run "
                "complete-template-customization"
            )
        missing_outfits = [
            str(persona.get("displayName") or persona.get("id") or "unknown")
            for persona in payload.get("personas") or []
            if isinstance(persona, dict) and not persona.get("fixedOutfit")
        ]
        if missing_outfits:
            template_gates.append(
                f"set fixed outfits for {', '.join(missing_outfits)} in story.json"
            )
        if template_gates:
            raise WorkflowError(
                "Template story is not ready to lock: "
                + "; then ".join(template_gates)
                + "."
            )
    # If story page count differs and story not conflicting with images, sync settings
    pages_raw = payload.get("pages")
    if selection is not None and isinstance(pages_raw, list):
        _, selected_template = get_story_template(str(selection["templateId"]))
        if len(pages_raw) != int(selected_template["pageCount"]):
            raise WorkflowError(
                "Template story page count drifted from its catalog source; "
                "reapply the template before lock-story"
            )
    if isinstance(pages_raw, list) and len(pages_raw) != len(expected_ids):
        if any(a.get("imagePath") for a in book["assets"] if a.get("includeInPdf")):
            raise WorkflowError(
                "story page count differs from settings but images already exist"
            )
        book["settings"]["pdfPageCount"] = len(pages_raw)
        book["settings"]["storyPageCount"] = max(0, len(pages_raw) - 2)
        book["assets"] = rebuild_assets(book)
        expected_ids = pdf_ids(book)
    pages = validate_story_payload(payload, expected_ids)
    cast_errors = _story_cast_errors(payload, pages)
    if cast_errors:
        raise WorkflowError(
            "Story cast validation failed: "
            + "; ".join(issue["message"] for issue in cast_errors[:8])
        )
    validate_story_persona_sources(payload, book)
    # Surface the most specific user-personalization error first. The broader
    # language/continuity review still runs before anything is locked.
    personalization_report = validate_personalization_coverage(payload, pages)
    selected_profile = get_story_language_profile(payload.get("targetAge"))
    if not payload.get("languageProfileId"):
        payload["languageProfileId"] = selected_profile["id"]
    quality_report = review_story_quality(payload, pages)
    blocking_quality = list(quality_report["errors"])
    if (
        selection is not None
        and selection.get("sourceLanguageProfileId")
        != selection.get("targetLanguageProfileId")
    ):
        blocking_quality.extend(strict_template_age_issues(quality_report))
    if blocking_quality:
        messages = [issue["message"] for issue in blocking_quality[:8]]
        remaining = len(blocking_quality) - len(messages)
        suffix = f"; plus {remaining} more" if remaining > 0 else ""
        raise WorkflowError(
            "Story quality check failed before lock-story: "
            + "; ".join(messages)
            + suffix
            + ". Run review-story for the full report."
        )
    destination = input_dir(project) / "story.json"
    atomic_json(destination, payload)
    for page in pages:
        asset_by_id(book, page["id"])["storyText"] = page["text"]

    # One reference sheet per declared location, inserted right after the
    # character sheet so both are generated before any story page.
    locations = payload.get("locations") or []
    existing = {a["id"]: a for a in book["assets"] if isinstance(a, dict)}
    location_map: dict[str, str] = {}
    location_assets: list[dict[str, Any]] = []
    for index, entry in enumerate(locations, start=1):
        asset_id = location_asset_id(index)
        location_map[str(entry["id"]).strip()] = asset_id
        asset = existing.get(asset_id) or make_asset(
            asset_id, None, include_in_pdf=False
        )
        asset["locationId"] = str(entry["id"]).strip()
        asset["locationNameAr"] = str(entry.get("nameAr") or "").strip()
        location_assets.append(asset)
    book["locationAssets"] = location_map
    book["assets"] = [
        existing.get("character-sheet") or make_asset(
            "character-sheet", None, include_in_pdf=False
        ),
        *location_assets,
        *[asset_by_id(book, asset_id) for asset_id in expected_ids],
    ]
    book["storyPath"] = "input/story.json"
    book["settings"]["languageProfileId"] = quality_report["languageProfileId"]
    book["storyQuality"] = quality_report
    book["status"] = "writing_prompts"
    book["nextAsset"] = "character-sheet"
    prompt_count = len(all_asset_ids(book))
    book["nextAction"] = (
        f"Write {prompt_count} JSON prompts under input/prompts/ "
        f"(character-sheet + {len(location_assets)} location-sheet(s) + "
        f"{len(expected_ids)} story pages that narrate the beats), "
        "validate-prompts, then generate-book-images "
        "(sheets first, then all pages parallel, covers last)"
    )
    save_book(project, book)
    return {
        "story": str(destination),
        "pageCount": len(pages),
        "pdfAssetIds": expected_ids,
        "locationAssets": location_map,
        "habitArc": personalization_report["habitArc"],
        "storyQuality": quality_report,
        "coveredRequests": personalization_report["coveredRequests"],
        "nextAction": book["nextAction"],
    }


def normalize_arabic(text: str) -> str:
    """Fold Arabic spelling variants so أ/إ/آ and ة/ه don't slip past the list."""
    folded = re.sub(r"[ً-ْـ]", "", text)
    for source, target in (
        ("أإآٱ", "ا"),
        ("ى", "ي"),
        ("ة", "ه"),
        ("ؤ", "و"),
        ("ئ", "ي"),
    ):
        for char in source:
            folded = folded.replace(char, target)
    return folded


ARABIC_LETTER = r"ء-ي"
# Arabic attaches prefixes directly to the word, so a bare substring test is
# unusable: folded "إلسا" sits inside ordinary words like "الساحة". Allow the
# common one-letter prefixes, but require a real boundary on the right.
ARABIC_PREFIXES = "وفبلك"


def arabic_name_pattern(name: str) -> str:
    folded = normalize_arabic(name.lower())
    return (
        rf"(?<![{ARABIC_LETTER}])[{ARABIC_PREFIXES}]?"
        rf"{re.escape(folded)}(?![{ARABIC_LETTER}])"
    )


def find_franchise_name_hits(text: str) -> list[str]:
    """Return franchise names found in image-prompt text (Latin + Arabic)."""
    if not isinstance(text, str) or not text.strip():
        return []
    lowered = text.lower()
    hits: list[str] = []
    for name in FRANCHISE_NAME_BLOCKLIST:
        if name in lowered:
            hits.append(name)
    for name in FRANCHISE_NAME_WORD_BOUNDARY:
        if re.search(rf"\b{re.escape(name)}\b", lowered):
            hits.append(name)
    folded = normalize_arabic(lowered)
    for name in FRANCHISE_NAME_ARABIC:
        if re.search(arabic_name_pattern(name), folded):
            hits.append(name)
    return hits


# Everything here reaches the image model, directly or by being copied into
# compiledPrompt. Scanning only compiledPrompt was why Arabic requests and
# scene/beat text kept smuggling franchise names through.
IMAGE_BOUND_PROMPT_FIELDS = (
    "compiledPrompt",
    "narrativeBeat",
    "primaryRequest",
    "spatialStaging",
    "palette",
)
IMAGE_BOUND_SCENE_FIELDS = (
    "place",
    "timeOfDay",
    "atmosphere",
    "lighting",
    "foreground",
    "midground",
    "background",
    "backdropDetails",
)


def scan_prompt_for_franchise_names(payload: dict[str, Any], label: str) -> list[str]:
    """Collect franchise-name failures across every image-bound field."""
    failures: list[str] = []

    def check(text: Any, where: str) -> None:
        hits = find_franchise_name_hits(text if isinstance(text, str) else "")
        if hits:
            failures.append(
                f"franchise name(s) {sorted(set(hits))} in {where} of {label} — "
                "describe the look instead (see copyright-safe-guests.md)"
            )

    for field in IMAGE_BOUND_PROMPT_FIELDS:
        check(payload.get(field), field)

    scene = payload.get("scene") if isinstance(payload.get("scene"), dict) else {}
    for field in IMAGE_BOUND_SCENE_FIELDS:
        check(scene.get(field), f"scene.{field}")
    for index, prop in enumerate(scene.get("propsInFrame") or []):
        check(prop, f"scene.propsInFrame[{index}]")

    for entry in payload.get("participants") or []:
        if isinstance(entry, dict):
            check(entry.get("displayName"), f"participants.{entry.get('id')}.displayName")

    for guest in payload.get("guests") or []:
        if not isinstance(guest, dict):
            continue
        gid = guest.get("id") or "guest"
        check(guest.get("appearanceNotes"), f"guests.{gid}.appearanceNotes")
        check(guest.get("displayName"), f"guests.{gid}.displayName")
        notes = guest.get("appearanceNotes")
        if not isinstance(notes, str) or len(notes.strip()) < MIN_GUEST_DESCRIPTION_CHARS:
            failures.append(
                f"guests.{gid}.appearanceNotes in {label} is too thin "
                f"(need {MIN_GUEST_DESCRIPTION_CHARS}+ chars). A vague guest is "
                "what makes the model reach for the franchise it recognizes — "
                "describe costume, colors, silhouette, and materials concretely. "
                "Reusable descriptions: references/guests/catalog.json"
            )

    for field in ("actionAndEmotion", "identityLocks"):
        block = payload.get(field)
        if isinstance(block, dict):
            for key, value in block.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        check(sub_value, f"{field}.{key}.{sub_key}")
                else:
                    check(value, f"{field}.{key}")

    return failures


def _clean(value: Any) -> str:
    """Collapse a field to a single clean line, or empty if it's a CHANGE stub."""
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split()).strip(" .")
    if not text or text.upper().startswith("CHANGE"):
        return ""
    return text


def _clean_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = _clean(item)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _join_sentences(parts: Iterable[str]) -> str:
    """Join field fragments as real sentences, not lowercase run-ons."""
    out: list[str] = []
    for part in parts:
        text = part.strip() if isinstance(part, str) else ""
        if not text:
            continue
        out.append(text[0].upper() + text[1:])
    return ". ".join(out) + "." if out else ""


def build_compiled_prompt(payload: dict[str, Any], *, orientation: str) -> str:
    """Assemble the $imagegen prompt deterministically from the JSON fields.

    Written by code, not by the agent, for two reasons: the section order is
    fixed (identity and place first, boilerplate last, because image models
    weight the head of a prompt most), and the result is bounded. Hand-written
    compiledPrompt strings drifted long and unordered, and the tail — which is
    where the Arabic text rules and the avoid list lived — got dropped.
    """
    asset_id = str(payload.get("assetId") or "asset")
    is_character_sheet = asset_id == "character-sheet"
    is_location_sheet = asset_id.startswith("location-sheet-")

    style = payload.get("style") if isinstance(payload.get("style"), dict) else {}
    scene = payload.get("scene") if isinstance(payload.get("scene"), dict) else {}
    composition = (
        payload.get("composition")
        if isinstance(payload.get("composition"), dict)
        else {}
    )
    text_block = payload.get("text") if isinstance(payload.get("text"), dict) else {}
    locks = payload.get("identityLocks") if isinstance(payload.get("identityLocks"), dict) else {}
    outfits = payload.get("fixedOutfits") if isinstance(payload.get("fixedOutfits"), dict) else {}
    actions = (
        payload.get("actionAndEmotion")
        if isinstance(payload.get("actionAndEmotion"), dict)
        else {}
    )

    names: dict[str, str] = {}
    on_page: list[str] = []
    for entry in payload.get("participants") or []:
        if not isinstance(entry, dict) or entry.get("onPage", True) is False:
            continue
        pid = entry.get("id")
        if not isinstance(pid, str):
            continue
        on_page.append(pid)
        names[pid] = _clean(entry.get("displayName")) or pid

    # (priority, text). Priority 0 never gets dropped; higher numbers are shed
    # first when the prompt runs long, so the tail can never eat the Arabic
    # text rules or the identity locks.
    sections: list[tuple[int, str]] = []

    def add(priority: int, text: str) -> None:
        if text and text.strip():
            sections.append((priority, text.strip()))

    # 1. What kind of image this is, and its shape. Never trimmed.
    shape = f"{orientation} orientation"
    if is_character_sheet:
        add(
            0,
            f"Character reference sheet, {shape}. "
            f"{_clean(payload.get('primaryRequest'))}.",
        )
    elif is_location_sheet:
        add(
            0,
            f"Location reference sheet, {shape}, no people at all. "
            f"{_clean(payload.get('primaryRequest'))}.",
        )
    else:
        add(
            0,
            f"Children's picture-book page illustration, full-bleed, {shape}. "
            f"Beat: {_clean(payload.get('narrativeBeat'))}. "
            f"{_clean(payload.get('primaryRequest'))}.",
        )

    # 2. Who, and the identity locks. Highest-value content for likeness.
    # Split in two: face/hair/outfit carry the likeness and are never dropped;
    # the secondary traits are already visible in the attached photo and
    # character sheet, so they yield first when a page runs long.
    for pid in on_page:
        lock = locks.get(pid) if isinstance(locks.get(pid), dict) else {}
        primary: list[str] = []
        for key in ("face", "hair"):
            value = _clean(lock.get(key))
            if value and value.lower() not in {"none", "n/a"}:
                primary.append(value)
        outfit = _clean(outfits.get(pid))
        if outfit:
            primary.append(f"always wears {outfit}")
        if primary:
            add(1, f"{names[pid]} ({pid}): " + "; ".join(primary) + ".")

        secondary: list[str] = []
        for key in ("age", "skin", "build", "accessories"):
            value = _clean(lock.get(key))
            if value and value.lower() not in {"none", "n/a"}:
                secondary.append(value)
        if secondary:
            add(3, f"{names[pid]}: " + "; ".join(secondary) + ".")
    if len(on_page) >= 2:
        staging = _clean(payload.get("spatialStaging"))
        add(
            1,
            (f"Staging: {staging}. " if staging else "")
            + "Each person must match their own reference photo — never swap "
            "identity, faces, or outfits between them.",
        )

    # 3. What happens.
    for pid in on_page:
        act = actions.get(pid) if isinstance(actions.get(pid), dict) else {}
        action = _clean(act.get("action"))
        emotion = _clean(act.get("emotion"))
        if action or emotion:
            add(
                1,
                f"{names[pid]}: {action}{'; ' if action and emotion else ''}{emotion}.",
            )

    # 4. Guests, described only — names are handled upstream.
    for guest in payload.get("guests") or []:
        if not isinstance(guest, dict):
            continue
        notes = _clean(guest.get("appearanceNotes"))
        if notes:
            add(1, f"Original guest character (not any known franchise): {notes}.")

    # 5. Where.
    place_bits = [
        _clean(scene.get("place")),
        _clean(scene.get("timeOfDay")),
        _clean(scene.get("lighting")),
    ]
    add(1, "Setting: " + _join_sentences(place_bits))
    layer_bits = [
        f"Foreground: {_clean(scene.get('foreground'))}" if _clean(scene.get("foreground")) else "",
        f"Midground: {_clean(scene.get('midground'))}" if _clean(scene.get("midground")) else "",
        f"Background: {_clean(scene.get('background'))}" if _clean(scene.get("background")) else "",
    ]
    add(2, ". ".join(b for b in layer_bits if b) + "." if any(layer_bits) else "")
    props = _clean_list(scene.get("propsInFrame"), 6)
    if props:
        add(3, "Props in frame: " + ", ".join(props) + ".")

    # 6. Style — verbatim from the theme catalog, identical on every asset.
    style_line = _join_sentences(
        [_clean(style.get("medium")), _clean(style.get("finish"))]
    )
    if style_line:
        add(0, "Style: " + style_line)

    # 7. Composition.
    comp_bits = [
        _clean(composition.get("shotScale")),
        _clean(composition.get("viewpoint")),
        _clean(composition.get("focalHierarchy")),
    ]
    comp = "; ".join(b for b in comp_bits if b)
    if comp:
        add(3, f"Composition: {comp}.")

    # 8. Arabic text. Sheets carry none.
    verbatim = payload.get("verbatimArabicOverride") or (
        text_block.get("verbatimArabic") if isinstance(text_block, dict) else ""
    )
    if not (is_character_sheet or is_location_sheet) and isinstance(verbatim, str) and verbatim.strip():
        integration = (
            composition.get("textIntegration")
            if isinstance(composition.get("textIntegration"), dict)
            else {}
        )
        placement = _clean(integration.get("placement")) or "a quiet zone"
        surface = _clean(integration.get("surface"))
        add(
            0,
            f'Render this Arabic text exactly once inside the artwork, right-to-left, '
            f'correctly connected and fully legible: "{verbatim.strip()}". '
            f"Place it along the {placement} of the frame"
            + (f", on {surface}" if surface else "")
            + ". Blend the lettering into the art sharing the scene palette, "
            "lighting and texture. No hard white box, no sticker label, no speech "
            "bubble, no Latin text. Keep it clear of faces and hands.",
        )
        # Models happily invent Arabic on posters, signs and book covers, and it
        # comes out unrelated or malformed. Everything writable stays blank
        # unless the author explicitly allowed a string.
        extras = _clean_list(payload.get("inImageTextExtras"), 4)
        if extras:
            add(
                0,
                "The only other writing allowed anywhere in the image: "
                + "; ".join(f'"{e}"' for e in extras)
                + ". Every other sign, poster, book cover, board and label must "
                "carry no writing at all — wordless drawings only.",
            )
        else:
            add(
                0,
                "This caption is the ONLY text anywhere in the image. Every sign, "
                "poster, book cover, noticeboard, banner and label must be blank "
                "or show wordless drawings — never invented words or letters.",
            )

    # 9. Palette + continuity.
    add(4, f"Palette: {_clean(payload.get('palette'))}." if _clean(payload.get("palette")) else "")
    continuity = (
        payload.get("continuity") if isinstance(payload.get("continuity"), dict) else {}
    )
    carried = _clean(continuity.get("fromPreviousPage"))
    if carried and carried.lower() != "n/a":
        add(4, f"Carried from the previous page: {carried}.")

    # 10. Avoid — first to go, since the constraints it repeats are mostly
    # already implied by the positive description above.
    avoid = _clean_list(payload.get("avoid"), 12)
    if len(on_page) >= 2 and not any("identity swap" in a.lower() for a in avoid):
        avoid.append("identity swap between characters")
    if avoid:
        add(5, "Avoid: " + ", ".join(avoid) + ".")

    def render(rows: list[tuple[int, str]]) -> str:
        return " ".join(text for _, text in rows)

    prompt = render(sections)
    # Shed whole sections, least important first, until it fits. Never cut a
    # sentence in half and never drop priority 0 or 1.
    for priority in (5, 4, 3, 2):
        if len(prompt) <= MAX_COMPILED_PROMPT_CHARS:
            break
        sections = [row for row in sections if row[0] != priority]
        prompt = render(sections)
    if len(prompt) > MAX_COMPILED_PROMPT_CHARS:
        longest = max(sections, key=lambda row: len(row[1]))[1]
        raise WorkflowError(
            f"{asset_id}: even after dropping optional sections the prompt is "
            f"{len(prompt)} chars (cap {MAX_COMPILED_PROMPT_CHARS}). Shorten the "
            f"verbose field behind this text: {longest[:160]}…"
        )
    return prompt.strip()


def command_compile_prompts(args: argparse.Namespace) -> dict[str, Any]:
    """Rewrite compiledPrompt in every prompt JSON from its structured fields."""
    project = require_absolute(args.project, "project")
    book = load_book(project)
    orientation = book_orientation(book)
    written: list[dict[str, Any]] = []
    for asset in book["assets"]:
        path = prompt_file(project, asset)
        if not path.is_file():
            raise WorkflowError(f"Missing prompt file: {path}")
        payload = read_json(path)
        compiled = build_compiled_prompt(payload, orientation=orientation)
        if len(compiled) < MIN_COMPILED_PROMPT_CHARS:
            raise WorkflowError(
                f"Compiled prompt for {asset['id']} is only {len(compiled)} chars — "
                "the structured fields are too thin. Fill scene layers, identity "
                f"locks, and actions in {path}"
            )
        payload["compiledPrompt"] = compiled
        atomic_json(path, payload)
        written.append({"assetId": asset["id"], "chars": len(compiled)})
    return {
        "compiled": len(written),
        "orientation": orientation,
        "assets": written,
        "nextAction": "Run validate-prompts, then generate-book-images",
    }


def prompt_file(project: Path, asset: dict[str, Any]) -> Path:
    relative = asset.get("promptPath")
    if not relative:
        raise WorkflowError(f"{asset['id']} has no promptPath")
    path = project / relative
    return path


def load_prompt_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    compiled = payload.get("compiledPrompt")
    if not isinstance(compiled, str) or len(compiled.strip()) < MIN_COMPILED_PROMPT_CHARS:
        raise WorkflowError(
            f"compiledPrompt missing/too short in {path} "
            f"(need {MIN_COMPILED_PROMPT_CHARS}+ chars) — run compile-prompts"
        )
    if len(compiled) > MAX_COMPILED_PROMPT_CHARS:
        raise WorkflowError(
            f"compiledPrompt in {path} is {len(compiled)} chars, over the "
            f"{MAX_COMPILED_PROMPT_CHARS} cap. Long prompts get their tail ignored "
            "by the image model — run compile-prompts to rebuild it bounded."
        )
    return payload


def command_validate_prompts(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    if not book.get("storyPath"):
        raise WorkflowError("Lock story.json before validating prompts")
    persona_ids = {
        p["id"]
        for p in (book.get("personas") or [])
        if isinstance(p, dict) and isinstance(p.get("id"), str)
    }
    story_participants: dict[str, set[str]] = {}
    story_page_location: dict[str, str] = {}
    story_file = project / book["storyPath"]
    if story_file.is_file():
        story = read_json(story_file)
        for page in story.get("pages") or []:
            if not isinstance(page, dict) or not isinstance(page.get("id"), str):
                continue
            story_participants[page["id"]] = {
                pid
                for pid in (page.get("participants") or [])
                if isinstance(pid, str)
            }
            if isinstance(page.get("locationId"), str):
                story_page_location[page["id"]] = page["locationId"].strip()
    failures: list[str] = []
    orientation = book_orientation(book)
    theme_fingerprint: str | None = None
    resolved_theme_id: str | None = None
    brief_path = input_dir(project) / "brief.json"
    if brief_path.is_file():
        brief = read_json(brief_path)
        theme_id = brief.get("themeId")
        if isinstance(theme_id, str) and theme_id.strip():
            resolved_theme_id = theme_id.strip()
            try:
                theme = get_theme(resolved_theme_id)
            except WorkflowError as exc:
                failures.append(str(exc))
                theme = None
            if theme is not None:
                fp = theme.get("fingerprint")
                if isinstance(fp, str) and fp.strip():
                    theme_fingerprint = fp.strip()
    for asset in book["assets"]:
        path = prompt_file(project, asset)
        if not path.is_file():
            failures.append(f"missing {asset['promptPath']}")
            continue
        try:
            payload = load_prompt_payload(path)
        except WorkflowError as exc:
            failures.append(str(exc))
            continue
        if payload.get("assetId") != asset["id"]:
            failures.append(f"assetId mismatch in {asset['promptPath']}")

        composition = (
            payload.get("composition")
            if isinstance(payload.get("composition"), dict)
            else {}
        )
        declared = str(composition.get("orientation") or "").strip().lower()
        if declared != orientation:
            failures.append(
                f"composition.orientation must be {orientation!r} (book setting), "
                f"got {declared!r} in {asset['promptPath']}"
            )

        if theme_fingerprint:
            style = payload.get("style") if isinstance(payload.get("style"), dict) else {}
            medium = style.get("medium") if isinstance(style, dict) else ""
            medium_s = medium if isinstance(medium, str) else ""
            if theme_fingerprint.lower() not in medium_s.lower():
                failures.append(
                    f"style.medium must include theme fingerprint "
                    f"{theme_fingerprint!r} in {asset['promptPath']}"
                )

        # Copyright-safe: scan every field that can reach the image model.
        failures.extend(scan_prompt_for_franchise_names(payload, asset["promptPath"]))

        locks = payload.get("identityLocks")
        outfits = payload.get("fixedOutfits")
        actions = payload.get("actionAndEmotion")
        participants = payload.get("participants") or []
        on_page_ids: list[str] = []
        for entry in participants:
            if not isinstance(entry, dict):
                continue
            pid = entry.get("id")
            if not isinstance(pid, str):
                continue
            if entry.get("onPage", True) is False:
                continue
            on_page_ids.append(pid)
            if pid not in persona_ids and asset["id"] != "character-sheet":
                # guests are separate; only flag unknown persona-* ids
                if pid.startswith("persona-"):
                    failures.append(
                        f"unknown persona {pid} in {asset['promptPath']}"
                    )

        if asset["id"] == "character-sheet":
            missing = persona_ids - set(on_page_ids)
            if missing:
                failures.append(
                    f"character-sheet must include all personas; missing {sorted(missing)}"
                )
            if not isinstance(locks, dict) or any(
                pid not in (locks or {}) for pid in persona_ids
            ):
                failures.append(
                    "character-sheet identityLocks must be keyed per personaId "
                    f"for all of {sorted(persona_ids)}"
                )
            if not isinstance(outfits, dict) or any(
                pid not in (outfits or {}) for pid in persona_ids
            ):
                failures.append(
                    "character-sheet fixedOutfits must be keyed per personaId "
                    f"for all of {sorted(persona_ids)}"
                )
        elif asset["id"].startswith("location-sheet-"):
            declared_loc = str(payload.get("locationId") or "").strip()
            if declared_loc != asset.get("locationId"):
                failures.append(
                    f"{asset['promptPath']} locationId {declared_loc!r} != "
                    f"book asset locationId {asset.get('locationId')!r}"
                )
            if on_page_ids:
                failures.append(
                    f"{asset['promptPath']} must have no participants — a location "
                    "sheet is the empty place only, so people never leak into it"
                )
        else:
            expected_loc = story_page_location.get(asset["id"])
            declared_loc = str(payload.get("locationId") or "").strip()
            if expected_loc and declared_loc != expected_loc:
                failures.append(
                    f"{asset['promptPath']} locationId {declared_loc!r} != "
                    f"story.json {expected_loc!r}"
                )
            expected = story_participants.get(asset["id"])
            if expected is not None and set(on_page_ids) != expected:
                failures.append(
                    f"{asset['promptPath']} participants {sorted(on_page_ids)} "
                    f"!= story.json {sorted(expected)}"
                )
            if len(on_page_ids) >= 2 and not str(
                payload.get("spatialStaging") or ""
            ).strip():
                failures.append(
                    f"spatialStaging required for multi-persona page: {asset['promptPath']}"
                )
            if isinstance(locks, dict) and locks and not any(
                k.startswith("persona-") for k in locks
            ):
                failures.append(
                    f"identityLocks must be per-persona objects in {asset['promptPath']}"
                )
            for pid in on_page_ids:
                if isinstance(locks, dict) and pid not in locks:
                    failures.append(
                        f"missing identityLocks.{pid} in {asset['promptPath']}"
                    )
                if isinstance(outfits, dict) and pid not in outfits:
                    failures.append(
                        f"missing fixedOutfits.{pid} in {asset['promptPath']}"
                    )
                if isinstance(actions, dict) and pid not in actions:
                    failures.append(
                        f"missing actionAndEmotion.{pid} in {asset['promptPath']}"
                    )

        if asset["includeInPdf"]:
            exact_text = asset.get("storyText") or ""
            compiled = payload["compiledPrompt"]
            verbatim = (
                payload.get("text", {}).get("verbatimArabic")
                if isinstance(payload.get("text"), dict)
                else None
            )
            if exact_text and exact_text not in compiled:
                failures.append(f"exact story text missing from compiledPrompt: {asset['promptPath']}")
            if exact_text and verbatim != exact_text:
                failures.append(
                    f"text.verbatimArabic must match story.json for {asset['promptPath']}"
                )
            lower = compiled.lower()
            if len(on_page_ids) >= 2 and not any(
                phrase in lower
                for phrase in ("identity swap", "never swap identity")
            ):
                failures.append(
                    f"compiledPrompt must forbid identity swap when 2+ people: "
                    f"{asset['promptPath']} — run compile-prompts"
                )
            if "no hard white box" not in lower:
                failures.append(
                    f"compiledPrompt must forbid a hard white text box: "
                    f"{asset['promptPath']} — run compile-prompts"
                )
    if failures:
        raise WorkflowError("Prompt validation failed:\n- " + "\n- ".join(failures))
    for asset in book["assets"]:
        if asset["status"] == "planned":
            asset["status"] = "prompted"
    book["status"] = "character_sheet"
    book["nextAsset"] = "character-sheet"
    book["nextAction"] = (
        "Run generate-book-images --project <client> "
        "(character-sheet via Codex, then all PDF pages in parallel)"
    )
    save_book(project, book)
    return {
        "valid": True,
        "promptCount": len(book["assets"]),
        "personaCount": len(persona_ids),
        "themeId": resolved_theme_id,
        "nextAction": book["nextAction"],
    }


def ensure_consent(book: dict[str, Any]) -> None:
    if not book.get("consent", {}).get("confirmed"):
        raise WorkflowError("Consent must be confirmed before any image call")


def active_fix_ids(book: dict[str, Any]) -> list[str]:
    queue = book.get("review", {}).get("fixQueue", [])
    return [
        entry["assetId"]
        for entry in queue
        if isinstance(entry, dict) and entry.get("assetId")
    ]


def command_begin_asset(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    require_asset_id(book, args.asset)
    ensure_consent(book)
    asset = asset_by_id(book, args.asset)
    allow_parallel = bool(getattr(args, "allow_parallel", False))
    if asset["status"] == "generating" and not allow_parallel:
        raise WorkflowError(f"{args.asset} is already generating; reconcile it first")
    if asset["attempt"] >= MAX_ATTEMPTS:
        raise WorkflowError(f"{args.asset} reached the {MAX_ATTEMPTS}-attempt limit")

    if args.asset.startswith("location-sheet-"):
        if not book.get("storyPath"):
            raise WorkflowError("Lock story.json before generating location sheets")
        sheet = asset_by_id(book, "character-sheet")
        if sheet["status"] != "accepted":
            raise WorkflowError(
                "Character sheet must be accepted before location sheets"
            )
        if asset.get("imagePath") and not allow_parallel:
            raise WorkflowError(f"{args.asset} already has an image")
    elif args.asset != "character-sheet":
        sheet = asset_by_id(book, "character-sheet")
        if sheet["status"] != "accepted":
            raise WorkflowError("Character sheet must be accepted before page generation")
        pending_locations = [
            asset_id
            for asset_id in location_asset_ids(book)
            if not asset_by_id(book, asset_id).get("imagePath")
        ]
        if pending_locations:
            raise WorkflowError(
                "Generate location sheets before story pages (missing: "
                f"{', '.join(pending_locations)}). Pages use them to keep every "
                "visit to the same place looking identical."
            )
        fix_ids = active_fix_ids(book)
        if fix_ids:
            if not allow_parallel and args.asset != fix_ids[0]:
                raise WorkflowError(f"Next queued fix is {fix_ids[0]}, not {args.asset}")
            if allow_parallel and args.asset not in fix_ids:
                raise WorkflowError(f"{args.asset} is not in the fix queue")
        elif not allow_parallel:
            expected = next_first_pass_asset(book)
            if expected and args.asset != expected:
                raise WorkflowError(f"Next first-pass asset is {expected}, not {args.asset}")
        else:
            # parallel first-pass: asset must still lack an image
            if asset.get("imagePath"):
                raise WorkflowError(f"{args.asset} already has an image")
    else:
        if not book.get("storyPath"):
            raise WorkflowError("Lock story.json before generating the character sheet")
        if asset["status"] == "accepted":
            raise WorkflowError("Character sheet is already accepted")
        if asset["status"] not in {"prompted", "needs_revision"}:
            raise WorkflowError("Validate all prompts before generating the character sheet")

    path = prompt_file(project, asset)
    payload = load_prompt_payload(path)
    if asset["includeInPdf"] and asset["storyText"] not in payload["compiledPrompt"]:
        raise WorkflowError(f"Current prompt does not contain exact story text: {path}")

    if asset["status"] != "generating":
        asset["attempt"] += 1
    asset["status"] = "generating"
    version = asset["promptVersion"]
    existing = next((item for item in asset["versions"] if item["version"] == version), None)
    if existing is None:
        asset["versions"].append(
            {
                "version": version,
                "attempt": asset["attempt"],
                "promptPath": asset["promptPath"],
                "imagePath": None,
                "reviewPath": None,
                "status": "generating",
            }
        )
    else:
        existing["status"] = "generating"
        existing["attempt"] = asset["attempt"]
    book["status"] = "generating"
    book["nextAsset"] = args.asset
    book["nextAction"] = (
        f"Dispatch Codex $imagegen for {args.asset} "
        f"(compiledPrompt from {asset['promptPath']}), then reconcile"
    )
    save_book(project, book)
    return {
        "asset": args.asset,
        "attempt": asset["attempt"],
        "promptVersion": version,
        "promptPath": str(path),
        "compiledPrompt": payload["compiledPrompt"],
        "nextAction": book["nextAction"],
    }


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(f".{destination.name}.tmp")
    shutil.copy2(source, tmp)
    os.replace(tmp, destination)


def update_next_after_image(book: dict[str, Any], asset_id: str) -> None:
    if asset_id == "character-sheet":
        book["status"] = "character_review"
        book["nextAsset"] = "character-sheet"
        book["nextAction"] = (
            "Review character sheet visually; if ok run character-review --accept, "
            "else write next prompt version and retry"
        )
        return
    fix_ids = active_fix_ids(book)
    if fix_ids:
        if asset_id == fix_ids[0]:
            book["review"]["fixQueue"] = book["review"]["fixQueue"][1:]
        if book["review"]["fixQueue"]:
            nxt = book["review"]["fixQueue"][0]["assetId"]
            book["status"] = "fixing"
            book["nextAsset"] = nxt
            book["nextAction"] = (
                f"Write targeted {asset_by_id(book, nxt)['promptPath']}, then begin-asset"
            )
        else:
            book["status"] = "review"
            book["nextAsset"] = None
            book["nextAction"] = "Rebuild draft PDF, verify, then rerun reviewers"
        return
    nxt = next_first_pass_asset(book)
    if nxt:
        book["status"] = "generating"
        book["nextAsset"] = nxt
        book["nextAction"] = (
            f"Run generate-asset for {nxt} (Codex $imagegen), or generate-pages-parallel"
        )
    else:
        book["status"] = "draft_ready"
        book["nextAsset"] = None
        book["nextAction"] = "Build and verify the draft PDF"


def command_reconcile_image(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    asset = asset_by_id(book, args.asset)
    if asset["status"] != "generating":
        raise WorkflowError(f"{args.asset} is not awaiting reconcile (status={asset['status']})")
    source = require_absolute(args.image, "image")
    width, height, image_format = validate_image(source)

    # The image agent is told to place a file at an exact path, and it can
    # satisfy that by copying an image that already exists nearby instead of
    # generating one. Observed in practice: a page arrived carrying the cover's
    # artwork. Identical bytes across two assets is never legitimate here.
    digest = sha256(source)
    for other in book["assets"]:
        if other["id"] == args.asset or not other.get("imagePath"):
            continue
        other_path = project / other["imagePath"]
        if not other_path.is_file():
            continue
        if sha256(other_path) == digest:
            raise WorkflowError(
                f"{args.asset} image is byte-identical to {other['id']} — the "
                "generator copied an existing image instead of drawing this "
                f"page. Delete {source} and regenerate {args.asset}."
            )

    suffix = source.suffix.lower() or ".png"
    relative = f"output/images/{args.asset}{suffix}"
    destination = project / relative
    atomic_copy(source, destination)
    asset["imagePath"] = relative
    asset["status"] = "generated" if args.asset != "character-sheet" else "awaiting_review"
    version = asset["promptVersion"]
    for item in asset["versions"]:
        if item["version"] == version:
            item["imagePath"] = relative
            item["status"] = asset["status"]
            item["width"] = width
            item["height"] = height
            item["format"] = image_format
            item["sha256"] = sha256(destination)
    update_next_after_image(book, args.asset)
    save_book(project, book)
    return {
        "asset": args.asset,
        "imagePath": str(destination),
        "nextAction": book["nextAction"],
    }


def persist_review(project: Path, payload: dict[str, Any], destination: Path) -> str:
    atomic_json(destination, payload)
    return str(destination.relative_to(project))


def command_character_review(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    asset = asset_by_id(book, "character-sheet")
    if not asset.get("imagePath"):
        raise WorkflowError("Character sheet image missing")
    if args.accept:
        asset["status"] = "accepted"
        book["status"] = "generating"
        book["nextAsset"] = "cover"
        book["nextAction"] = (
            "Run generate-book-images --project <client> "
            "(or generate-pages-parallel if character already accepted)"
        )
        save_book(project, book)
        return {"decision": "accept", "nextAction": book["nextAction"]}

    review_path = require_absolute(args.review, "review") if args.review else None
    if review_path is None:
        raise WorkflowError("Provide --accept or --review <json>")
    payload = read_json(review_path)
    decision = payload.get("decision")
    stored_rel = persist_review(
        project,
        payload,
        output_dir(project) / "reviews" / "character-sheet.json",
    )
    if decision == "accept":
        asset["status"] = "accepted"
        book["status"] = "generating"
        book["nextAsset"] = "cover"
        book["nextAction"] = (
            "Run generate-book-images --project <client> "
            "(or generate-pages-parallel if character already accepted)"
        )
    else:
        asset["status"] = "needs_revision"
        asset["promptVersion"] += 1
        asset["promptPath"] = (
            f"input/prompts/character-sheet.v{asset['promptVersion']:02d}.json"
        )
        book["status"] = "character_sheet"
        book["nextAsset"] = "character-sheet"
        book["nextAction"] = (
            f"Write {asset['promptPath']}, then begin-asset for character-sheet"
        )
    for item in asset["versions"]:
        if item["version"] == asset["promptVersion"] - (0 if decision == "accept" else 1):
            item["reviewPath"] = stored_rel
    save_book(project, book)
    return {"decision": decision, "review": stored_rel, "nextAction": book["nextAction"]}


def ordered_pdf_assets(book: dict[str, Any]) -> list[dict[str, Any]]:
    assets = [asset_by_id(book, asset_id) for asset_id in pdf_ids(book)]
    missing = [asset["id"] for asset in assets if not asset.get("imagePath")]
    if missing:
        raise WorkflowError(f"Missing images for: {', '.join(missing)}")
    return assets


def next_pdf_path(project: Path, book: dict[str, Any], edition: str) -> Path:
    _ = book
    return output_dir(project) / "pdf" / f"{edition}.pdf"


def image_aspect(image_path: Path) -> float:
    Image, _, _ = import_pillow()
    with Image.open(image_path) as image:
        width, height = image.size
    if height <= 0:
        raise WorkflowError(f"Invalid image height: {image_path}")
    return width / height


def draw_full_bleed(pdf: Any, image_path: Path, page_width: float, page_height: float) -> None:
    """Cover the page without distorting the art.

    Aspect-correct scale-to-fill: overflow is cropped evenly, which is what a
    printed full-bleed page does anyway. The old preserveAspectRatio=False
    squashed every off-ratio image instead.
    """
    from reportlab.lib.utils import ImageReader

    reader = ImageReader(str(image_path))
    source_width, source_height = reader.getSize()
    scale = max(page_width / source_width, page_height / source_height)
    draw_width = source_width * scale
    draw_height = source_height * scale
    pdf.drawImage(
        reader,
        (page_width - draw_width) / 2,
        (page_height - draw_height) / 2,
        width=draw_width,
        height=draw_height,
        preserveAspectRatio=True,
        anchor="c",
    )


def command_build(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
    except ImportError as exc:
        raise WorkflowError(
            "reportlab is required: python3 -m pip install reportlab"
        ) from exc

    assets = ordered_pdf_assets(book)
    # Page size comes from the book's declared orientation, not from whatever
    # aspect the first image happened to come back as.
    orientation = book_orientation(book)
    ratio = ORIENTATION_RATIOS[orientation]
    if ratio >= 1:
        page_height = A4[0]
        page_width = page_height * ratio
    else:
        page_width = A4[0]
        page_height = page_width / ratio

    destination = next_pdf_path(project, book, args.edition)
    destination.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(destination), pagesize=(page_width, page_height))
    for asset in assets:
        image_path = project / asset["imagePath"]
        validate_image(image_path)
        draw_full_bleed(pdf, image_path, page_width, page_height)
        pdf.showPage()
    pdf.save()
    digest = sha256(destination)
    relative = str(destination.relative_to(project))
    book["pdf"][args.edition] = {
        "status": "built",
        "path": relative,
        "sha256": digest,
        "builtAt": now_iso(),
    }
    book["status"] = "draft_built" if args.edition == "draft" else "final_built"
    book["nextAction"] = f"Run verify --edition {args.edition}"
    save_book(project, book)
    return {
        "pdf": str(destination),
        "sha256": digest,
        "orientation": orientation,
        "nextAction": book["nextAction"],
    }


def command_verify(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    entry = book["pdf"].get(args.edition) or {}
    if not entry.get("path"):
        raise WorkflowError(f"No {args.edition} PDF built yet")
    pdf_path = project / entry["path"]
    if not pdf_path.is_file():
        raise WorkflowError(f"Missing PDF: {pdf_path}")

    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError as exc:
            raise WorkflowError(
                "pypdf is required: python3 -m pip install pypdf"
            ) from exc

    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)
    expected = int(book["settings"]["pdfPageCount"])
    if page_count != expected:
        raise WorkflowError(f"PDF page count is {page_count}, expected {expected}")

    Image, _, _ = import_pillow()
    render_dir = output_dir(project) / "renders" / args.edition
    if render_dir.exists():
        shutil.rmtree(render_dir)
    render_dir.mkdir(parents=True, exist_ok=True)

    # Confirm source images still valid, ordered, and all the same shape.
    orientation = book_orientation(book)
    expected_ratio = ORIENTATION_RATIOS[orientation]
    off_ratio: list[dict[str, Any]] = []
    for index, asset_id in enumerate(pdf_ids(book), start=1):
        asset = asset_by_id(book, asset_id)
        image_path = project / asset["imagePath"]
        validate_image(image_path)
        ratio = image_aspect(image_path)
        if abs(ratio - expected_ratio) / expected_ratio > ASPECT_TOLERANCE:
            off_ratio.append(
                {
                    "assetId": asset_id,
                    "aspect": round(ratio, 3),
                    "expected": round(expected_ratio, 3),
                }
            )
        target = render_dir / f"{index:02d}-{asset_id}.png"
        atomic_copy(image_path, target)

    if off_ratio:
        detail = ", ".join(
            f"{row['assetId']} ({row['aspect']} vs {row['expected']})"
            for row in off_ratio
        )
        raise WorkflowError(
            f"{len(off_ratio)} image(s) do not match the book orientation "
            f"({orientation}): {detail}. Regenerate them — mixed aspect ratios "
            "get cropped in the PDF and make the book look inconsistent."
        )

    entry["status"] = "verified"
    entry["verifiedAt"] = now_iso()
    book["pdf"][args.edition] = entry
    if args.edition == "draft":
        book["status"] = "review"
        book["nextAction"] = (
            "Show draft PDF to user AND auto-start reviewers "
            "(story/arabic/continuity/pdf). Save review JSON under output/reviews/. "
            "Iterate fixes with user until satisfied, then build final."
        )
    else:
        book["status"] = "complete"
        book["nextAction"] = "Handoff final PDF to user"
    save_book(project, book)
    return {
        "edition": args.edition,
        "pageCount": page_count,
        "orientation": orientation,
        "renders": str(render_dir),
        "pdf": str(pdf_path),
        "nextAction": book["nextAction"],
    }


def command_contact_sheet(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    Image, ImageDraw, _ = import_pillow()
    assets = ordered_pdf_assets(book)
    # Thumb box follows the book shape so the contact sheet reads like the book.
    ratio = ORIENTATION_RATIOS[book_orientation(book)]
    thumb_w, thumb_h = (420, int(420 / ratio)) if ratio >= 1 else (int(420 * ratio), 420)
    cols = min(5, max(1, len(assets)))
    rows = (len(assets) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * thumb_h), "white")
    for index, asset in enumerate(assets):
        row, col = divmod(index, cols)
        with Image.open(project / asset["imagePath"]) as image:
            image = image.convert("RGB")
            image.thumbnail((thumb_w, thumb_h))
            offset = (
                col * thumb_w + (thumb_w - image.width) // 2,
                row * thumb_h + (thumb_h - image.height) // 2,
            )
            sheet.paste(image, offset)
    destination = output_dir(project) / "contact-sheets" / "pages.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)
    return {"contactSheet": str(destination), "pageCount": len(assets)}


def normalize_issue(issue: Any, role: str, allowed_ids: list[str]) -> dict[str, Any]:
    if not isinstance(issue, dict):
        raise WorkflowError(f"{role} review contains a non-object issue")
    asset_id = issue.get("assetId")
    if asset_id not in allowed_ids:
        raise WorkflowError(f"{role} review has unknown assetId: {asset_id!r}")
    severity = issue.get("severity")
    if severity not in {"blocking", "note"}:
        raise WorkflowError(f"{role} issue severity must be blocking|note")
    instruction = str(issue.get("revisionInstruction", "")).strip()
    if severity == "blocking" and not instruction:
        raise WorkflowError(
            f"{role} blocking issue for {asset_id} needs revisionInstruction"
        )
    return {
        "assetId": asset_id,
        "severity": severity,
        "code": str(issue.get("code", "unspecified")),
        "evidence": str(issue.get("evidence", "")),
        "revisionInstruction": instruction or None,
        "reviewerRole": role,
    }


def command_merge_reviews(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    allowed_ids = pdf_ids(book)
    if book["pdf"]["draft"].get("status") != "verified":
        raise WorkflowError("Verify the current draft PDF before merging reviews")
    if len(args.review) != 4:
        raise WorkflowError("Exactly four review JSON files are required")
    payloads: dict[str, dict[str, Any]] = {}
    for review_path in args.review:
        path = require_absolute(review_path, "review")
        payload = read_json(path)
        role = payload.get("reviewerRole")
        if role not in REVIEWER_ROLES:
            raise WorkflowError(f"Invalid reviewerRole in {path}: {role!r}")
        if role in payloads:
            raise WorkflowError(f"Duplicate reviewerRole: {role}")
        payloads[role] = payload
    if set(payloads) != REVIEWER_ROLES:
        raise WorkflowError(f"Reviews must cover: {', '.join(sorted(REVIEWER_ROLES))}")

    review_pass = book["review"].get("pass", 0) + 1
    issues_by_asset: dict[str, list[dict[str, Any]]] = {}
    saved_paths: list[str] = []
    for role, payload in payloads.items():
        normalized = [
            normalize_issue(issue, role, allowed_ids)
            for issue in payload.get("issues", [])
        ]
        stored = {**payload, "pass": review_pass, "issues": normalized}
        destination = (
            output_dir(project) / "reviews" / f"pass-{review_pass:02d}-{role}.json"
        )
        saved_paths.append(persist_review(project, stored, destination))
        for issue in normalized:
            if issue["severity"] == "blocking":
                issues_by_asset.setdefault(issue["assetId"], []).append(issue)

    fix_queue: list[dict[str, Any]] = []
    manual: list[dict[str, Any]] = []
    for asset_id in allowed_ids:
        issues = issues_by_asset.get(asset_id)
        if not issues:
            asset = asset_by_id(book, asset_id)
            if asset.get("imagePath") and asset["status"] != "needs_manual_review":
                asset["status"] = "accepted"
            continue
        asset = asset_by_id(book, asset_id)
        entry = {"assetId": asset_id, "issues": issues, "attempt": asset["attempt"]}
        if asset["attempt"] < MAX_ATTEMPTS:
            asset["status"] = "needs_revision"
            asset["promptVersion"] += 1
            asset["promptPath"] = (
                f"input/prompts/{asset_id}.v{asset['promptVersion']:02d}.json"
            )
            fix_queue.append(entry)
        else:
            asset["status"] = "needs_manual_review"
            manual.append(entry)

    book["review"]["pass"] = review_pass
    book["review"]["mergedReviewPaths"] = saved_paths
    book["review"]["fixQueue"] = fix_queue
    book["review"]["manualReview"] = manual
    if fix_queue:
        book["review"]["status"] = "fixes_pending"
        book["status"] = "fixing"
        book["nextAsset"] = fix_queue[0]["assetId"]
        book["nextAction"] = (
            f"Write targeted {asset_by_id(book, fix_queue[0]['assetId'])['promptPath']}, "
            "then run begin-asset / generate-batch for fix queue. "
            "User may also request manual edits. Re-show PDF after fixes."
        )
    else:
        book["review"]["status"] = "manual_review" if manual else "passed"
        book["status"] = "final_ready"
        book["nextAsset"] = None
        book["nextAction"] = (
            "No automatic fixes left. Ask user if satisfied; if yes build final PDF, "
            "else apply user notes and continue review loop."
        )
    save_book(project, book)
    return {
        "pass": review_pass,
        "fixQueue": [entry["assetId"] for entry in fix_queue],
        "manualReview": [entry["assetId"] for entry in manual],
        "nextAction": book["nextAction"],
    }


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    project = require_absolute(args.project, "project")
    book = load_book(project)
    template_selection = book.get("templateSelection")
    brief_path = input_dir(project) / "brief.json"
    if brief_path.is_file():
        brief = read_json(brief_path)
        template_selection = brief.get("templateSelection") or template_selection
    return {
        "project": str(project),
        "status": book.get("status"),
        "nextAsset": book.get("nextAsset"),
        "nextAction": book.get("nextAction"),
        "consent": book.get("consent", {}).get("confirmed"),
        "storyPath": book.get("storyPath"),
        "templateSelection": template_selection,
        "assets": {
            asset["id"]: {
                "status": asset["status"],
                "attempt": asset["attempt"],
                "promptPath": asset["promptPath"],
                "imagePath": asset.get("imagePath"),
            }
            for asset in book["assets"]
        },
        "review": book.get("review"),
        "pdf": book.get("pdf"),
    }


def skill_scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def resolve_codex_dispatch() -> Path:
    """Locate codex-imagegen dispatch.py (personal skill or repo symlink)."""
    repo_root = skill_scripts_dir().parents[1]  # tools/scripts → hekaytyworkflow
    candidates = [
        Path.home() / ".cursor" / "skills" / "codex-imagegen" / "scripts" / "dispatch.py",
        repo_root
        / ".cursor"
        / "skills"
        / "codex-imagegen"
        / "scripts"
        / "dispatch.py",
    ]
    for path in candidates:
        if path.is_file():
            return path.resolve()
    raise WorkflowError(
        "codex-imagegen dispatch.py not found. Expected at "
        "~/.cursor/skills/codex-imagegen/scripts/dispatch.py"
    )


def default_codex_workers(job_count: int) -> int:
    """Parallel Codex sessions.

    Capped well below the job count on purpose. Each page job now views 4-5
    reference images before generating, and 20 concurrent sessions starved each
    other badly enough that 20 of 22 pages blew a 900s timeout while only 2
    finished. Fewer workers finish more pages per minute here.
    """
    raw = (
        os.environ.get("HEKAYATI_CODEX_WORKERS")
        or os.environ.get("CODEX_IMAGEGEN_WORKERS")
    )
    if raw and raw.strip().isdigit():
        return max(1, int(raw.strip()))
    return max(1, min(job_count, MAX_CODEX_WORKERS))


def default_codex_timeout(job_count: int, workers: int | None = None) -> int:
    """Per-job timeout, scaled by how many rounds the queue has to run.

    The timeout applies per job, but jobs queue behind the worker pool, so a
    deep queue needs headroom for the jobs that start last.
    """
    raw = os.environ.get("HEKAYATI_CODEX_TIMEOUT_SEC")
    if raw and raw.strip().isdigit():
        return int(raw.strip())
    lanes = workers or default_codex_workers(job_count)
    rounds = max(1, -(-job_count // max(1, lanes)))
    return min(CODEX_TIMEOUT_CEILING_SEC, CODEX_TIMEOUT_BASE_SEC * rounds)


def run_codex_imagegen(
    *,
    project: Path,
    jobs: list[dict[str, Any]],
    timeout_sec: int | None = None,
    workers: int | None = None,
    orientation: str = DEFAULT_ORIENTATION,
) -> dict[str, Any]:
    """Write jobs JSON and run Codex $imagegen via parallel codex-imagegen dispatch."""
    if not jobs:
        raise WorkflowError("No image jobs to dispatch")
    images = output_dir(project) / "images"
    images.mkdir(parents=True, exist_ok=True)
    jobs_path = images / ".codex-jobs.json"
    atomic_json(jobs_path, {"orientation": orientation, "jobs": jobs})
    timeout = timeout_sec if timeout_sec is not None else default_codex_timeout(len(jobs))
    worker_n = workers if workers is not None else default_codex_workers(len(jobs))
    cmd = [
        sys.executable,
        str(resolve_codex_dispatch()),
        "--jobs",
        str(jobs_path),
        "--cd",
        str(project),
        "--timeout-sec",
        str(timeout),
        "--workers",
        str(worker_n),
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise WorkflowError(
            "codex-imagegen dispatch returned non-JSON "
            f"(exit {proc.returncode}): "
            f"{(proc.stdout or '')[:500]} {(proc.stderr or '')[:500]}"
        ) from exc
    payload.setdefault("exitCode", proc.returncode)
    payload["jobsPath"] = str(jobs_path)
    if proc.returncode != 0 and not payload.get("results"):
        raise WorkflowError(
            payload.get("error")
            or proc.stderr
            or f"Codex imagegen failed (exit {proc.returncode})"
        )
    return payload


def command_generate_asset(args: argparse.Namespace) -> dict[str, Any]:
    """Begin asset + Codex $imagegen + reconcile."""
    project = require_absolute(args.project, "project")
    if getattr(args, "_locked", False):
        return _generate_asset_locked(args, project)
    with ProjectLock(project, "generate-asset"):
        return _generate_asset_locked(args, project)


def _generate_asset_locked(args: argparse.Namespace, project: Path) -> dict[str, Any]:
    book = load_book(project)
    require_asset_id(book, args.asset)
    begin_ns = argparse.Namespace(project=project, asset=args.asset)
    begin = command_begin_asset(begin_ns)
    book = load_book(project)
    refs = collect_asset_refs(project, book, args.asset)
    tmp_out = output_dir(project) / "images" / f".tmp-{args.asset}.png"
    # A leftover temp from a previous run is something the agent can copy
    # instead of generating. Clear it so the path is empty when the job starts.
    tmp_out.unlink(missing_ok=True)
    jobs = [
        {
            "id": args.asset,
            "prompt": begin["compiledPrompt"],
            "output": str(tmp_out.resolve()),
            "refs": [str(r) for r in refs],
        }
    ]
    timeout = getattr(args, "timeout_sec", None)
    workers = getattr(args, "workers", None)
    payload = run_codex_imagegen(
        project=project,
        jobs=jobs,
        timeout_sec=timeout,
        workers=workers,
        orientation=book_orientation(book),
    )
    result_row = next(
        (r for r in (payload.get("results") or []) if r.get("id") == args.asset),
        None,
    )
    if not result_row or not result_row.get("ok"):
        raise WorkflowError(
            (result_row or {}).get("error")
            or payload.get("error")
            or f"Codex imagegen failed for {args.asset}"
        )
    image_path = Path(result_row["path"])
    if not image_path.is_file():
        raise WorkflowError(f"Codex output missing: {image_path}")
    reconciled = command_reconcile_image(
        argparse.Namespace(project=project, asset=args.asset, image=image_path)
    )
    book = load_book(project)
    book.setdefault("settings", {})["imageProvider"] = "codex"
    book["settings"]["imageModel"] = "gpt-image-2"
    book["settings"]["imageBackend"] = "codex-imagegen"
    save_book(project, book)
    return {
        "asset": args.asset,
        "attempt": begin["attempt"],
        "promptPath": begin["promptPath"],
        "provider": "codex",
        "imagePath": reconciled["imagePath"],
        "nextAction": reconciled["nextAction"],
        "codex": {
            "jobsPath": payload.get("jobsPath"),
            "briefPath": payload.get("briefPath"),
            "bytes": result_row.get("bytes"),
        },
    }


def command_generate_batch(args: argparse.Namespace) -> dict[str, Any]:
    """Batch image generation via one Codex $imagegen dispatch."""
    project = require_absolute(args.project, "project")
    if getattr(args, "_locked", False):
        return _generate_batch_locked(args, project)
    with ProjectLock(project, "generate-batch"):
        return _generate_batch_locked(args, project)


def _generate_batch_locked(args: argparse.Namespace, project: Path) -> dict[str, Any]:
    book = load_book(project)
    ensure_consent(book)
    for asset_id in args.assets:
        require_asset_id(book, asset_id)

    jobs: list[dict[str, Any]] = []
    for asset_id in args.assets:
        begin = command_begin_asset(
            argparse.Namespace(
                project=project, asset=asset_id, allow_parallel=True
            )
        )
        book = load_book(project)
        refs = collect_asset_refs(project, book, asset_id)
        tmp_out = output_dir(project) / "images" / f".tmp-{asset_id}.png"
        tmp_out.unlink(missing_ok=True)
        jobs.append(
            {
                "id": asset_id,
                "prompt": begin["compiledPrompt"],
                "output": str(tmp_out.resolve()),
                "refs": [str(r) for r in refs],
            }
        )

    timeout = getattr(args, "timeout_sec", None)
    workers = getattr(args, "workers", None)
    payload = run_codex_imagegen(
        project=project,
        jobs=jobs,
        timeout_sec=timeout,
        workers=workers,
        orientation=book_orientation(book),
    )

    reconciled: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    by_id = {
        r.get("id"): r for r in (payload.get("results") or []) if isinstance(r, dict)
    }
    for job in jobs:
        asset_id = job["id"]
        row = by_id.get(asset_id) or {}
        image_path = Path(row["path"]) if row.get("path") else Path(job["output"])
        if not row.get("ok") or not image_path.is_file():
            failures.append(
                {
                    "id": asset_id,
                    "ok": False,
                    "error": row.get("error") or f"missing output: {image_path}",
                }
            )
            continue
        try:
            result = command_reconcile_image(
                argparse.Namespace(
                    project=project, asset=asset_id, image=image_path
                )
            )
            reconciled.append(
                {"asset": asset_id, "imagePath": result["imagePath"]}
            )
        except WorkflowError as exc:
            failures.append({"id": asset_id, "ok": False, "error": str(exc)})

    book = load_book(project)
    book.setdefault("settings", {})["imageProvider"] = "codex"
    book["settings"]["imageModel"] = "gpt-image-2"
    book["settings"]["imageBackend"] = "codex-imagegen"
    save_book(project, book)
    return {
        "ok": len(failures) == 0,
        "provider": "codex",
        "mode": "batch",
        "jobCount": len(jobs),
        "jobsPath": payload.get("jobsPath"),
        "briefPath": payload.get("briefPath"),
        "reconciled": reconciled,
        "failures": failures,
        "nextAction": book.get("nextAction"),
    }


def command_generate_pages_parallel(args: argparse.Namespace) -> dict[str, Any]:
    """Interior pages in one parallel dispatch, then covers in a second wave.

    Covers go last so they can reference finished interior art.
    """
    project = require_absolute(args.project, "project")
    if getattr(args, "_locked", False):
        return _generate_pages_parallel_locked(args, project)
    with ProjectLock(project, "generate-pages-parallel"):
        args._locked = True
        return _generate_pages_parallel_locked(args, project)


def _generate_pages_parallel_locked(args: argparse.Namespace, project: Path) -> dict[str, Any]:
    book = load_book(project)
    sheet = asset_by_id(book, "character-sheet")
    if sheet["status"] != "accepted":
        raise WorkflowError("Accept character-sheet before generate-pages-parallel")

    # Resume: if Codex already wrote .tmp-<asset>.png, reconcile those first.
    resumed: list[dict[str, Any]] = []
    resume_failures: list[dict[str, Any]] = []
    images = output_dir(project) / "images"
    for asset_id in generation_order(book):
        asset = asset_by_id(book, asset_id)
        if asset.get("imagePath"):
            continue
        tmp = images / f".tmp-{asset_id}.png"
        if not (tmp.is_file() and tmp.stat().st_size > 0):
            continue
        try:
            result = command_reconcile_image(
                argparse.Namespace(project=project, asset=asset_id, image=tmp)
            )
            resumed.append({"asset": asset_id, "imagePath": result["imagePath"]})
        except WorkflowError as exc:
            resume_failures.append({"id": asset_id, "ok": False, "error": str(exc)})

    book = load_book(project)
    pending_interior = [
        asset_id
        for asset_id in interior_ids(book)
        if not asset_by_id(book, asset_id).get("imagePath")
    ]
    pending_covers = [
        asset_id
        for asset_id in cover_ids(book)
        if not asset_by_id(book, asset_id).get("imagePath")
    ]
    # Covers wait for a complete interior; otherwise they have nothing to match.
    pending = pending_interior or pending_covers
    wave = "interior" if pending_interior else "covers"
    if not pending:
        if next_first_pass_asset(book) is None:
            book["status"] = "draft_ready"
            book["nextAction"] = (
                "Build draft PDF (build --edition draft), verify, show PDF path to user, "
                "and immediately run auto reviewers into output/reviews/"
            )
            save_book(project, book)
        return {
            "ok": len(resume_failures) == 0,
            "mode": "pages-parallel",
            "message": "All PDF pages already have images",
            "resumedFromTmp": resumed,
            "resumeFailures": resume_failures,
            "nextAction": book.get("nextAction")
            or "Build and verify draft PDF, then show user + auto-review",
        }

    workers = getattr(args, "workers", None)
    if workers is None:
        workers = default_codex_workers(len(pending))
    # Still parallel, just not unboundedly so — see MAX_CODEX_WORKERS.
    if workers < 2 and len(pending) > 1:
        workers = min(len(pending), MAX_CODEX_WORKERS)
    timeout = getattr(args, "timeout_sec", None)
    if timeout is None:
        timeout = default_codex_timeout(len(pending), workers)
    batch_args = argparse.Namespace(
        project=project,
        assets=pending,
        timeout_sec=timeout,
        workers=workers,
        _locked=getattr(args, "_locked", False),
    )
    result = command_generate_batch(batch_args)
    book = load_book(project)
    remaining = next_first_pass_asset(book)
    if result.get("ok") and remaining is None:
        book["status"] = "draft_ready"
        book["nextAction"] = (
            "Build draft PDF (build --edition draft), verify, show PDF path to user, "
            "and immediately run auto reviewers into output/reviews/"
        )
        save_book(project, book)
        result["nextAction"] = book["nextAction"]
    elif result.get("ok") and wave == "interior":
        book["nextAction"] = (
            "Interior pages done. Run generate-pages-parallel again to render the "
            "cover(s) last, referencing the finished interior art."
        )
        save_book(project, book)
        result["nextAction"] = book["nextAction"]
    result["mode"] = "pages-parallel"
    result["wave"] = wave
    result["requested"] = pending
    result["pendingCovers"] = pending_covers
    result["workersUsed"] = workers
    result["resumedFromTmp"] = resumed
    if resume_failures:
        result.setdefault("failures", [])
        if isinstance(result["failures"], list):
            result["failures"] = list(result["failures"]) + resume_failures
    return result


def command_generate_book_images(args: argparse.Namespace) -> dict[str, Any]:
    """Prompts folder ready → character-sheet → (accept) → all PDF pages parallel.

    Default pauses after character-sheet for visual accept.
    Pass --auto-accept-character to continue without pause.
    """
    project = require_absolute(args.project, "project")
    with ProjectLock(project, "generate-book-images"):
        return _generate_book_images_locked(args, project)


def _generate_book_images_locked(args: argparse.Namespace, project: Path) -> dict[str, Any]:
    timeout = getattr(args, "timeout_sec", None)
    workers = getattr(args, "workers", None)
    auto_accept = bool(getattr(args, "auto_accept_character", False))

    # Ensure prompts validated / status ready
    book = load_book(project)
    if not book.get("storyPath"):
        raise WorkflowError("Lock story.json before generate-book-images")
    ensure_consent(book)

    prompted = all(
        asset["status"] not in {"planned"} for asset in book["assets"]
    )
    if not prompted or book.get("status") in {"writing_prompts", "interview"}:
        command_validate_prompts(argparse.Namespace(project=project))
        book = load_book(project)

    sheet = asset_by_id(book, "character-sheet")
    steps: dict[str, Any] = {"validated": True}

    # Step A: character-sheet image
    if sheet["status"] != "accepted":
        needs_gen = sheet["status"] in {
            "prompted",
            "needs_revision",
            "planned",
        } or (
            sheet["status"] == "generating" and not sheet.get("imagePath")
        )
        if sheet["status"] == "awaiting_review" and sheet.get("imagePath"):
            needs_gen = False
        elif sheet.get("imagePath") and sheet["status"] in {
            "generated",
            "awaiting_review",
        }:
            needs_gen = False
        else:
            # regenerate if missing image or still prompted
            needs_gen = not sheet.get("imagePath")

        if needs_gen:
            char_result = command_generate_asset(
                argparse.Namespace(
                    project=project,
                    asset="character-sheet",
                    timeout_sec=timeout,
                    workers=workers,
                    _locked=True,
                )
            )
            steps["characterSheet"] = char_result
            book = load_book(project)
            sheet = asset_by_id(book, "character-sheet")

        image_abs = (
            str((project / sheet["imagePath"]).resolve())
            if sheet.get("imagePath")
            else None
        )

        if sheet["status"] != "accepted":
            if auto_accept:
                accept = command_character_review(
                    argparse.Namespace(project=project, accept=True, review=None)
                )
                steps["characterAccept"] = accept
                book = load_book(project)
                sheet = asset_by_id(book, "character-sheet")
            else:
                book["nextAction"] = (
                    "Review character sheet image; if ok run: "
                    f"character-review --accept, then generate-book-images again "
                    f"(or pass --auto-accept-character). Image: {image_abs}"
                )
                save_book(project, book)
                return {
                    "ok": True,
                    "mode": "generate-book-images",
                    "paused": True,
                    "reason": "character_sheet_awaiting_accept",
                    "characterSheetImage": image_abs,
                    "steps": steps,
                    "nextAction": book["nextAction"],
                }

    # Step B: location sheets — one parallel dispatch, before any story page.
    book = load_book(project)
    pending_locations = [
        asset_id
        for asset_id in location_asset_ids(book)
        if not asset_by_id(book, asset_id).get("imagePath")
    ]
    if pending_locations:
        steps["locationSheets"] = command_generate_batch(
            argparse.Namespace(
                project=project,
                assets=pending_locations,
                timeout_sec=timeout,
                workers=workers,
                _locked=True,
            )
        )
        if not steps["locationSheets"].get("ok"):
            return {
                "ok": False,
                "mode": "generate-book-images",
                "paused": False,
                "reason": "location_sheet_failed",
                "steps": steps,
                "nextAction": (
                    "Fix the failed location-sheet prompt(s) and rerun "
                    "generate-book-images. Pages cannot start without them."
                ),
            }

    # Step C: interior pages parallel, then Step D: covers last.
    waves: list[dict[str, Any]] = []
    for _ in range(2):
        wave_result = command_generate_pages_parallel(
            argparse.Namespace(
                project=project,
                timeout_sec=timeout,
                workers=workers,
                _locked=True,
            )
        )
        waves.append(wave_result)
        if not wave_result.get("ok", True):
            break
        if load_book(project).get("status") == "draft_ready":
            break
    steps["pages"] = waves
    book = load_book(project)
    return {
        "ok": all(bool(w.get("ok", True)) for w in waves),
        "mode": "generate-book-images",
        "paused": False,
        "steps": steps,
        "nextAction": book.get("nextAction") or waves[-1].get("nextAction"),
    }


def _check_python_pkg(name: str) -> dict[str, Any]:
    try:
        mod = __import__(name)
        version = getattr(mod, "__version__", "unknown")
        return {"ok": True, "package": name, "version": str(version)}
    except Exception as exc:  # noqa: BLE001 — doctor must never crash
        return {"ok": False, "package": name, "error": str(exc)}


def command_doctor(_args: argparse.Namespace) -> dict[str, Any]:
    """Report whether this machine can run the Hekayati workflow."""
    checks: list[dict[str, Any]] = []

    py_ok = sys.version_info >= (3, 9)
    checks.append(
        {
            "id": "python",
            "ok": py_ok,
            "detail": f"{sys.version.split()[0]} ({sys.executable})",
            "fix": None
            if py_ok
            else "Need Python 3.9+. Run: python3 tools/scripts/story_pipeline.py setup",
        }
    )

    for pkg, import_name in (
        ("pillow", "PIL"),
        ("reportlab", "reportlab"),
        ("pypdf", "pypdf"),
    ):
        result = _check_python_pkg(import_name)
        checks.append(
            {
                "id": pkg,
                "ok": bool(result["ok"]),
                "detail": result.get("version") or result.get("error"),
                "fix": None
                if result["ok"]
                else f"python3 -m pip install -r tools/requirements.txt",
            }
        )

    codex = shutil.which("codex")
    checks.append(
        {
            "id": "codex-cli",
            "ok": bool(codex),
            "detail": codex or "not on PATH",
            "fix": None
            if codex
            else "Install Codex CLI (setup-mac.sh uses brew cask or npm @openai/codex)",
        }
    )

    logged_in = False
    login_detail = "codex missing"
    if codex:
        try:
            proc = subprocess.run(
                [codex, "login", "status"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            login_detail = (proc.stdout or proc.stderr or "").strip() or f"exit {proc.returncode}"
            logged_in = "logged in" in login_detail.lower()
        except Exception as exc:  # noqa: BLE001
            login_detail = str(exc)
    checks.append(
        {
            "id": "codex-login",
            "ok": logged_in,
            "detail": login_detail,
            "fix": None if logged_in else "Run: codex login",
        }
    )

    dispatch_ok = False
    dispatch_path = ""
    try:
        dispatch_path = str(resolve_codex_dispatch())
        dispatch_ok = True
    except WorkflowError as exc:
        dispatch_path = str(exc)
    checks.append(
        {
            "id": "codex-imagegen",
            "ok": dispatch_ok,
            "detail": dispatch_path,
            "fix": None
            if dispatch_ok
            else "Restore .cursor/skills/codex-imagegen or ~/.cursor/skills/codex-imagegen",
        }
    )

    # Ready to run books = everything except login can still be "almost ready".
    install_ok = all(c["ok"] for c in checks if c["id"] != "codex-login")
    ready = all(c["ok"] for c in checks)
    next_action = "ready — say ابدأ / start"
    if not install_ok:
        next_action = "python3 tools/scripts/story_pipeline.py setup"
    elif not logged_in:
        next_action = "codex login"
    return {
        "mode": "doctor",
        "ready": ready,
        "installOk": install_ok,
        "platform": sys.platform,
        "checks": checks,
        "nextAction": next_action,
    }


def command_setup(args: argparse.Namespace) -> dict[str, Any]:
    """Run Mac bootstrap (Homebrew/Python/Codex/pip), then doctor."""
    if sys.platform != "darwin" and not args.force:
        raise WorkflowError(
            "setup targets macOS. On other OS install Python 3.9+, "
            "pip install -r tools/requirements.txt, and Codex CLI manually. "
            "Pass --force to run the Mac script anyway."
        )
    script = skill_scripts_dir() / "setup-mac.sh"
    if not script.is_file():
        raise WorkflowError(f"Missing setup script: {script}")
    proc = subprocess.run(
        ["bash", str(script)],
        cwd=str(skill_scripts_dir().parents[1]),
        check=False,
    )
    doctor = command_doctor(argparse.Namespace())
    return {
        "mode": "setup",
        "setupExitCode": proc.returncode,
        "doctor": doctor,
        "nextAction": doctor.get("nextAction"),
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Hekayati client-project pipeline")
    sub = root.add_subparsers(dest="command", required=True)

    def add_project(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--project",
            required=True,
            type=Path,
            help="Absolute client project folder (all run data saved here)",
        )

    p_doctor = sub.add_parser(
        "doctor",
        help="Check Python, pip deps, Codex CLI, login, and codex-imagegen",
    )
    p_doctor.set_defaults(func=command_doctor)

    p_setup = sub.add_parser(
        "setup",
        help="Mac bootstrap: Homebrew/Python/Codex CLI/pip deps (then doctor)",
    )
    p_setup.add_argument(
        "--force",
        action="store_true",
        help="Run setup-mac.sh even when not on darwin",
    )
    p_setup.set_defaults(func=command_setup)

    p_init = sub.add_parser("init")
    add_project(p_init)
    p_init.add_argument(
        "--pages",
        type=int,
        default=DEFAULT_PDF_PAGES,
        help=f"Total PDF pages including cover+ending (default {DEFAULT_PDF_PAGES})",
    )
    p_init.set_defaults(func=command_init)

    p_pages = sub.add_parser("set-pages", help="Set pdf page count before story lock")
    add_project(p_pages)
    p_pages.add_argument("--pages", type=int, required=True)
    p_pages.set_defaults(func=command_set_pages)

    p_consent = sub.add_parser("confirm-consent")
    add_project(p_consent)
    p_consent.add_argument("--statement", required=True)
    p_consent.set_defaults(func=command_confirm_consent)

    p_list_themes = sub.add_parser(
        "list-themes",
        help="List all art themes from themes/catalog.json (book-start menu)",
    )
    p_list_themes.set_defaults(func=command_list_themes)

    p_age_profiles = sub.add_parser(
        "list-age-profiles",
        help="List age-specific Egyptian-Arabic dictionaries and writing budgets",
    )
    p_age_profiles.set_defaults(func=command_list_age_profiles)

    p_age_profile = sub.add_parser(
        "show-age-profile",
        help="Show the exact writing/narrative profile selected for one age",
    )
    p_age_profile.add_argument("--age", required=True, type=int)
    p_age_profile.set_defaults(func=command_show_age_profile)

    p_theme = sub.add_parser(
        "apply-theme",
        help="Set brief/story themeId+visualStyle from themes/catalog.json; copy style refs",
    )
    add_project(p_theme)
    p_theme.add_argument(
        "--theme",
        required=True,
        help="Theme id from themes/catalog.json (storybook|cartoony|fairytale-glow|feature-cgi|enchanted-glow|wonder-trail)",
    )
    p_theme.set_defaults(func=command_apply_theme)

    p_guests = sub.add_parser(
        "list-guests",
        help="List vetted original guest characters (safe stand-ins for franchises)",
    )
    p_guests.set_defaults(func=command_list_guests)

    p_show_guest = sub.add_parser(
        "show-guest", help="Show one guest entry with its full appearanceNotes"
    )
    p_show_guest.add_argument("--guest", required=True)
    p_show_guest.set_defaults(func=command_show_guest)

    p_templates = sub.add_parser(
        "list-templates",
        help="List ready-made personalized story templates",
    )
    p_templates.add_argument(
        "--category",
        help="Optional exact category filter",
    )
    p_templates.set_defaults(func=command_list_templates)

    p_show_template = sub.add_parser(
        "show-template",
        help="Show one complete ready-made story template",
    )
    p_show_template.add_argument("--template", required=True, help="Template id")
    p_show_template.set_defaults(func=command_show_template)

    p_apply_template = sub.add_parser(
        "apply-template",
        help="Personalize a ready-made template into client input/story.json",
    )
    add_project(p_apply_template)
    p_apply_template.add_argument("--template", required=True, help="Template id")
    p_apply_template.add_argument(
        "--note",
        help="Optional tailoring note kept with the selected template",
    )
    p_apply_template.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing pre-prompt story draft",
    )
    p_apply_template.set_defaults(func=command_apply_template)

    p_template_note = sub.add_parser(
        "set-template-note",
        help="Add, replace, or clear the selected template tailoring note",
    )
    add_project(p_template_note)
    p_template_note.add_argument(
        "--note",
        required=True,
        help="Tailoring note; pass an empty string to clear",
    )
    p_template_note.set_defaults(func=command_set_template_note)

    p_template_done = sub.add_parser(
        "complete-template-customization",
        help="Confirm the template note has been incorporated into story pages",
    )
    add_project(p_template_done)
    p_template_done.set_defaults(func=command_complete_template_customization)

    p_personalize = sub.add_parser(
        "set-personalization",
        help="Record the child's habit focus, traits, and must-appear requests",
    )
    add_project(p_personalize)
    p_personalize.add_argument(
        "--json",
        help=(
            "Personalization payload: {habitFocus, secondaryHabits[], traits[], "
            "requests[]}"
        ),
    )
    p_personalize.add_argument(
        "--file", type=Path, help="Absolute path to a JSON payload file"
    )
    p_personalize.add_argument(
        "--replace",
        action="store_true",
        help="Overwrite the stored block instead of merging into it",
    )
    p_personalize.set_defaults(func=command_set_personalization)

    p_show_personalization = sub.add_parser(
        "show-personalization",
        help="Show the stored personalization block and what it added to mustShow/avoid",
    )
    add_project(p_show_personalization)
    p_show_personalization.set_defaults(func=command_show_personalization)

    p_lock = sub.add_parser("lock-story")
    add_project(p_lock)
    p_lock.add_argument("--story", type=Path, help="Optional path; default input/story.json")
    p_lock.set_defaults(func=command_lock_story)

    p_story_review = sub.add_parser(
        "review-story",
        help="Review age fit, Egyptian wording, clarity, and causal continuity",
    )
    add_project(p_story_review)
    p_story_review.add_argument(
        "--story", type=Path, help="Optional absolute story path; default input/story.json"
    )
    p_story_review.set_defaults(func=command_review_story)

    p_compile = sub.add_parser(
        "compile-prompts",
        help="Rebuild compiledPrompt in every prompt JSON from its structured fields",
    )
    p_compile.add_argument("--project", required=True, type=Path)
    p_compile.set_defaults(func=command_compile_prompts)

    p_validate = sub.add_parser("validate-prompts")
    add_project(p_validate)
    p_validate.set_defaults(func=command_validate_prompts)

    p_begin = sub.add_parser("begin-asset")
    add_project(p_begin)
    p_begin.add_argument("--asset", required=True)
    p_begin.set_defaults(func=command_begin_asset)

    p_reconcile = sub.add_parser("reconcile-image")
    add_project(p_reconcile)
    p_reconcile.add_argument("--asset", required=True)
    p_reconcile.add_argument("--image", required=True, type=Path)
    p_reconcile.set_defaults(func=command_reconcile_image)

    p_char = sub.add_parser("character-review")
    add_project(p_char)
    p_char.add_argument("--accept", action="store_true")
    p_char.add_argument("--review", type=Path)
    p_char.set_defaults(func=command_character_review)

    p_build = sub.add_parser("build")
    add_project(p_build)
    p_build.add_argument("--edition", required=True, choices=["draft", "final"])
    p_build.set_defaults(func=command_build)

    p_verify = sub.add_parser("verify")
    add_project(p_verify)
    p_verify.add_argument("--edition", required=True, choices=["draft", "final"])
    p_verify.set_defaults(func=command_verify)

    p_contact = sub.add_parser("contact-sheet")
    add_project(p_contact)
    p_contact.set_defaults(func=command_contact_sheet)

    p_merge = sub.add_parser("merge-reviews")
    add_project(p_merge)
    p_merge.add_argument("--review", action="append", required=True, type=Path)
    p_merge.set_defaults(func=command_merge_reviews)

    p_status = sub.add_parser("status")
    add_project(p_status)
    p_status.set_defaults(func=command_status)

    def add_codex_args(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--timeout-sec",
            type=int,
            default=None,
            help="Per-job Codex timeout seconds (default 600)",
        )
        p.add_argument(
            "--workers",
            type=int,
            default=None,
            help="Parallel Codex sessions (default min(jobs, 20))",
        )

    p_gen = sub.add_parser(
        "generate-asset",
        help="Begin + Codex $imagegen + reconcile",
    )
    add_project(p_gen)
    add_codex_args(p_gen)
    p_gen.add_argument("--asset", required=True)
    p_gen.set_defaults(func=command_generate_asset)

    p_batch = sub.add_parser(
        "generate-batch",
        help="Batch Codex $imagegen in parallel for listed assets",
    )
    add_project(p_batch)
    add_codex_args(p_batch)
    p_batch.add_argument("--assets", nargs="+", required=True)
    p_batch.set_defaults(func=command_generate_batch)

    p_pages_gen = sub.add_parser(
        "generate-pages-parallel",
        help="Generate all pending PDF pages via parallel Codex $imagegen",
    )
    add_project(p_pages_gen)
    add_codex_args(p_pages_gen)
    p_pages_gen.set_defaults(func=command_generate_pages_parallel)

    p_book_images = sub.add_parser(
        "generate-book-images",
        help=(
            "From prompts folder: character-sheet first, then all PDF pages "
            "(parallel Codex). Pauses for character accept unless "
            "--auto-accept-character."
        ),
    )
    add_project(p_book_images)
    add_codex_args(p_book_images)
    p_book_images.add_argument(
        "--auto-accept-character",
        action="store_true",
        help="Accept character-sheet automatically and continue to all pages",
    )
    p_book_images.set_defaults(func=command_generate_book_images)

    return root


def main() -> None:
    args = parser().parse_args()
    try:
        result = args.func(args)
    except WorkflowError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        sys.exit(1)
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
