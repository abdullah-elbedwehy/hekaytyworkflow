"""Render and parse the editable Markdown story-review checkpoint.

The file is deliberately pleasant to edit in Obsidian while its HTML comments
form a small, strict interchange format.  Only the four story-page fields in
``EDITABLE_FIELDS`` cross the review boundary; persona records and their source
paths are never rendered.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any


EDITABLE_FIELDS = ("text", "beat", "setting", "action")

_FIELD_LABELS = {
    "text": "النص اللي هيظهر في الصفحة",
    "beat": "دور الصفحة في القصة",
    "setting": "وصف المكان",
    "action": "الحركة اللي باينة في المشهد",
}

_PAGE_START_RE = re.compile(
    r'^<!-- hekayati:page:start id="(?P<id>[^"\r\n]+)" -->$', re.MULTILINE
)
_PAGE_END_RE = re.compile(
    r'^<!-- hekayati:page:end id="(?P<id>[^"\r\n]+)" -->$', re.MULTILINE
)
_FIELD_START_RE = re.compile(
    r'^<!-- hekayati:field:start name="(?P<name>[^"\r\n]+)" -->$',
    re.MULTILINE,
)
_FIELD_END_RE = re.compile(
    r'^<!-- hekayati:field:end name="(?P<name>[^"\r\n]+)" -->$',
    re.MULTILINE,
)


class StoryReviewError(ValueError):
    """Raised when a review file cannot be applied safely."""


def _normalise_markdown(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("Markdown text must be a string")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip(" \t") for line in text.split("\n")]
    return "\n".join(lines).rstrip("\n") + "\n"


def normalized_markdown_sha256(text: str) -> str:
    """Hash canonical UTF-8 Markdown, ignoring newline/trailing-space drift."""

    normalised = _normalise_markdown(text)
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def _clean_id(raw_id: Any, *, context: str) -> str:
    if not isinstance(raw_id, str) or not raw_id.strip():
        raise StoryReviewError(f"{context} needs a non-empty string id")
    page_id = raw_id.strip()
    if page_id != raw_id or any(token in page_id for token in ('"', "\n", "\r", "--")):
        raise StoryReviewError(f"Unsafe page id in {context}: {raw_id!r}")
    return page_id


def _story_pages(story: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], list[str]]:
    if not isinstance(story, Mapping):
        raise StoryReviewError("Story must be an object")
    raw_pages = story.get("pages")
    if not isinstance(raw_pages, list) or not raw_pages:
        raise StoryReviewError("Story needs a non-empty pages list")

    pages: list[Mapping[str, Any]] = []
    page_ids: list[str] = []
    for index, page in enumerate(raw_pages, start=1):
        if not isinstance(page, Mapping):
            raise StoryReviewError(f"Story page {index} must be an object")
        page_id = _clean_id(page.get("id"), context=f"story page {index}")
        pages.append(page)
        page_ids.append(page_id)

    duplicates = _duplicates(page_ids)
    if duplicates:
        raise StoryReviewError(f"Duplicate story page ids: {', '.join(duplicates)}")
    return pages, page_ids


def _required_page_value(page: Mapping[str, Any], page_id: str, field: str) -> str:
    value = page.get(field)
    if not isinstance(value, str) or not value.strip():
        raise StoryReviewError(f"Page {page_id!r} needs non-empty {field}")
    return _normalise_field_value(value)


def _normalise_field_value(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = "\n".join(line.rstrip(" \t") for line in value.split("\n"))
    return value.strip()


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        serialisable = value
    else:
        serialisable = str(value)
    return json.dumps(serialisable, ensure_ascii=False)


def _page_heading(page_id: str, position: int, roles: Mapping[str, str] | None = None) -> str:
    """Name each page by its structural role so the editor is never guessing.

    The dedication and «قصص تانية» pages read as ordinary numbered pages
    otherwise, and an editor who does not know they are fixed will happily
    rewrite copy the doctrine owns.
    """
    role = (roles or {}).get(page_id)
    if page_id == "cover":
        label = "الغلاف الأمامي"
    elif page_id == "back-cover":
        label = "الغلاف الخلفي (نص ثابت)"
    elif role == "dedication":
        label = "الإهداء (نص ثابت)"
    elif role == "other-stories":
        label = "قصص تانية (تخطيط ثابت)"
    else:
        # Number by the printed interior page, not by position in the list —
        # `page-02` is the book's second interior page, and an editor counting
        # covers alongside pages will report the wrong page back.
        match = re.fullmatch(r"page-(\d+)", page_id)
        number = int(match.group(1)) if match else position
        label = f"الصفحة {number}"
    return f"## {label} — `{page_id}`"


def _structure_roles(page_count: int) -> dict[str, str]:
    """Structural role per page id, or an empty map if the doctrine is unusable.

    Rendering the review file must never be what blocks a book, so a doctrine
    problem downgrades the headings instead of raising here — `check-doctrine`
    is where that failure belongs.
    """
    try:
        import doctrine  # local import keeps this module standalone for tests

        return doctrine.structure_slot_roles(page_count)
    except Exception:  # noqa: BLE001
        return {}


def render_story_review(
    story: Mapping[str, Any],
    story_sha256: str,
    revision: Any,
    prepared_at: Any,
) -> str:
    """Render one complete, Obsidian-friendly story review document."""

    pages, page_ids = _story_pages(story)
    title = story.get("title", story.get("titleAr"))
    if not isinstance(title, str) or not title.strip():
        raise StoryReviewError("Story needs a non-empty title")
    target_age = story.get("targetAge", story.get("age"))
    if target_age is None or isinstance(target_age, bool):
        raise StoryReviewError("Story needs targetAge metadata")
    if not isinstance(story_sha256, str) or not story_sha256.strip():
        raise StoryReviewError("story_sha256 must be non-empty")
    if prepared_at is None or not str(prepared_at).strip():
        raise StoryReviewError("prepared_at must be non-empty")

    display_title = " ".join(title.splitlines()).strip()
    lines = [
        "---",
        "review_type: hekayati-story",
        "schema_version: 1",
        f"title: {_yaml_scalar(title.strip())}",
        f"target_age: {_yaml_scalar(target_age)}",
        f"page_count: {len(page_ids)}",
        f"story_sha256: {_yaml_scalar(story_sha256.strip())}",
        f"revision: {_yaml_scalar(revision)}",
        f"prepared_at: {_yaml_scalar(prepared_at)}",
        "---",
        "",
        f"# مراجعة قصة: {display_title}",
        "",
        "> [!warning] مهم قبل ما تخلص المراجعة",
        "> عدّل المحتوى جوه الأربع خانات بس. ماتغيّرش، ماتنقلش، ولا تمسح "
        "أي علامة HTML بتبدأ بـ `hekayati:` عشان الملف يتقري صح.",
        "",
    ]

    roles = _structure_roles(len(page_ids))
    for position, (page, page_id) in enumerate(zip(pages, page_ids), start=1):
        lines.extend(
            [
                f'<!-- hekayati:page:start id="{page_id}" -->',
                _page_heading(page_id, position, roles),
                "",
            ]
        )
        if roles.get(page_id) in {"dedication", "other-stories"}:
            lines.extend(
                [
                    "> [!note] الصفحة دي ثابتة",
                    "> نصها بيتكتب من الـhandoff. سيبها زي ما هي إلا لو عمر غيّر القاعدة نفسها.",
                    "",
                ]
            )
        for field in EDITABLE_FIELDS:
            lines.extend(
                [
                    f"### {_FIELD_LABELS[field]}",
                    f'<!-- hekayati:field:start name="{field}" -->',
                    _required_page_value(page, page_id, field),
                    f'<!-- hekayati:field:end name="{field}" -->',
                    "",
                ]
            )
        lines.extend(
            [
                f'<!-- hekayati:page:end id="{page_id}" -->',
                "",
                "---",
                "",
            ]
        )

    return _normalise_markdown("\n".join(lines))


def _duplicates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _validated_expected_ids(expected_ids: Iterable[str]) -> list[str]:
    if isinstance(expected_ids, (str, bytes)):
        raise StoryReviewError("expected_ids must be a sequence of page ids")
    try:
        ids = [
            _clean_id(page_id, context="expected_ids")
            for page_id in expected_ids
        ]
    except TypeError as exc:
        raise StoryReviewError("expected_ids must be iterable") from exc
    if not ids:
        raise StoryReviewError("expected_ids cannot be empty")
    duplicates = _duplicates(ids)
    if duplicates:
        raise StoryReviewError(f"Duplicate expected page ids: {', '.join(duplicates)}")
    return ids


def _validate_marker_ids(
    actual_ids: list[str], expected_ids: list[str], *, marker_kind: str
) -> None:
    duplicates = _duplicates(actual_ids)
    if duplicates:
        raise StoryReviewError(
            f"Duplicate {marker_kind} page markers: {', '.join(duplicates)}"
        )
    unknown = [page_id for page_id in actual_ids if page_id not in expected_ids]
    if unknown:
        raise StoryReviewError(
            f"Unknown {marker_kind} page ids: {', '.join(unknown)}"
        )
    missing = [page_id for page_id in expected_ids if page_id not in actual_ids]
    if missing:
        raise StoryReviewError(
            f"Missing {marker_kind} page ids: {', '.join(missing)}"
        )
    if actual_ids != expected_ids:
        raise StoryReviewError(f"{marker_kind.capitalize()} page ids are out of order")


def _page_spans(markdown: str, expected_ids: list[str]) -> list[tuple[str, int, int]]:
    starts = list(_PAGE_START_RE.finditer(markdown))
    ends = list(_PAGE_END_RE.finditer(markdown))
    _validate_marker_ids(
        [match.group("id") for match in starts],
        expected_ids,
        marker_kind="start",
    )
    _validate_marker_ids(
        [match.group("id") for match in ends],
        expected_ids,
        marker_kind="end",
    )

    events = sorted(
        [
            *((match.start(), "start", match.group("id"), match) for match in starts),
            *((match.start(), "end", match.group("id"), match) for match in ends),
        ],
        key=lambda event: event[0],
    )
    expected_events = [
        event
        for page_id in expected_ids
        for event in (("start", page_id), ("end", page_id))
    ]
    if [(kind, page_id) for _, kind, page_id, _ in events] != expected_events:
        raise StoryReviewError("Page markers are nested, mismatched, or out of order")

    spans: list[tuple[str, int, int]] = []
    for index, page_id in enumerate(expected_ids):
        start_match = events[index * 2][3]
        end_match = events[index * 2 + 1][3]
        spans.append((page_id, start_match.end(), end_match.start()))
    return spans


def _parse_page_fields(page_id: str, block: str) -> dict[str, str]:
    starts = list(_FIELD_START_RE.finditer(block))
    ends = list(_FIELD_END_RE.finditer(block))
    start_names = [match.group("name") for match in starts]
    end_names = [match.group("name") for match in ends]

    unknown = [
        name
        for name in [*start_names, *end_names]
        if name not in EDITABLE_FIELDS
    ]
    if unknown:
        raise StoryReviewError(
            f"Page {page_id!r} has unknown field markers: {', '.join(dict.fromkeys(unknown))}"
        )

    for field in EDITABLE_FIELDS:
        start_count = start_names.count(field)
        end_count = end_names.count(field)
        if start_count > 1 or end_count > 1:
            raise StoryReviewError(
                f"Page {page_id!r} has duplicate {field} field markers"
            )
        if start_count != 1 or end_count != 1:
            raise StoryReviewError(
                f"Page {page_id!r} is missing {field} field markers"
            )

    events = sorted(
        [
            *((match.start(), "start", match.group("name"), match) for match in starts),
            *((match.start(), "end", match.group("name"), match) for match in ends),
        ],
        key=lambda event: event[0],
    )
    if len(events) != len(EDITABLE_FIELDS) * 2:
        raise StoryReviewError(f"Page {page_id!r} has an invalid field-marker count")
    for index in range(0, len(events), 2):
        start_event = events[index]
        end_event = events[index + 1]
        if start_event[1] != "start" or end_event[1] != "end":
            raise StoryReviewError(f"Page {page_id!r} has malformed field markers")
        if start_event[2] != end_event[2]:
            raise StoryReviewError(f"Page {page_id!r} has nested field markers")

    edits: dict[str, str] = {}
    starts_by_name = {match.group("name"): match for match in starts}
    ends_by_name = {match.group("name"): match for match in ends}
    for field in EDITABLE_FIELDS:
        value = _normalise_field_value(
            block[starts_by_name[field].end() : ends_by_name[field].start()]
        )
        if not value:
            raise StoryReviewError(f"Page {page_id!r} has an empty {field} value")
        edits[field] = value
    return edits


def parse_story_review(
    markdown: str, expected_ids: Iterable[str]
) -> dict[str, dict[str, str]]:
    """Parse a complete review file and reject any structural drift."""

    normalised = _normalise_markdown(markdown)
    ids = _validated_expected_ids(expected_ids)
    edits: dict[str, dict[str, str]] = {}
    for page_id, start, end in _page_spans(normalised, ids):
        edits[page_id] = _parse_page_fields(page_id, normalised[start:end])
    return edits


def apply_story_review(
    story: Mapping[str, Any], edits: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Return a deep-copied story with one validated edit set per page."""

    pages, page_ids = _story_pages(story)
    if not isinstance(edits, Mapping):
        raise StoryReviewError("Story review edits must be an object keyed by page id")

    edit_ids = list(edits.keys())
    if not all(isinstance(page_id, str) for page_id in edit_ids):
        raise StoryReviewError("Story review edit ids must be strings")
    unknown = [page_id for page_id in edit_ids if page_id not in page_ids]
    if unknown:
        raise StoryReviewError(f"Unknown story review edit ids: {', '.join(unknown)}")
    missing = [page_id for page_id in page_ids if page_id not in edits]
    if missing:
        raise StoryReviewError(f"Missing story review edits: {', '.join(missing)}")

    validated: dict[str, dict[str, str]] = {}
    for page_id in page_ids:
        page_edits = edits[page_id]
        if not isinstance(page_edits, Mapping):
            raise StoryReviewError(f"Review edits for {page_id!r} must be an object")
        unknown_fields = [field for field in page_edits if field not in EDITABLE_FIELDS]
        if unknown_fields:
            raise StoryReviewError(
                f"Review edits for {page_id!r} have unknown fields: "
                + ", ".join(str(field) for field in unknown_fields)
            )
        missing_fields = [field for field in EDITABLE_FIELDS if field not in page_edits]
        if missing_fields:
            raise StoryReviewError(
                f"Review edits for {page_id!r} are missing fields: "
                + ", ".join(missing_fields)
            )
        validated[page_id] = {}
        for field in EDITABLE_FIELDS:
            value = page_edits[field]
            if not isinstance(value, str):
                raise StoryReviewError(
                    f"Review edit {page_id!r}.{field} must be a string"
                )
            clean_value = _normalise_field_value(value)
            if not clean_value:
                raise StoryReviewError(
                    f"Review edit {page_id!r}.{field} cannot be empty"
                )
            validated[page_id][field] = clean_value

    updated = copy.deepcopy(dict(story))
    updated_pages = updated["pages"]
    for page in updated_pages:
        page_id = page["id"]
        page.update(validated[page_id])
    return updated


__all__ = [
    "EDITABLE_FIELDS",
    "StoryReviewError",
    "apply_story_review",
    "normalized_markdown_sha256",
    "parse_story_review",
    "render_story_review",
]
