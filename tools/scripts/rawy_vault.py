"""Rawy: one Obsidian-first operating surface for Hekayati clients.

Tracked files define the portable vault shell. Private client folders and the
generated statistics note stay local and Git-ignored.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from progress import book_progress


CLIENTS_DIRNAME = "Clients"
CLIENT_NOTE = "Client.md"
GALLERY_NOTE = "Gallery.md"
ARCHIVE_NOTE = "Archive.md"
GENERATED_START = "<!-- rawy:generated:start -->"
GENERATED_END = "<!-- rawy:generated:end -->"
NOTES_MARKER = "<!-- rawy:notes -->"
# One reviewable comment box per image. The operator types between the markers;
# every re-sync reads them back and writes them out again, so a note survives
# regenerating the gallery — losing a reviewer's comment silently is worse than
# not offering the box at all.
IMAGE_NOTE_RE = re.compile(
    r"<!-- rawy-image-note:(?P<asset>[^:>\s]+):start -->(?P<body>.*?)"
    r"<!-- rawy-image-note:(?P=asset):end -->",
    re.DOTALL,
)
TEXT_SUFFIXES = {".json", ".md", ".txt"}


class RawyError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def rawy_root(root: Path | None = None) -> Path:
    return (Path(root).resolve() if root else repo_root()) / "Rawy"


def clients_root(root: Path | None = None) -> Path:
    return rawy_root(root) / CLIENTS_DIRNAME


def is_rawy_client(project: Path, root: Path | None = None) -> bool:
    project = Path(project).resolve()
    parent = clients_root(root).resolve()
    return project.parent == parent


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = text if text.endswith("\n") else text + "\n"
    path.write_text(payload, encoding="utf-8")
    return path


def _write_json(path: Path, payload: Any) -> Path:
    return _write(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _yaml_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(str(value), ensure_ascii=False)


def _parse_yaml_value(value: str) -> Any:
    raw = value.strip()
    if raw in {"null", "~"}:
        return None
    if raw in {"true", "false"}:
        return raw == "true"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        if re.fullmatch(r"-?\d+", raw):
            return int(raw)
        if re.fullmatch(r"-?\d+\.\d+", raw):
            return float(raw)
        return raw


def read_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        return {}, ""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    values: dict[str, Any] = {}
    for line in text[4:end].splitlines():
        if not line or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key:
            values[key] = _parse_yaml_value(value)
    return values, text[end + 5 :]


def render_frontmatter(values: Mapping[str, Any]) -> str:
    lines = ["---"]
    for key, value in values.items():
        lines.append(f"{key}: {_yaml_value(value)}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9\u0600-\u06ff_-]+", "-", value.strip())
    slug = re.sub(r"-{2,}", "-", slug).strip("-_")
    if not slug or slug in {".", ".."}:
        raise RawyError("Client slug is empty after normalization")
    return slug.lower() if slug.isascii() else slug


def _read_book(project: Path) -> dict[str, Any] | None:
    path = project / "output" / "book.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RawyError(f"Invalid book manifest: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RawyError(f"Book manifest must be an object: {path}")
    return payload


def _read_brief(project: Path) -> dict[str, Any]:
    path = project / "input" / "brief.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _book_title(project: Path, book: Mapping[str, Any], brief: Mapping[str, Any]) -> str:
    story_path = project / str(book.get("storyPath") or "input/story.json")
    if story_path.is_file():
        try:
            story = json.loads(story_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            story = {}
        if isinstance(story, dict):
            title = _first_text(story.get("title"), story.get("titleAr"))
            if title:
                return title
    return _first_text(brief.get("title"))


def _request_text(book: Mapping[str, Any], brief: Mapping[str, Any]) -> str:
    goal = book.get("storyGoal") or brief.get("storyGoal") or {}
    goal_text = ""
    if isinstance(goal, dict):
        goal_text = _first_text(goal.get("goalAr"), goal.get("goal"))
    return _first_text(brief.get("purpose"), goal_text, brief.get("outline"))


def _default_client_name(project: Path, brief: Mapping[str, Any]) -> str:
    for persona in brief.get("personas") or []:
        if isinstance(persona, dict):
            name = _first_text(persona.get("displayName"))
            if name:
                return name
    return project.name


def _next_action_label(
    book: Mapping[str, Any], progress: Mapping[str, Any], status: str
) -> str:
    story_review = str((book.get("storyReview") or {}).get("status") or "")
    if story_review in {"prepared", "awaiting_user", "pending", "stale"}:
        return "راجع القصة واعتمدها / Review and approve the story"
    prompt_review = str((book.get("promptApproval") or {}).get("status") or "")
    if prompt_review in {"prepared", "awaiting_user", "pending", "stale"}:
        return "راجع حزمة أوصاف الرسم واعتمدها / Review and approve the prompt pack"
    selected_lane = str((book.get("imageLane") or {}).get("selected") or "")
    if prompt_review == "approved" and not selected_lane:
        return "اختار مسار توليد الصور / Choose the image lane"
    phase = str(progress.get("phase") or "setup")
    labels = {
        "setup": "استكمال البيانات والموافقة / Complete intake and consent",
        "story": "استكمال القصة ومراجعتها / Complete and review the story",
        "prompts": "تجهيز أوصاف الرسومات / Prepare illustration prompts",
        "character_sheet": "مراجعة شكل الشخصيات / Review the character sheet",
        "location_sheets": "استكمال أوراق الأماكن / Complete location sheets",
        "interior": "استكمال رسومات الصفحات / Complete page illustrations",
        "covers": "تجهيز الغلافين / Prepare both covers",
        "draft_pdf": "تجهيز ومراجعة نسخة PDF / Build and verify the draft PDF",
        "review": "مراجعة الكتاب وإصلاح الملاحظات / Review and resolve findings",
        "final_pdf": "الموافقة النهائية والنسخة الأخيرة / Final approval and PDF",
    }
    if status == "completed":
        return "مكتمل / Complete"
    return labels.get(phase, "راجع حالة الطلب / Review the order")


def _status_from_book(book: Mapping[str, Any], progress: Mapping[str, Any]) -> str:
    final = ((book.get("pdf") or {}).get("final") or {}).get("status")
    if final == "verified" or progress.get("percent") == 100:
        return "completed"
    story_review = (book.get("storyReview") or {}).get("status")
    if story_review in {"prepared", "awaiting_user", "pending", "stale"}:
        return "waiting"
    assets = book.get("assets") or []
    if any(
        isinstance(asset, dict)
        and asset.get("id") == "character-sheet"
        and asset.get("status") in {"awaiting_review", "generated"}
        for asset in assets
    ):
        return "waiting"
    return "active"


def _relative_link(rawy: Path, path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    try:
        return path.resolve().relative_to(rawy.resolve()).as_posix()
    except ValueError:
        return ""


def _generated_client_values(
    project: Path,
    existing: Mapping[str, Any],
    book: Mapping[str, Any] | None,
) -> dict[str, Any]:
    brief = _read_brief(project)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    values: dict[str, Any] = dict(existing)
    values.setdefault("type", "rawy-client")
    values.setdefault("cssclasses", ["rawy-client"])
    if values.get("cssclasses") == "rawy-client":
        values["cssclasses"] = ["rawy-client"]
    values.setdefault("client_name", _default_client_name(project, brief))
    values.setdefault("phone", "")
    values.setdefault("request", _request_text(book or {}, brief))
    created = ""
    if book:
        created = str(book.get("createdAt") or "")[:10]
    values.setdefault("created", created or date.today().isoformat())
    values.setdefault("deadline", "")
    values.setdefault("payment", "unknown")
    values.setdefault("priority", "normal")
    values.setdefault("blocker", "")
    # Archiving is a property, not a folder move: one checkbox in Obsidian's
    # own property editor takes a finished client out of every active view, and
    # unticking it brings them back with their history intact.
    values.setdefault("archived", False)
    archived = bool(values.get("archived"))
    if not book:
        values.update(
            {
                "status": "new",
                "book_title": "",
                "progress": 0,
                "phase": "intake",
                "phase_label": "بيانات العميل / Client intake",
                "next_action": "",
                "story_review_status": "not_started",
                "draft_pdf": "",
                "final_pdf": "",
                "needs_attention": False,
                "updated": now,
            }
        )
        return values

    progress = book_progress(dict(book))
    status = _status_from_book(book, progress)
    rawy = rawy_root()
    draft_value = ((book.get("pdf") or {}).get("draft") or {}).get("path")
    final_value = ((book.get("pdf") or {}).get("final") or {}).get("path")
    draft = project / str(draft_value) if draft_value else None
    final = project / str(final_value) if final_value else None
    blocker = _first_text(values.get("blocker"))
    values.update(
        {
            "status": status,
            "book_title": _book_title(project, book, brief),
            "progress": int(progress.get("percent") or 0),
            "phase": str(progress.get("phase") or "unknown"),
            "phase_label": _first_text(
                progress.get("phaseLabelAr"), progress.get("phaseLabelEn")
            ),
            "next_action": _next_action_label(book, progress, status),
            "story_review_status": str(
                (book.get("storyReview") or {}).get("status") or "not_started"
            ),
            "draft_pdf": _relative_link(rawy, draft),
            "final_pdf": _relative_link(rawy, final),
            # An archived client never asks for attention, however it was left.
            "needs_attention": bool(not archived and (blocker or status == "waiting")),
            "updated": str(book.get("updatedAt") or now),
        }
    )
    return values


def _preserved_notes(body: str) -> str:
    if NOTES_MARKER not in body:
        return ""
    notes = body.split(NOTES_MARKER, 1)[1].lstrip("\n")
    lines = notes.splitlines()
    if lines and lines[0].strip() == "## ملاحظات / Notes":
        lines = lines[1:]
    return "\n".join(lines).strip()


def _client_link(project: Path, relative: str, label: str) -> str:
    path = project / relative
    if not path.is_file():
        return ""
    vault_relative = path.resolve().relative_to(rawy_root().resolve()).as_posix()
    if path.suffix.lower() == ".md":
        return f"[[{vault_relative[:-3]}|{label}]]"
    return f"[[{vault_relative}|{label}]]"


def _vault_link(relative: str, label: str) -> str:
    path = rawy_root() / relative
    if not path.is_file():
        return ""
    if path.suffix.lower() == ".md":
        return f"[[{relative[:-3]}|{label}]]"
    return f"[[{relative}|{label}]]"


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
# Where a finished asset sits in the book, so the gallery reads in reading order
# instead of alphabetically (page-10 before page-2).
_SHEET_PREFIXES = ("character-sheet", "location-sheet")


def _asset_sort_key(asset_id: str) -> tuple[int, int, str]:
    if asset_id.startswith(_SHEET_PREFIXES):
        return (0, 0, asset_id)
    if asset_id == "cover":
        return (1, 0, asset_id)
    if asset_id == "back-cover":
        return (3, 0, asset_id)
    match = re.match(r"^page-(\d+)$", asset_id)
    if match:
        return (2, int(match.group(1)), asset_id)
    return (4, 0, asset_id)


def _gallery_rows(project: Path, book: Mapping[str, Any] | None) -> list[dict[str, str]]:
    """Every asset that has an image on disk, in book order."""
    rows: list[dict[str, str]] = []
    if not book:
        return rows
    rawy = rawy_root().resolve()
    for asset in book.get("assets") or []:
        if not isinstance(asset, Mapping):
            continue
        relative = str(asset.get("imagePath") or "").strip()
        if not relative:
            continue
        path = project / relative
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        try:
            vault_relative = path.resolve().relative_to(rawy).as_posix()
        except ValueError:
            continue
        rows.append(
            {
                "id": str(asset.get("id") or ""),
                "status": str(asset.get("status") or ""),
                "embed": vault_relative,
            }
        )
    rows.sort(key=lambda row: _asset_sort_key(row["id"]))
    return rows


def read_image_notes(project: Path) -> dict[str, str]:
    """Whatever the operator has written under each image, by asset id."""
    gallery = Path(project) / GALLERY_NOTE
    if not gallery.is_file():
        return {}
    notes: dict[str, str] = {}
    for match in IMAGE_NOTE_RE.finditer(gallery.read_text(encoding="utf-8")):
        # The box lives inside a callout, so every line carries a "> " prefix
        # that belongs to the markup rather than to what was typed.
        lines = [
            re.sub(r"^\s*>\s?", "", line).rstrip()
            for line in match.group("body").splitlines()
        ]
        body = "\n".join(lines).strip()
        if body:
            notes[match.group("asset")] = body
    return notes


def _gallery_entry(row: Mapping[str, str], note: str) -> list[str]:
    """One image, plus the box the operator writes their objection into.

    The callout is collapsed (`-`) when empty so the page stays a gallery, and
    expanded (`+`) once something is written, so an image that needs work is
    visible while scrolling instead of hidden behind a fold.
    """
    asset_id = row["id"]
    body = note.strip()
    fold = "+" if body else "-"
    label = "✏️ ملاحظتك / Your note" + (" — محتاجة شغل" if body else "")
    quoted = [f"> {line}".rstrip() for line in body.splitlines()] if body else ["> "]
    return [
        f"### {asset_id} · {row['status']}",
        "",
        f"![[{row['embed']}]]",
        "",
        f"> [!rawy-note]{fold} {label}",
        f"> <!-- rawy-image-note:{asset_id}:start -->",
        *quoted,
        f"> <!-- rawy-image-note:{asset_id}:end -->",
        "",
    ]


def _gallery_body(
    project: Path,
    values: Mapping[str, Any],
    rows: list[dict[str, str]],
    notes: Mapping[str, str] | None = None,
) -> str:
    client_name = values.get("client_name") or project.name
    slug = project.name
    lines = [
        "---",
        "cssclasses: [rawy-gallery]",
        "---",
        "",
        f"# صور {client_name}",
        "",
        "> [!rawy-actions]",
        f"> [[Clients/{slug}/Client|↩︎ رجوع للعميل / Back to client]]",
        "> [[Dashboard|راوي / Dashboard]]",
        "",
    ]
    if not rows:
        lines += [
            "مفيش صور اتعملت لسه.",
            "",
            "*No images generated yet.*",
            "",
        ]
        return "\n".join(lines)

    notes = dict(notes or {})
    flagged = [row["id"] for row in rows if notes.get(row["id"])]
    lines += [
        f"**{len(rows)}** صورة / images"
        + (f" · **{len(flagged)}** عليها ملاحظات / with notes" if flagged else ""),
        "",
    ]
    if flagged:
        lines += [
            "> [!rawy-blocker] صور عليها ملاحظات / Images with notes",
            "> " + "، ".join(flagged),
            "",
        ]
    lines += [
        "> [!rawy-action] المراجعة / Review",
        "> اكتب ملاحظتك تحت أي صورة مش عاجباك، وبعدين قول لي في الشات وأنا هعيد",
        "> الصورة دي بس. لو كله تمام، قول لي وهبدأ الـPDF.",
        ">",
        "> *Write a note under any image you want changed, then tell me in chat —"
        " I redo only that image. If everything is fine, say so and I build the PDF.*",
        "",
    ]
    groups = (
        ("الشيتات المرجعية / Reference sheets", lambda i: i.startswith(_SHEET_PREFIXES)),
        ("الأغلفة / Covers", lambda i: i in {"cover", "back-cover"}),
        ("الصفحات / Pages", lambda i: i.startswith("page-")),
    )
    seen: set[str] = set()
    for title, matches in groups:
        section = [row for row in rows if matches(row["id"]) and row["id"] not in seen]
        if not section:
            continue
        seen.update(row["id"] for row in section)
        lines += [f"## {title}", ""]
        for row in section:
            lines += _gallery_entry(row, notes.get(row["id"], ""))
    leftovers = [row for row in rows if row["id"] not in seen]
    if leftovers:
        lines += ["## غير مصنّف / Other", ""]
        for row in leftovers:
            lines += _gallery_entry(row, notes.get(row["id"], ""))
    return "\n".join(lines)


def _client_body(project: Path, values: Mapping[str, Any], notes: str) -> str:
    payment_labels = {
        "unknown": "غير محدد / Unknown",
        "not_paid": "لم يُدفع / Not paid",
        "deposit": "عربون / Deposit",
        "paid": "مدفوع / Paid",
    }
    priority_labels = {
        "normal": "عادي / Normal",
        "high": "عالي / High",
        "urgent": "مستعجل / Urgent",
    }
    status_labels = {
        "new": "جديد / New",
        "active": "شغّال / Active",
        "waiting": "مستني مراجعة / Waiting",
        "completed": "مكتمل / Completed",
    }
    links = [
        _client_link(project, "input/story-review.md", "مراجعة القصة / Story review"),
        _vault_link(str(values.get("draft_pdf") or ""), "PDF مسودة / Draft PDF")
        if values.get("draft_pdf")
        else "",
        _vault_link(str(values.get("final_pdf") or ""), "PDF نهائي / Final PDF")
        if values.get("final_pdf")
        else "",
    ]
    link_lines = [f"- {link}" for link in links if link]
    if not link_lines:
        link_lines = ["- مفيش ملفات مراجعة جاهزة / No review files ready"]
    next_action = _first_text(values.get("next_action")) or "—"
    request = _first_text(values.get("request")) or "—"
    # The newest PDF is the one worth a button; the Files list below still holds
    # both editions.
    pdf_button = ""
    for key, label in (("final_pdf", "📕 PDF نهائي / Final PDF"), ("draft_pdf", "📄 PDF مسودة / Draft PDF")):
        link = _vault_link(str(values.get(key) or ""), label) if values.get(key) else ""
        if link:
            pdf_button = link
            break
    flagged = read_image_notes(project)
    gallery_label = "🖼️ صور الكتاب / Book images"
    if flagged:
        gallery_label = f"🖼️ صور الكتاب — {len(flagged)} ملاحظة / {len(flagged)} noted"
    archived = bool(values.get("archived"))
    archive_label = (
        "📦 الأرشيف / Archive"
        if not archived
        else "📦 العميل مؤرشف / Client archived"
    )
    return "\n".join(
        [
            GENERATED_START,
            f"# {values.get('client_name') or project.name}",
            "",
            # One row of real buttons. `rawy-actions` is styled by the vault CSS
            # snippet, so these render as tappable pills rather than a list of
            # links — the gallery is one click from the client, not four.
            "> [!rawy-actions]",
            f"> [[Clients/{project.name}/Gallery|{gallery_label}]]",
            *([f"> {pdf_button}"] if pdf_button else []),
            "> [[Dashboard|🏠 راوي / Dashboard]]",
            f"> [[Archive|{archive_label}]]",
            "",
            "> [!rawy-progress] الحالة / Status",
            f"> **{int(values.get('progress') or 0)}%** · "
            f"{status_labels.get(str(values.get('status')), str(values.get('status')))}",
            f"> {values.get('phase_label') or 'بيانات العميل / Client intake'}",
            "",
            "## بيانات العميل / Client",
            "",
            f"- **الاسم / Name:** {values.get('client_name') or '—'}",
            f"- **رقم التليفون / Phone:** {values.get('phone') or '—'}",
            f"- **تاريخ الإنشاء / Created:** {values.get('created') or '—'}",
            f"- **المطلوب / Request:** {request}",
            "",
            "## التنفيذ / Production",
            "",
            f"- **الكتاب / Book:** {values.get('book_title') or '—'}",
            f"- **الموعد / Deadline:** {values.get('deadline') or '—'}",
            f"- **الدفع / Payment:** {payment_labels.get(str(values.get('payment')), '—')}",
            f"- **الأولوية / Priority:** {priority_labels.get(str(values.get('priority')), '—')}",
            "",
            "> [!rawy-action] الخطوة الجاية / Next action",
            f"> {next_action}",
            "",
            "> [!rawy-blocker] العائق / Blocker",
            f"> {_first_text(values.get('blocker')) or 'مفيش / None'}",
            "",
            "## الملفات / Files",
            "",
            *link_lines,
            "",
            GENERATED_END,
            "",
            NOTES_MARKER,
            "## ملاحظات / Notes",
            "",
            notes.rstrip(),
            "",
        ]
    )


def sync_client(project: Path) -> dict[str, Any]:
    project = Path(project).resolve()
    if not project.is_dir():
        raise RawyError(f"Client folder does not exist: {project}")
    if not is_rawy_client(project):
        raise RawyError(f"Client must be inside {clients_root()}: {project}")
    note = project / CLIENT_NOTE
    existing, body = read_frontmatter(note)
    book = _read_book(project)
    values = _generated_client_values(project, existing, book)
    _write(note, render_frontmatter(values) + _client_body(project, values, _preserved_notes(body)))
    rows = _gallery_rows(project, book)
    # Read the operator's notes before rewriting the file they live in.
    image_notes = read_image_notes(project)
    gallery = _write(
        project / GALLERY_NOTE, _gallery_body(project, values, rows, image_notes)
    )
    flagged = sorted(asset for asset in image_notes if asset)
    return {
        "client": str(project),
        "note": str(note),
        "gallery": str(gallery),
        "images": len(rows),
        "imageNotes": flagged,
        "archived": bool(values.get("archived")),
        "properties": values,
    }


def set_archived(project: Path, *, archived: bool) -> dict[str, Any]:
    """Archive or restore one client.

    Nothing moves and nothing is deleted: the note keeps a single `archived`
    property, every active view filters on it, and the Archive note lists what
    it hides. A client can be brought back with the same call, or by unticking
    the box in Obsidian's own property editor — which is the point of storing it
    as a property rather than as a folder move.
    """
    project = Path(project).resolve()
    if not is_rawy_client(project):
        raise RawyError(f"Client must be inside {clients_root()}: {project}")
    note = project / CLIENT_NOTE
    if not note.is_file():
        raise RawyError(f"Client note is missing: {note}")
    existing, _ = read_frontmatter(note)
    was = bool(existing.get("archived"))
    existing["archived"] = bool(archived)
    if archived:
        existing["archived_at"] = date.today().isoformat()
    else:
        existing.pop("archived_at", None)
    _write(note, render_frontmatter(existing) + read_frontmatter(note)[1])
    result = sync_client(project)
    return {
        "client": str(project),
        "archived": bool(archived),
        "changed": was != bool(archived),
        "note": result["note"],
    }


def archived_clients() -> list[dict[str, Any]]:
    clients = clients_root()
    if not clients.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for project in sorted(path for path in clients.iterdir() if path.is_dir()):
        note = project / CLIENT_NOTE
        if not note.is_file():
            continue
        values, _ = read_frontmatter(note)
        if values.get("type") != "rawy-client" or not values.get("archived"):
            continue
        rows.append(
            {
                "slug": project.name,
                "client_name": str(values.get("client_name") or project.name),
                "book_title": str(values.get("book_title") or ""),
                "archived_at": str(values.get("archived_at") or ""),
            }
        )
    return rows


def create_client(
    *,
    name: str,
    phone: str,
    request: str,
    created: str | None = None,
    slug: str | None = None,
) -> dict[str, Any]:
    if not name.strip():
        raise RawyError("Client name is required")
    if not phone.strip():
        raise RawyError("Client phone is required")
    if not request.strip():
        raise RawyError("Client request is required")
    created_value = (created or date.today().isoformat()).strip()
    try:
        date.fromisoformat(created_value)
    except ValueError as exc:
        raise RawyError("created must use YYYY-MM-DD") from exc
    client_slug = safe_slug(slug or name)
    project = clients_root() / client_slug
    if project.exists():
        raise RawyError(f"Client already exists: {project}")
    project.mkdir(parents=True)
    values = {
        "type": "rawy-client",
        "cssclasses": ["rawy-client"],
        "client_name": name.strip(),
        "phone": phone.strip(),
        "request": request.strip(),
        "created": created_value,
        "deadline": "",
        "payment": "unknown",
        "priority": "normal",
        "blocker": "",
    }
    _write(project / CLIENT_NOTE, render_frontmatter(values) + _client_body(project, _generated_client_values(project, values, None), ""))
    sync_rawy()
    return {"client": str(project), "note": str(project / CLIENT_NOTE)}


def write_obsidian_config(root: Path | None = None) -> list[Path]:
    """Write the core-only Obsidian configuration. Rawy uses no community plugins."""

    rawy = rawy_root(root)
    config = rawy / ".obsidian"
    core_plugins = {
        "file-explorer": True,
        "global-search": True,
        "switcher": True,
        "graph": False,
        "backlink": False,
        "outgoing-link": False,
        "tag-pane": False,
        "page-preview": True,
        "templates": False,
        "note-composer": False,
        "command-palette": True,
        "editor-status": False,
        "bookmarks": True,
        "outline": False,
        "word-count": False,
        "file-recovery": True,
        "properties": False,
        "bases": True,
    }
    return [
        _write_json(
            config / "app.json",
            {
                "rightToLeft": False,
                "readableLineLength": False,
                "alwaysUpdateLinks": True,
                "newLinkFormat": "shortest",
                "useMarkdownLinks": False,
                "attachmentFolderPath": "./",
                "showUnsupportedFiles": False,
                "strictLineBreaks": False,
                "showLineNumber": False,
                "spellcheck": False,
                "livePreview": True,
                "defaultViewMode": "preview",
                "showInlineTitle": False,
                "propertiesInDocument": "visible",
                # Obsidian reads each entry as a case-insensitive regex when it is
                # wrapped in slashes, and as a literal path prefix otherwise.
                # Only generated production folders are hidden; every file the
                # client note links to stays indexed.
                "userIgnoreFilters": [
                    "/\\/(prompts|style|renders|contact-sheets|reviews|__pycache__)\\//"
                ],
            },
        ),
        _write_json(
            config / "appearance.json",
            {
                "theme": "obsidian",
                "baseFontSize": 17,
                "textFontFamily": "Rawy Cairo",
                "monospaceFontFamily": "SFMono-Regular",
                "cssTheme": "",
                "accentColor": "#82a4c9",
                "showViewHeader": True,
                "enabledCssSnippets": ["rawy"],
            },
        ),
        _write_json(config / "core-plugins.json", core_plugins),
        _write_json(config / "community-plugins.json", []),
        _write_json(config / "hotkeys.json", {}),
        _write_json(
            config / "bookmarks.json",
            {
                "items": [
                    {"type": "file", "path": "Dashboard.md", "title": "Rawy / راوي"},
                    {"type": "file", "path": "Clients.base", "title": "Clients / العملاء"},
                ]
            },
        ),
    ]


def write_archive_note(root: Path | None = None) -> Path:
    """The archive is one note listing what the active views are hiding."""
    rows = archived_clients()
    lines = [
        "---",
        "cssclasses: [rawy-dashboard]",
        "---",
        "",
        "# الأرشيف / Archive",
        "",
        "> [!rawy-actions]",
        "> [[Dashboard|🏠 راوي / Dashboard]]",
        "> [[Clients.base|👥 كل العملاء / All clients]]",
        "",
    ]
    if not rows:
        lines += [
            "مفيش عملاء مؤرشفين.",
            "",
            "*Nothing archived yet. To archive a client, open their note and tick"
            " the `archived` property — they leave every active view and appear"
            " here. Untick it to bring them back.*",
            "",
        ]
    else:
        lines += [
            f"**{len(rows)}** عميل مؤرشف / archived",
            "",
            "| العميل / Client | الكتاب / Book | التاريخ / Archived |",
            "|---|---|---|",
        ]
        for row in rows:
            link = f"[[Clients/{row['slug']}/Client|{row['client_name']}]]"
            lines.append(
                f"| {link} | {row['book_title'] or '—'} | {row['archived_at'] or '—'} |"
            )
        lines += [
            "",
            "شيل علامة `archived` من نوت العميل عشان يرجع تاني.",
            "",
            "*Untick `archived` on a client note to bring them back.*",
            "",
        ]
    return _write(rawy_root(root) / ARCHIVE_NOTE, "\n".join(lines))


def sync_rawy(client: Path | None = None) -> dict[str, Any]:
    rawy = rawy_root()
    rawy.mkdir(parents=True, exist_ok=True)
    clients = clients_root()
    clients.mkdir(parents=True, exist_ok=True)
    written = write_obsidian_config()
    projects: Iterable[Path]
    if client:
        projects = [Path(client).resolve()]
    else:
        projects = sorted(path for path in clients.iterdir() if path.is_dir())
    synced: list[dict[str, Any]] = []
    for project in projects:
        synced.append(sync_client(project))
    total = sum(
        1
        for project in sorted(path for path in clients.iterdir() if path.is_dir())
        if read_frontmatter(project / CLIENT_NOTE)[0].get("type") == "rawy-client"
    )
    archive_note = write_archive_note()
    archived = archived_clients()
    return {
        "vault": str(rawy),
        "clients": total,
        "archived": len(archived),
        "synced": synced,
        "archiveNote": str(archive_note),
        "written": [str(path) for path in written],
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _binary_manifest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() not in TEXT_SUFFIXES
    }


def _text_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
    ]


def migrate_client(source: Path, slug: str) -> dict[str, Any]:
    source = Path(source).expanduser().resolve()
    if not source.is_absolute() or not source.is_dir():
        raise RawyError(f"Migration source does not exist: {source}")
    if is_rawy_client(source):
        raise RawyError(f"Client is already inside Rawy: {source}")
    target = clients_root() / safe_slug(slug)
    if target.exists():
        raise RawyError(f"Migration target already exists: {target}")
    book = _read_book(source)
    if not book:
        raise RawyError(f"Migration source has no output/book.json: {source}")
    before_progress = book_progress(book)
    before_review = json.loads(json.dumps(book.get("storyReview") or {}))
    file_count = sum(1 for path in source.rglob("*") if path.is_file())
    binary_before = _binary_manifest(source)
    old_prefix = str(source)
    new_prefix = str(target.resolve())
    affected_before = [
        path.relative_to(source).as_posix()
        for path in _text_files(source)
        if old_prefix in path.read_text(encoding="utf-8", errors="strict")
    ]
    had_client_note = (source / CLIENT_NOTE).is_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.stat().st_dev != target.parent.stat().st_dev:
        raise RawyError("Verified migration requires source and Rawy on the same filesystem")

    moved = False
    try:
        source.rename(target)
        moved = True
        rewritten: list[str] = []
        for path in _text_files(target):
            text = path.read_text(encoding="utf-8", errors="strict")
            if old_prefix not in text:
                continue
            path.write_text(text.replace(old_prefix, new_prefix), encoding="utf-8")
            rewritten.append(path.relative_to(target).as_posix())

        remaining = [
            path.relative_to(target).as_posix()
            for path in _text_files(target)
            if old_prefix in path.read_text(encoding="utf-8", errors="strict")
        ]
        after_book = _read_book(target)
        if not after_book:
            raise RawyError("Migrated book manifest disappeared")
        after_progress = book_progress(after_book)
        after_review = after_book.get("storyReview") or {}
        after_count = sum(1 for path in target.rglob("*") if path.is_file())
        binary_after = _binary_manifest(target)
        if remaining:
            raise RawyError(f"Old path remains in: {remaining[:5]}")
        if sorted(rewritten) != sorted(affected_before):
            raise RawyError("Path rewrite count changed during migration")
        if before_progress != after_progress:
            raise RawyError("Book progress changed during migration")
        if before_review != after_review:
            raise RawyError("Story-review state changed during migration")
        if file_count != after_count:
            raise RawyError("File count changed during migration")
        if binary_before != binary_after:
            raise RawyError("Binary checksums changed during migration")
        sync_client(target)
        sync_rawy()
        return {
            "source": old_prefix,
            "target": new_prefix,
            "files": file_count,
            "rewritten": rewritten,
            "binaryFiles": len(binary_before),
            "progress": after_progress,
            "storyReview": after_review,
        }
    except Exception as exc:
        rollback_error: Exception | None = None
        if moved and target.exists():
            try:
                if not had_client_note:
                    generated_note = target / CLIENT_NOTE
                    if generated_note.is_file():
                        generated_note.unlink()
                for path in _text_files(target):
                    text = path.read_text(encoding="utf-8", errors="strict")
                    if new_prefix in text:
                        path.write_text(text.replace(new_prefix, old_prefix), encoding="utf-8")
                target.rename(source)
            except Exception as rollback_exc:  # noqa: BLE001
                rollback_error = rollback_exc
        if rollback_error:
            raise RawyError(
                f"Migration failed ({exc}); rollback also failed ({rollback_error})"
            ) from exc
        if isinstance(exc, RawyError):
            raise
        raise RawyError(f"Migration failed and was rolled back: {exc}") from exc
