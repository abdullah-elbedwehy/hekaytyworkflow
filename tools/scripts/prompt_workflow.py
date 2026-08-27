#!/usr/bin/env python3
"""Prompt approval, image-lane, inbox, and local-learning state for Rawy.

This module owns human-facing prompt review artifacts and their cryptographic
binding.  It deliberately has no dependency on ``story_pipeline`` so the main
pipeline can call it without an import cycle.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import doctrine


class PromptWorkflowError(RuntimeError):
    pass


ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def _arabic_indic(value: Any) -> str:
    return str(value).translate(ARABIC_INDIC)


PROMPTS_DIRNAME = "Prompts"
ASSETS_DIRNAME = "Assets"
HISTORY_DIRNAME = "History"
INBOX_DIRNAME = "Images Inbox"
PROCESSED_DIRNAME = "Processed"
LEARNING_RELATIVE = Path(".rawy/prompt-learning.json")
EDITABLE_FIELDS = ("override", "notes")
EDIT_RE = re.compile(
    r"<!-- rawy-prompt:(override|notes):start -->\s*(.*?)\s*"
    r"<!-- rawy-prompt:\1:end -->",
    re.DOTALL,
)
PACK_EDIT_RE = re.compile(
    r"<!-- rawy-prompt:pack-notes:start -->\s*(.*?)\s*"
    r"<!-- rawy-prompt:pack-notes:end -->",
    re.DOTALL,
)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
DESIGNED_ASSETS = {"cover", "page-01", "page-22", "back-cover"}
# Markers that mean "this page is a puzzle" wherever they appear. Distinctive
# enough that a plain substring match does not misfire on ordinary narration.
GAME_MARKERS = (
    "game page",
    "maze",
    "spot the difference",
    "spot-the-difference",
    "search-and-find",
    "search and find",
    "activity page",
    "صفحة لعبة",
    "متاهة",
    "اختلافات",
)
# Arabic imperatives addressed to the reader. These are ordinary words with a
# suffix ("ساعدني", "دوّرت"), so they only count standing alone.
GAME_IMPERATIVES = ("ساعد", "دوّر", "لاقي", "وصّل")
CARRIERS: tuple[dict[str, str], ...] = (
    {
        "kind": "wall-frame",
        "description": "برواز كبير مسطح على الحائط جوه المشهد",
        "rationale": "سطح واضح ومقروء ويفضل جزء طبيعي من المكان",
        "treatment": "printed-ink",
    },
    {
        "kind": "open-book",
        "description": "كتاب كبير مفتوح على صفحة فاضية مسطحة",
        "rationale": "الكتاب منطقي في عالم قصة طفل ويدي مساحة عريضة للسطور",
        "treatment": "printed-ink",
    },
    {
        "kind": "toy-box-face",
        "description": "واجهة صندوق لعب خشبي كبيرة وفاضية",
        "rationale": "مرتبطة بأوضة الطفل وتسمح بطلاء النص بشكل طبيعي",
        "treatment": "painted",
    },
    {
        "kind": "small-chalkboard",
        "description": "سبورة صغيرة مسطحة على حامل وسطحها نضيف",
        "rationale": "عنصر طفولي منطقي ويدعم مظهر الطباشير بعد التوليد",
        "treatment": "chalk",
    },
    {
        "kind": "fabric-card",
        "description": "كارت قماش كبير مسطح متعلق بالمشهد",
        "rationale": "يضيف سطح مقروء من غير ما يبان كأنه UI overlay",
        "treatment": "stitched",
    },
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_json(path: Path, payload: Any) -> None:
    atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def initialize_book_state(book: dict[str, Any]) -> None:
    book.setdefault(
        "promptApproval",
        {
            "status": "not_prepared",
            "packVersion": 0,
            "preparedAt": None,
            "approvedAt": None,
            "statement": None,
            "manifestSha256": None,
            "storySha256": None,
        },
    )
    book.setdefault(
        "imageLane",
        {
            "selected": None,
            "selectedAt": None,
            "statement": None,
            "overrides": {},
            "history": [],
        },
    )
    settings = book.setdefault("settings", {})
    # Story text lives inside the art by default; there is no caption-overlay
    # mode to opt out to.
    settings.setdefault("textIntegrationVersion", 1)
    settings.setdefault("textRendering", "in-image")


def review_root(project: Path) -> Path:
    return project / PROMPTS_DIRNAME


def asset_review_path(project: Path, asset_id: str) -> Path:
    return review_root(project) / ASSETS_DIRNAME / f"{asset_id}.md"


def prompt_review_index(project: Path) -> Path:
    return review_root(project) / "Index.md"


def inbox_root(project: Path) -> Path:
    return project / INBOX_DIRNAME


def ensure_client_surfaces(project: Path) -> dict[str, str]:
    for path in (
        review_root(project) / ASSETS_DIRNAME,
        review_root(project) / HISTORY_DIRNAME,
        inbox_root(project) / PROCESSED_DIRNAME,
    ):
        path.mkdir(parents=True, exist_ok=True)
    readme = inbox_root(project) / "README.md"
    if not readme.exists():
        atomic_text(
            readme,
            "# Images Inbox\n\n"
            "حط كل صورة باسم الـasset بالظبط: `page-05.png` أو "
            "`character-sheet.webp`. النظام بيفحص المقاس والاتجاه والنسخة، "
            "ومابيكتبش فوق صورة قديمة.\n\n"
            "Drop each image using its exact asset ID. Accepted files move to "
            "`Processed/`; rejected files stay here with the reason in "
            "`Inbox Status.md`.\n",
        )
    status = inbox_root(project) / "Inbox Status.md"
    if not status.exists():
        atomic_text(status, "# Inbox Status\n\nمفيش صور مستنية فحص.\n")
    return {
        "prompts": str(review_root(project)),
        "inbox": str(inbox_root(project)),
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromptWorkflowError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PromptWorkflowError(f"Expected an object in {path}")
    return payload


def integration_mode(asset_id: str, page: Mapping[str, Any] | None = None) -> str:
    """Classify one asset, and in particular decide whether it is a game page.

    Getting this wrong in the permissive direction is what handoff §8 calls the
    most-broken rule: an undetected game page never has to declare a
    `gameSpec`, so nobody writes the elements down and the model invents a maze
    with three exits.

    The page's own visible text is what makes it a puzzle — «ساعد سما توصل
    للفصل» is the instruction the child reads — so `text` is searched along with
    the structural fields. It used to be left out, which meant only a page that
    happened to carry the word "maze" in its `beat` was ever caught.

    Because the heuristic can misfire on ordinary narration, `pageType` is
    authoritative when the author sets it: `"game"` forces a game page and
    `"story"` opts out.
    """
    if asset_id == "character-sheet" or asset_id.startswith("location-sheet-"):
        return "none"
    if asset_id in DESIGNED_ASSETS:
        return "designed-page"
    declared = str((page or {}).get("pageType") or "").strip().casefold()
    if declared == "game":
        return "game-native"
    if declared == "story":
        return "scene-surface"
    searchable = " ".join(
        str((page or {}).get(key) or "")
        for key in ("role", "pageType", "beat", "setting", "text")
    ).casefold()
    if any(marker in searchable for marker in GAME_MARKERS):
        return "game-native"
    for word in GAME_IMPERATIVES:
        if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", searchable):
            return "game-native"
    return "scene-surface"


def _planned_region(text: str, mode: str) -> dict[str, float]:
    # Long copy is given more area before image generation.  Preflight still
    # rejects text that cannot fit at the configured print minimum.
    length = len(" ".join(text.split()))
    if mode == "designed-page":
        return {"x": 0.53, "y": 0.10, "width": 0.39, "height": 0.78}
    if mode == "game-native":
        return {"x": 0.58, "y": 0.08, "width": 0.34, "height": 0.42}
    height = 0.34 if length <= 90 else 0.42 if length <= 150 else 0.50
    return {"x": 0.56, "y": 0.10, "width": 0.35, "height": height}


def text_integration_plan(
    asset_id: str,
    page: Mapping[str, Any] | None,
    *,
    story_text: str,
    narrative_index: int,
) -> dict[str, Any]:
    mode = integration_mode(asset_id, page)
    if mode == "none":
        return {"version": 1, "mode": "none", "status": "not-applicable"}
    if mode == "game-native":
        carrier = {
            "kind": "game-instruction-board",
            "description": "لوحة تعليمات كبيرة مسطحة مدمجة في تصميم اللعبة",
            "rationale": "النص يبقى جزء من واجهة اللعبة من غير ما يغطي المسار أو العناصر",
            "treatment": "printed-ink",
        }
    elif mode == "designed-page":
        carrier = {
            "kind": "designed-copy-area",
            "description": "مساحة تصميم فاضية واضحة مدمجة في الصفحة",
            "rationale": "الصفحة تصميمية وليست مشهد سردي، فالمساحة تتبنى داخل التكوين",
            "treatment": "printed-ink",
        }
    else:
        carrier = CARRIERS[narrative_index % len(CARRIERS)]
    return {
        "version": 1,
        "mode": mode,
        "carrierKind": carrier["kind"],
        "carrierDescription": carrier["description"],
        "rationaleAr": carrier["rationale"],
        "treatment": carrier["treatment"],
        "plannedRegion": _planned_region(story_text, mode),
        "maxLines": 5,
        "minimumFontPt": 12,
        "textSource": "asset.storyText",
        "resolvedQuad": None,
        "status": "planned",
    }


def upgrade_text_integration(
    project: Path,
    rawy_root: Path,
    book: dict[str, Any],
    *,
    version: int,
) -> dict[str, Any]:
    if version != 1:
        raise PromptWorkflowError("Only text-integration version 1 is supported")
    initialize_book_state(book)
    story_path = project / str(book.get("storyPath") or "")
    if not story_path.is_file():
        raise PromptWorkflowError("An approved locked story is required")
    story_review = book.get("storyReview") or {}
    if story_review.get("status") != "approved":
        raise PromptWorkflowError("Story review must be approved before upgrading prompts")
    story = _read_json(story_path)
    pages = {
        str(page.get("id")): page
        for page in story.get("pages") or []
        if isinstance(page, Mapping) and page.get("id")
    }
    learned_rules = active_learning_rules(rawy_root)
    learned_ids = [item["id"] for item in learned_rules]
    changed: list[dict[str, Any]] = []
    narrative_index = 0
    for asset in book.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        asset_id = str(asset.get("id") or "")
        page = pages.get(asset_id)
        mode = integration_mode(asset_id, page)
        if mode == "scene-surface":
            narrative_index += 1
        # Migration v1 intentionally preserves approved sheets and the existing
        # dedication asset. They carry no narrative caption dependency and must
        # not be silently version-bumped during a text-integration rework.
        if mode == "none" or asset_id == "page-01":
            continue
        current_path = project / str(asset.get("promptPath") or "")
        if not current_path.is_file():
            raise PromptWorkflowError(f"Missing prompt file: {current_path}")
        payload = _read_json(current_path)
        current_integration = payload.get("textIntegration") or {}
        if (
            payload.get("schemaVersion") == 2
            and current_integration.get("version") == version
        ):
            continue
        next_version = int(asset.get("promptVersion") or 1) + 1
        next_relative = f"input/prompts/{asset_id}.v{next_version:02d}.json"
        next_path = project / next_relative
        if next_path.exists():
            raise PromptWorkflowError(f"Refusing to overwrite prompt version: {next_path}")
        integration = text_integration_plan(
            asset_id,
            page,
            story_text=str(asset.get("storyText") or ""),
            narrative_index=max(0, narrative_index - 1),
        )
        payload["schemaVersion"] = 2
        payload["version"] = next_version
        payload["textIntegration"] = integration
        payload["learnedRuleIds"] = learned_ids
        payload["learnedRulesApplied"] = learned_rules
        composition = payload.get("composition")
        if isinstance(composition, dict):
            composition.pop("captionSafeZone", None)
        primary = str(payload.get("primaryRequest") or "")
        primary = re.sub(
            r",?\s*with (?:both figures|all figures|the figure).*?caption band",
            "",
            primary,
            flags=re.IGNORECASE,
        )
        payload["primaryRequest"] = primary
        atomic_json(next_path, payload)
        previous_image = asset.get("imagePath")
        if previous_image and mode in {"scene-surface", "game-native"}:
            asset["supersededImagePath"] = previous_image
            asset["imagePath"] = None
        if mode in {"scene-surface", "game-native"}:
            for historical in asset.get("versions") or []:
                if isinstance(historical, dict) and historical.get("imagePath"):
                    historical.setdefault("supersededByTextIntegrationVersion", version)
        asset["promptVersion"] = next_version
        asset["promptPath"] = next_relative
        asset["status"] = "prompted"
        changed.append(
            {
                "assetId": asset_id,
                "from": str(current_path.relative_to(project)),
                "to": next_relative,
                "mode": mode,
            }
        )
    book["settings"]["textIntegrationVersion"] = version
    invalidate_after_prompt_change(book)
    book["status"] = "writing_prompts"
    book["nextAction"] = "Compile and validate schema-v2 prompts, then prepare prompt review"
    return {"version": version, "changed": changed, "learnedRuleIds": learned_ids}


def _book_placement(book: Mapping[str, Any]) -> dict[str, str]:
    """Arabic "which slot is this" label for every asset that lands in the PDF.

    A prompt note is read on its own — in Obsidian, or by somebody generating the
    art outside this repo. Without the slot, a folder of finished images has no
    order in it and the operator has to come back and ask.
    """
    count = int((book.get("settings") or {}).get("pdfPageCount") or 0)
    try:
        roles = doctrine.structure_slot_roles(count)
    except Exception:  # a book whose page count is not set yet
        return {}
    ordered = ["cover"]
    ordered += sorted(
        (asset_id for asset_id in roles if asset_id.startswith("page-")),
        key=lambda value: int(value.split("-")[1]),
    )
    ordered.append("back-cover")
    total = len(ordered)
    labels: dict[str, str] = {}
    for index, asset_id in enumerate(ordered, start=1):
        role = doctrine.role_label_ar(roles.get(asset_id, "story"))
        labels[asset_id] = (
            f"{role} — الصفحة {_arabic_indic(index)} من {_arabic_indic(total)} في الـPDF"
        )
    return labels


def _prompt_rows(project: Path, book: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    placement = _book_placement(book)
    for asset in book.get("assets") or []:
        if not isinstance(asset, Mapping):
            continue
        asset_id = str(asset.get("id") or "").strip()
        relative = str(asset.get("promptPath") or "").strip()
        if not asset_id or not relative:
            continue
        path = project / relative
        if not path.is_file():
            raise PromptWorkflowError(f"Missing prompt file: {path}")
        payload = _read_json(path)
        rows.append(
            {
                "assetId": asset_id,
                "promptPath": relative,
                "promptVersion": int(asset.get("promptVersion") or 1),
                "promptSha256": sha256_file(path),
                "payload": payload,
                "storyText": str(asset.get("storyText") or ""),
                "placement": placement.get(asset_id, "مرجع — مش صفحة في الـPDF"),
            }
        )
    if not rows:
        raise PromptWorkflowError("No prompt files are registered in book.json")
    return rows


def _extract_editable(text: str) -> dict[str, str]:
    values = {key: "" for key in EDITABLE_FIELDS}
    for match in EDIT_RE.finditer(text):
        values[match.group(1)] = match.group(2).strip()
    return values


def _extract_pack_notes(text: str) -> str:
    match = PACK_EDIT_RE.search(text)
    return match.group(1).strip() if match else ""


def _asset_note(
    row: Mapping[str, Any], *, editable: Mapping[str, str] | None = None
) -> str:
    """One asset's note: the review surface *and* the portable job.

    Everything somebody needs to render this asset without us is here — the slot
    it fills in the book, the files to attach in order, the Arabic the model has
    to draw and what it draws it on, and the prompt itself per image tool. That
    is deliberate: the same note is what Omar reviews in Obsidian and what gets
    handed to whoever is generating the art that week.
    """
    payload = row["payload"]
    inputs = payload.get("inputImages") or []
    attachments = [
        (str(item.get("role") or "reference"), str(item.get("path")))
        for item in inputs
        if isinstance(item, Mapping) and item.get("path")
    ]
    override = str((editable or {}).get("override") or "")
    notes = str((editable or {}).get("notes") or "")
    compiled_variants = payload.get("compiledPrompts")
    if not isinstance(compiled_variants, Mapping) or not compiled_variants:
        compiled_variants = {"default": str(payload.get("compiledPrompt") or "")}
    compiled_blocks = "\n\n".join(
        f"### {target}\n\n```text\n{text}\n```"
        for target, text in compiled_variants.items()
    )
    refs = (
        "\n".join(
            f"{index}. `[{role}] {path}`"
            for index, (role, path) in enumerate(attachments, start=1)
        )
        or "1. ⚠️ مفيش مرفقات على البرومبت ده"
    )
    learned = payload.get("learnedRuleIds") or []
    learned_text = ", ".join(f"`{item}`" for item in learned) or "—"

    in_image = str(payload.get("inImageText") or "").strip()
    surface = " ".join(str(payload.get("textSurface") or "").split())
    if in_image:
        text_block = (
            f"- **السطح اللي الكلام متكتوب عليه:** {surface or '⚠️ مش محدد'}\n"
            "- **النص، حرف بحرف:**\n\n"
            f"```\n{in_image}\n```\n\n"
            "- ممنوع شريط سفلي، ولا بانل، ولا طبقة نص فوق الرسمة. "
            "الكلام جزء من الرسمة نفسها.\n"
        )
    elif row["storyText"]:
        text_block = (
            "- ⚠️ الصفحة ليها نص معتمد بس البرومبت مش شايله. "
            "شغّل `compile-prompts` قبل أي توليد.\n"
        )
    else:
        text_block = "- الصورة دي بترجع من غير أي كتابة — كل سطح في الكادر فاضي.\n"

    return (
        "---\n"
        "type: rawy-prompt-review\n"
        f"asset_id: {json.dumps(row['assetId'], ensure_ascii=False)}\n"
        f"prompt_version: {row['promptVersion']}\n"
        f"prompt_sha256: {json.dumps(row['promptSha256'])}\n"
        "---\n\n"
        f"# {row['assetId']} · v{row['promptVersion']:02d}\n\n"
        "<!-- rawy-prompt:generated:start -->\n"
        "## مكان الصفحة في الكتاب\n\n"
        f"- **الدور:** {row.get('placement') or '—'}\n"
        f"- **ملف البرومبت:** `{row['promptPath']}`\n"
        f"- **قواعد متعلّمة مستخدمة:** {learned_text}\n\n"
        "## النص اللي المولّد لازم يكتبه جوه الرسمة\n\n"
        f"{text_block}\n"
        "## المرفقات المطلوبة (ارفعها بالترتيب ده)\n\n"
        f"{refs}\n\n"
        "## Prompts قابلة للنسخ\n\n"
        f"{compiled_blocks}\n"
        "<!-- rawy-prompt:generated:end -->\n\n"
        "## تعديل مباشر مقترح\n\n"
        "اكتب هنا نسخة بديلة لو عايز تغيّر الـprompt كله. الـagent هيحوّلها "
        "لنسخة JSON جديدة ويعيد التحقق.\n\n"
        "<!-- rawy-prompt:override:start -->\n"
        f"{override}\n"
        "<!-- rawy-prompt:override:end -->\n\n"
        "## ملاحظاتي\n\n"
        "<!-- rawy-prompt:notes:start -->\n"
        f"{notes}\n"
        "<!-- rawy-prompt:notes:end -->\n"
    )


def _archive_note(project: Path, asset_id: str, version: int, text: str) -> Path:
    destination = (
        review_root(project)
        / HISTORY_DIRNAME
        / f"{asset_id}.v{version:02d}.{now_iso().replace(':', '-')}.md"
    )
    atomic_text(destination, text)
    return destination


def _manifest(
    project: Path,
    book: Mapping[str, Any],
    *,
    require_review_files: bool,
) -> dict[str, Any]:
    rows = _prompt_rows(project, book)
    prompt_entries: list[dict[str, Any]] = []
    review_entries: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    for row in rows:
        payload = row["payload"]
        prompt_entries.append(
            {
                key: row[key]
                for key in ("assetId", "promptPath", "promptVersion", "promptSha256")
            }
        )
        integration = payload.get("textIntegration")
        if isinstance(integration, Mapping):
            plans.append(
                {
                    "assetId": row["assetId"],
                    "plan": integration,
                }
            )
        note = asset_review_path(project, row["assetId"])
        if require_review_files and not note.is_file():
            raise PromptWorkflowError(f"Missing prompt review file: {note}")
        if note.is_file():
            review_entries.append(
                {
                    "assetId": row["assetId"],
                    "path": str(note.relative_to(project)),
                    "sha256": sha256_file(note),
                }
            )
    index = prompt_review_index(project)
    if require_review_files and not index.is_file():
        raise PromptWorkflowError(f"Missing prompt review index: {index}")
    index_entry = (
        {
            "path": str(index.relative_to(project)),
            "sha256": sha256_file(index),
        }
        if index.is_file()
        else None
    )
    brief_path = project / str(book.get("briefPath") or "input/brief.json")
    brief = _read_json(brief_path) if brief_path.is_file() else {}
    story_sha = str(
        (book.get("storyReview") or {}).get("approvedStorySha256")
        or (book.get("storyReview") or {}).get("storySha256")
        or ""
    )
    payload = {
        "schemaVersion": 1,
        "storySha256": story_sha,
        "theme": {
            "themeId": brief.get("themeId"),
            "visualStyle": brief.get("visualStyle"),
        },
        "prompts": prompt_entries,
        "reviewFiles": review_entries,
        "index": index_entry,
        "textIntegrationPlans": plans,
    }
    payload["manifestSha256"] = sha256_bytes(_canonical_bytes(payload))
    return payload


def _pending_feedback(project: Path, book: Mapping[str, Any]) -> list[dict[str, str]]:
    pending: list[dict[str, str]] = []
    index = prompt_review_index(project)
    if index.is_file() and _extract_pack_notes(index.read_text(encoding="utf-8")):
        pending.append({"assetId": "pack", "field": "notes"})
    for row in _prompt_rows(project, book):
        note = asset_review_path(project, row["assetId"])
        if not note.is_file():
            continue
        editable = _extract_editable(note.read_text(encoding="utf-8"))
        for field, value in editable.items():
            if value:
                pending.append({"assetId": row["assetId"], "field": field})
    return pending


def prepare_prompt_review(project: Path, book: dict[str, Any]) -> dict[str, Any]:
    initialize_book_state(book)
    ensure_client_surfaces(project)
    rows = _prompt_rows(project, book)
    approval = book["promptApproval"]
    previous_manifest = approval.get("manifestSha256")
    written: list[str] = []
    archived: list[str] = []
    for row in rows:
        path = asset_review_path(project, row["assetId"])
        editable: dict[str, str] = {}
        if path.is_file():
            old = path.read_text(encoding="utf-8")
            old_match = re.search(r"^prompt_version:\s*(\d+)\s*$", old, re.MULTILINE)
            old_version = int(old_match.group(1)) if old_match else 0
            if old_version != row["promptVersion"]:
                archived_path = _archive_note(project, row["assetId"], old_version, old)
                archived.append(str(archived_path))
            else:
                editable = _extract_editable(old)
        atomic_text(path, _asset_note(row, editable=editable))
        written.append(str(path))

    index = prompt_review_index(project)
    previous_prompts = {
        (item.get("assetId"), item.get("promptSha256"))
        for item in ((approval.get("manifest") or {}).get("prompts") or [])
        if isinstance(item, Mapping)
    }
    current_prompts = {(row["assetId"], row["promptSha256"]) for row in rows}
    carry_pack_notes = bool(previous_prompts) and previous_prompts == current_prompts
    pack_notes = (
        _extract_pack_notes(index.read_text(encoding="utf-8"))
        if index.is_file() and carry_pack_notes
        else ""
    )
    table = ["| Asset | Version | Review |", "|---|---:|---|"]
    for row in rows:
        table.append(
            f"| `{row['assetId']}` | v{row['promptVersion']:02d} | "
            f"[[Assets/{row['assetId']}|فتح]] |"
        )
    atomic_text(
        index,
        "# مراجعة حزمة الـPrompts\n\n"
        "> راجع الحزمة كلها. اكتب ملاحظاتك جوه كل asset أو هنا. "
        "الموافقة واحدة ومرتبطة بكل الملفات الحالية.\n\n"
        + "\n".join(table)
        + "\n\n## ملاحظات عامة\n\n"
        "<!-- rawy-prompt:pack-notes:start -->\n"
        f"{pack_notes}\n"
        "<!-- rawy-prompt:pack-notes:end -->\n",
    )
    written.append(str(index))
    manifest = _manifest(project, book, require_review_files=True)
    pack_version = int(approval.get("packVersion") or 0)
    if manifest["manifestSha256"] != previous_manifest:
        pack_version += 1
    approval.update(
        {
            "status": "awaiting_user",
            "packVersion": max(1, pack_version),
            "preparedAt": now_iso(),
            "approvedAt": None,
            "statement": None,
            "manifestSha256": manifest["manifestSha256"],
            "storySha256": manifest["storySha256"],
            "manifest": manifest,
        }
    )
    book["status"] = "awaiting_prompt_review"
    book["nextAction"] = "راجع Prompts/Index.md، خلّص الملاحظات، وبعدها وافق على الحزمة كلها"
    return {
        "status": "awaiting_user",
        "packVersion": approval["packVersion"],
        "index": str(index),
        "written": written,
        "archived": archived,
        "manifestSha256": manifest["manifestSha256"],
    }


def prompt_review_status(project: Path, book: Mapping[str, Any]) -> dict[str, Any]:
    approval = book.get("promptApproval") or {}
    if not approval or approval.get("status") == "not_prepared":
        return {
            "status": "not_prepared",
            "nextAction": "Run prepare-prompt-review after prompt preflight passes",
        }
    try:
        current = _manifest(project, book, require_review_files=True)
    except PromptWorkflowError as exc:
        return {"status": "stale", "error": str(exc), "nextAction": "Rebuild prompt review"}
    pending = _pending_feedback(project, book)
    same = current["manifestSha256"] == approval.get("manifestSha256")
    status = str(approval.get("status") or "awaiting_user")
    if pending:
        status = "feedback_pending"
    elif not same:
        status = "changes_detected"
    elif status == "approved":
        status = "approved"
    else:
        status = "awaiting_user"
    next_actions = {
        "changes_detected": "Run prepare-prompt-review for the new prompt versions",
        "feedback_pending": "Apply every note to new prompt JSON versions, then rebuild the review",
        "awaiting_user": "Review Prompts/Index.md, then approve the whole pack",
        "approved": "Select agent or manual image lane",
    }
    return {
        "status": status,
        "packVersion": approval.get("packVersion"),
        "manifestSha256": current["manifestSha256"],
        "preparedManifestSha256": approval.get("manifestSha256"),
        "pendingFeedback": pending,
        "index": str(prompt_review_index(project)),
        "nextAction": next_actions[status],
    }


def approve_prompts(
    project: Path, book: dict[str, Any], statement: str
) -> dict[str, Any]:
    statement = statement.strip()
    if len(statement) < 3:
        raise PromptWorkflowError("Prompt approval statement is too short")
    status = prompt_review_status(project, book)
    if status["status"] != "awaiting_user":
        raise PromptWorkflowError(
            f"Prompt pack cannot be approved while status={status['status']}"
        )
    approval = book["promptApproval"]
    approval.update(
        {
            "status": "approved",
            "approvedAt": now_iso(),
            "statement": statement,
            "manifestSha256": status["manifestSha256"],
        }
    )
    book["status"] = "awaiting_image_lane"
    book["nextAction"] = "اختار مسار الصور: agent أو manual"
    return {
        "status": "approved",
        "packVersion": approval["packVersion"],
        "manifestSha256": approval["manifestSha256"],
        "nextAction": book["nextAction"],
    }


def reopen_prompt_review(book: dict[str, Any], statement: str) -> dict[str, Any]:
    statement = statement.strip()
    if len(statement) < 3:
        raise PromptWorkflowError("Reopen statement is too short")
    initialize_book_state(book)
    approval = book["promptApproval"]
    approval.update(
        {
            "status": "awaiting_user",
            "approvedAt": None,
            "statement": None,
            "reopenedAt": now_iso(),
            "reopenStatement": statement,
        }
    )
    book["imageLane"]["selected"] = None
    # A changed prompt pack makes every dependent page/cover image stale. Keep
    # the old versioned files on disk for audit history, but clear their active
    # pointers so the next approved pack must regenerate them.
    for asset in book.get("assets") or []:
        asset_id = str(asset.get("id") or "")
        if asset_id == "character-sheet" or asset_id.startswith("location-sheet-"):
            continue
        if asset.get("includeInPdf"):
            asset["status"] = "prompted"
            # Attempts belong to the approved prompt pack. Reopening after a
            # pack change starts a fresh generation budget; old versioned files
            # remain on disk for audit history but cannot block the new pack.
            asset["attempt"] = 0
            asset["imagePath"] = None
            asset["rawImagePath"] = None
            asset["textIntegrationRuntime"] = None
    book["status"] = "awaiting_prompt_review"
    book["nextAction"] = "راجع حزمة الـprompts الحالية من Rawy"
    return {"status": "awaiting_user", "nextAction": book["nextAction"]}


def require_prompt_approved(project: Path, book: Mapping[str, Any]) -> dict[str, Any]:
    status = prompt_review_status(project, book)
    if status["status"] != "approved":
        raise PromptWorkflowError(
            f"Current prompt pack is not approved (status={status['status']})"
        )
    return status


def selected_lane(book: Mapping[str, Any], asset_id: str | None = None) -> str | None:
    state = book.get("imageLane") or {}
    overrides = state.get("overrides") or {}
    if asset_id and isinstance(overrides, Mapping) and asset_id in overrides:
        entry = overrides[asset_id]
        if isinstance(entry, Mapping):
            return str(entry.get("lane") or "") or None
    selected = str(state.get("selected") or "")
    return selected or None


def set_image_lane(
    project: Path,
    book: dict[str, Any],
    *,
    lane: str,
    statement: str,
    asset_id: str | None = None,
) -> dict[str, Any]:
    require_prompt_approved(project, book)
    lane = lane.strip().lower()
    if lane not in {"agent", "manual"}:
        raise PromptWorkflowError("Image lane must be agent or manual")
    statement = statement.strip()
    if len(statement) < 3:
        raise PromptWorkflowError("Image-lane statement is too short")
    initialize_book_state(book)
    state = book["imageLane"]
    previous = selected_lane(book, asset_id)
    event = {
        "lane": lane,
        "previous": previous,
        "assetId": asset_id,
        "statement": statement,
        "selectedAt": now_iso(),
    }
    state["history"].append(event)
    if asset_id:
        state.setdefault("overrides", {})[asset_id] = event
    else:
        state.update(
            {
                "selected": lane,
                "selectedAt": event["selectedAt"],
                "statement": statement,
            }
        )
    book["status"] = "ready_for_images" if lane == "agent" else "awaiting_manual_images"
    book["nextAction"] = (
        "Generate character and location sheets"
        if lane == "agent"
        else "Export manual prompts and put returned files in Images Inbox"
    )
    return {"lane": lane, "assetId": asset_id, "nextAction": book["nextAction"]}


def require_lane(
    project: Path, book: Mapping[str, Any], *, expected: str, asset_id: str | None = None
) -> str:
    require_prompt_approved(project, book)
    actual = selected_lane(book, asset_id)
    if actual != expected:
        raise PromptWorkflowError(
            f"{asset_id or 'Book'} image lane is {actual or 'not selected'}, expected {expected}"
        )
    return actual


def inbox_candidates(project: Path) -> list[Path]:
    ensure_client_surfaces(project)
    return sorted(
        path
        for path in inbox_root(project).iterdir()
        if path.is_file() and not path.name.startswith(".") and path.suffix.lower() in IMAGE_SUFFIXES
    )


def inbox_status(project: Path, book: Mapping[str, Any]) -> dict[str, Any]:
    known = {
        str(asset.get("id"))
        for asset in book.get("assets") or []
        if isinstance(asset, Mapping) and asset.get("id")
    }
    rows: list[dict[str, Any]] = []
    for path in inbox_candidates(project):
        asset_id = path.stem
        rows.append(
            {
                "file": path.name,
                "assetId": asset_id,
                "known": asset_id in known,
                "lane": selected_lane(book, asset_id),
            }
        )
    return {"pending": len(rows), "files": rows, "inbox": str(inbox_root(project))}


def write_inbox_status(project: Path, rows: Iterable[Mapping[str, Any]]) -> Path:
    lines = ["# Inbox Status", "", "| File | Asset | Status |", "|---|---|---|"]
    count = 0
    for row in rows:
        count += 1
        lines.append(
            f"| `{row.get('file', '—')}` | `{row.get('assetId', '—')}` | "
            f"{row.get('status', 'pending')} |"
        )
    if count == 0:
        lines.extend(["", "مفيش صور مستنية فحص."])
    path = inbox_root(project) / "Inbox Status.md"
    atomic_text(path, "\n".join(lines) + "\n")
    return path


def move_processed(source: Path, project: Path, asset_id: str, version: int) -> Path:
    destination = (
        inbox_root(project)
        / PROCESSED_DIRNAME
        / f"{asset_id}.v{version:02d}{source.suffix.lower()}"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise PromptWorkflowError(f"Processed inbox file already exists: {destination}")
    source.replace(destination)
    return destination


def learning_path(rawy_root: Path) -> Path:
    return rawy_root / LEARNING_RELATIVE


def load_learnings(rawy_root: Path) -> dict[str, Any]:
    path = learning_path(rawy_root)
    if not path.is_file():
        return {"schemaVersion": 1, "rules": [], "events": []}
    payload = _read_json(path)
    payload.setdefault("schemaVersion", 1)
    payload.setdefault("rules", [])
    payload.setdefault("events", [])
    return payload


def active_learning_ids(rawy_root: Path) -> list[str]:
    payload = load_learnings(rawy_root)
    return [
        str(rule.get("id"))
        for rule in payload["rules"]
        if isinstance(rule, Mapping) and rule.get("status") == "active" and rule.get("id")
    ]


def active_learning_rules(rawy_root: Path) -> list[dict[str, str]]:
    payload = load_learnings(rawy_root)
    return [
        {"id": str(rule["id"]), "rule": str(rule["rule"])}
        for rule in payload["rules"]
        if isinstance(rule, Mapping)
        and rule.get("status") == "active"
        and rule.get("id")
        and rule.get("rule")
    ]


def _safe_rule_text(
    statement: str, *, project: Path, book: Mapping[str, Any]
) -> str:
    text = " ".join(statement.split())
    text = text.replace(str(project), "[client-path]")
    for persona in book.get("personas") or []:
        if isinstance(persona, Mapping):
            name = str(persona.get("displayName") or "").strip()
            if name:
                text = text.replace(name, "[persona]")
    text = re.sub(r"(?:/Users|/private|/Volumes)/\S+", "[local-path]", text)
    text = re.sub(r"\b\+?\d[\d\s-]{7,}\d\b", "[private-number]", text)
    if len(text) < 8:
        raise PromptWorkflowError("Learning statement must be a generalized 8+ character rule")
    return text[:240]


def record_learning(
    rawy_root: Path,
    project: Path,
    book: Mapping[str, Any],
    *,
    asset_id: str,
    statement: str,
    category: str,
    accepted: bool,
    before_sha256: str | None,
    after_sha256: str | None,
) -> dict[str, Any]:
    safe = _safe_rule_text(statement, project=project, book=book)
    payload = load_learnings(rawy_root)
    signature = sha256_bytes(_canonical_bytes({"category": category, "rule": safe.casefold()}))
    rule = next(
        (
            item
            for item in payload["rules"]
            if isinstance(item, dict) and item.get("signature") == signature
        ),
        None,
    )
    explicit = "اتعلم" in statement or "learn this" in statement.casefold()
    if rule is None:
        rule = {
            "id": f"learn-{signature[:10]}",
            "signature": signature,
            "category": category,
            "rule": safe,
            "status": "candidate",
            "acceptedCount": 0,
            "createdAt": now_iso(),
        }
        payload["rules"].append(rule)
    if accepted:
        rule["acceptedCount"] = int(rule.get("acceptedCount") or 0) + 1
    if not accepted:
        rule["status"] = "inactive"
        rule["inactivatedAt"] = now_iso()
    elif explicit or int(rule.get("acceptedCount") or 0) >= 2:
        rule["status"] = "active"
    if isinstance(book, dict):
        current = book.setdefault("promptLearningCandidates", [])
        if rule["id"] not in current and rule["status"] in {"candidate", "active"}:
            current.append(rule["id"])
    event = {
        "ruleId": rule["id"],
        "category": category,
        "carrierKind": None,
        "accepted": bool(accepted),
        "lane": selected_lane(book, asset_id),
        "beforeSha256": before_sha256,
        "afterSha256": after_sha256,
        "createdAt": now_iso(),
    }
    try:
        prompt_asset = next(
            item
            for item in book.get("assets") or []
            if isinstance(item, Mapping) and item.get("id") == asset_id
        )
        prompt_path = project / str(prompt_asset.get("promptPath") or "")
        integration = _read_json(prompt_path).get("textIntegration") or {}
        event["carrierKind"] = integration.get("carrierKind")
    except (StopIteration, PromptWorkflowError):
        pass
    payload["events"].append(event)
    atomic_json(learning_path(rawy_root), payload)
    return {"rule": rule, "event": event, "path": str(learning_path(rawy_root))}


def invalidate_after_prompt_change(book: dict[str, Any]) -> None:
    initialize_book_state(book)
    approval = book["promptApproval"]
    approval.update(
        {
            "status": "not_prepared",
            "preparedAt": None,
            "approvedAt": None,
            "statement": None,
            "manifestSha256": None,
            "storySha256": None,
        }
    )
    lane = book["imageLane"]
    lane["selected"] = None
    lane["selectedAt"] = None
    lane["statement"] = None
    lane["overrides"] = {}
