"""Render one self-contained image instruction for the manual ChatGPT lane.

Handoff §8: the phone tool has no state. Every message must carry the whole job
on its own — the reference-sheet clause, the exact scene, the orientation, and
the one-page-per-reply stop. This module turns a compiled prompt JSON into
exactly that block, ready to paste, with nothing left implicit.

The automated Codex lane is unchanged; this is the export for the way Omar
actually generates art today.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import doctrine


class ManualDispatchError(RuntimeError):
    pass


_SEPARATOR = "─" * 46


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _lines(values: Iterable[Any], bullet: str = "- ") -> list[str]:
    out: list[str] = []
    for value in values:
        text = _clean(value)
        if text:
            out.append(f"{bullet}{text}")
    return out


def reference_attachments(
    prompt: Mapping[str, Any], *, character_sheet_path: str | None = None
) -> list[dict[str, str]]:
    """Attachment checklist in handoff order: personas → sheet → location → style."""
    raw = prompt.get("inputImages")
    attachments: list[dict[str, str]] = []
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, Mapping):
                continue
            path = _clean(entry.get("path"))
            role = _clean(entry.get("role")) or "reference"
            if not path or path.upper().startswith("CHANGE"):
                continue
            attachments.append({"role": role, "path": path})
    if character_sheet_path and not any(
        item["role"] == "character-sheet" for item in attachments
    ):
        attachments.append({"role": "character-sheet", "path": _clean(character_sheet_path)})
    return attachments


def _scene_block(prompt: Mapping[str, Any]) -> list[str]:
    scene = prompt.get("scene")
    if not isinstance(scene, Mapping):
        return []
    labels = (
        ("place", "المكان"),
        ("timeOfDay", "الوقت والضوء"),
        ("atmosphere", "الجو"),
        ("lighting", "الإضاءة"),
        ("foreground", "المقدمة"),
        ("midground", "الوسط"),
        ("background", "الخلفية"),
        ("backdropDetails", "تفاصيل الخلفية"),
    )
    rows = [f"- {label}: {_clean(scene.get(key))}" for key, label in labels if _clean(scene.get(key))]
    props = scene.get("propsInFrame")
    if isinstance(props, list):
        prop_lines = _lines(props, bullet="  • ")
        if prop_lines:
            rows.append("- العناصر الظاهرة:")
            rows.extend(prop_lines)
    return rows


def _people_block(prompt: Mapping[str, Any]) -> list[str]:
    rows: list[str] = []
    participants = prompt.get("participants")
    action = prompt.get("actionAndEmotion") if isinstance(prompt.get("actionAndEmotion"), Mapping) else {}
    outfits = prompt.get("fixedOutfits") if isinstance(prompt.get("fixedOutfits"), Mapping) else {}
    if isinstance(participants, list):
        for entry in participants:
            if not isinstance(entry, Mapping) or entry.get("onPage") is False:
                continue
            persona_id = _clean(entry.get("id"))
            name = _clean(entry.get("displayName")) or persona_id
            if not name or name.upper().startswith("CHANGE"):
                continue
            rows.append(f"- {name} ({persona_id}):")
            outfit = _clean(outfits.get(persona_id)) if isinstance(outfits, Mapping) else ""
            if outfit and not outfit.upper().startswith("CHANGE"):
                rows.append(f"  • اللبس الثابت: {outfit}")
            beat = action.get(persona_id) if isinstance(action, Mapping) else None
            if isinstance(beat, Mapping):
                if _clean(beat.get("action")):
                    rows.append(f"  • الحركة: {_clean(beat.get('action'))}")
                if _clean(beat.get("emotion")):
                    rows.append(f"  • الإحساس: {_clean(beat.get('emotion'))}")
    guests = prompt.get("guests")
    if isinstance(guests, list):
        for guest in guests:
            if not isinstance(guest, Mapping):
                continue
            notes = _clean(guest.get("appearanceNotes"))
            if not notes or notes.upper().startswith("CHANGE"):
                continue
            name = _clean(guest.get("displayName")) or "ضيف"
            rows.append(f"- {name} (ضيف — بالوصف بس، من غير أي اسم علامة تجارية):")
            rows.append(f"  • {notes}")
    return rows


def render_manual_instruction(
    prompt: Mapping[str, Any],
    *,
    asset_id: str,
    page_text: str | None = None,
    page_role: str = "story",
    character_sheet_path: str | None = None,
    next_asset_id: str | None = None,
) -> str:
    """One paste-ready Arabic message for a single page (handoff §8 I1/I3/I5/I7)."""
    if not isinstance(prompt, Mapping):
        raise ManualDispatchError("prompt payload must be an object")
    asset_id = _clean(asset_id)
    if not asset_id:
        raise ManualDispatchError("asset_id is required")

    orientation = doctrine.required_orientation()
    ratio = doctrine.required_aspect_ratio()
    role_label = doctrine.role_label_ar(page_role)

    header = [
        f"# تعليمة توليد صورة واحدة — {asset_id} ({role_label})",
        "",
        "> رسالة واحدة كاملة بذاتها. متفترضش إن الأداة فاكرة أي حاجة من رسالة قبل كده.",
        "",
    ]

    attachments = reference_attachments(prompt, character_sheet_path=character_sheet_path)
    body: list[str] = ["## 1) المرفقات (بالترتيب ده بالظبط)"]
    rows = [f"[{item['role']}] {item['path']}" for item in attachments]
    # handoff §8 I3: the sheet goes on every single message. If the accepted
    # sheet path is not known yet, say so loudly instead of shipping a message
    # that silently omits the one attachment that stops identity drift.
    if not any(item["role"] == "character-sheet" for item in attachments):
        rows.append("[character-sheet] ⚠️ ارفق شيت الشخصية المعتمد — إلزامي في كل رسالة")
    body.extend(f"{index}. {row}" for index, row in enumerate(rows, start=1))
    body.extend(
        [
            "",
            "## 2) قاعدة المرجع (إلزامية في كل رسالة)",
            doctrine.reference_sheet_clause(),
            "لو حصل تعارض بين «الواقعية» و«مطابقة الـReference Sheet» → المطابقة تكسب.",
            "",
            f"## 3) الشكل",
            f"- الاتجاه: {orientation} {ratio} — ممنوع بالطول.",
            "- مشهد واحد = صورة واحدة. ممنوع تقسيم لقطات أو فريم مقسوم.",
            "- صورة full-bleed لصفحة كاملة.",
            "",
        ]
    )

    beat = _clean(prompt.get("narrativeBeat"))
    request = _clean(prompt.get("primaryRequest"))
    body.append("## 4) المشهد")
    if beat:
        body.append(f"- دور الصفحة: {beat}")
    if request:
        body.append(f"- الحركة الأساسية: {request}")
    body.extend(_scene_block(prompt))

    people = _people_block(prompt)
    if people:
        body.extend(["", "## 5) الناس في الكادر", *people])

    staging = _clean(prompt.get("spatialStaging"))
    if staging and not staging.upper().startswith("CHANGE"):
        body.extend(["", f"- التوزيع في الكادر: {staging}"])

    composition = prompt.get("composition")
    if isinstance(composition, Mapping):
        comp_rows = [
            f"- {label}: {_clean(composition.get(key))}"
            for key, label in (
                ("shotScale", "حجم اللقطة"),
                ("viewpoint", "زاوية الكاميرا"),
                ("focalHierarchy", "ترتيب النظر"),
                ("lens", "العدسة"),
                ("depthOfField", "عمق الميدان"),
            )
            if _clean(composition.get(key)) and not _clean(composition.get(key)).upper().startswith("CHANGE")
        ]
        if comp_rows:
            body.extend(["", "## 6) الكاميرا", *comp_rows])

    style = prompt.get("style")
    if isinstance(style, Mapping):
        style_rows = _lines(
            value
            for value in (style.get("medium"), style.get("finish"))
            if _clean(value) and not _clean(value).upper().startswith("CHANGE")
        )
        if style_rows:
            body.extend(["", "## 7) الستايل", *style_rows])

    palette = _clean(prompt.get("palette"))
    color_script = _clean(prompt.get("colorScript"))
    body.extend(["", "## 8) الألوان (آمنة للطباعة — إلزامي)"])
    if palette and not palette.upper().startswith("CHANGE"):
        body.append(f"- باليت القصة: {palette}")
    if color_script and not color_script.upper().startswith("CHANGE"):
        body.append(f"- انحياز الباليت في الصفحة دي: {color_script}")
    body.append(f"- {doctrine.print_safe_clause('ar')}")

    body.extend(
        [
            "",
            "## 9) ممنوعات",
            "- ممنوع أي كتابة في الصورة: كلام، حروف، أرقام، لافتات، أغلفة كتب، لوجوهات.",
            "- الشريط السفلي من الكادر يفضل هادي وفاضي — من غير وشوش ولا أيدي ولا حركة مهمة، ومن غير أي مربع أو بانل مرسوم.",
            "- ممنوع أسماء شخصيات مرخصة، لا بالعربي ولا باللاتيني.",
            "- ممنوع أشخاص زيادة عن المذكورين فوق.",
        ]
    )
    avoid_rows = _lines(prompt.get("avoid") or [], bullet="- ")
    if avoid_rows:
        body.extend(avoid_rows[:12])

    if page_text and _clean(page_text):
        body.extend(
            [
                "",
                "## 10) نص الصفحة (للسياق بس — متكتبوش في الصورة)",
                "> النص بيتحط كطبقة نص حقيقية في الـPDF، مش في الرسمة.",
                "",
                "```",
                _clean(page_text),
                "```",
            ]
        )

    stop = [
        "",
        _SEPARATOR,
        f"## اوقف هنا",
        f"ولّد **{asset_id}** بس، وابعت الصورة. اوقف واستنى تأكيدي.",
    ]
    if next_asset_id:
        stop.append(f"متولّدش {_clean(next_asset_id)} غير لما أقولك.")
    stop.append("ممنوع توليد أكتر من صفحة في نفس الرد.")

    return "\n".join([*header, *body, *stop]).rstrip() + "\n"


def render_batch_file(blocks: list[Mapping[str, str]]) -> str:
    """Bundle at most two page instructions per file (handoff §8 I7)."""
    if not blocks:
        raise ManualDispatchError("Nothing to render")
    if len(blocks) > doctrine.load_doctrine()["imageTool"]["maxPagesPerFile"]:
        raise ManualDispatchError(
            "handoff §8 I7: a manual dispatch file carries at most "
            f"{doctrine.load_doctrine()['imageTool']['maxPagesPerFile']} pages"
        )
    ids = " ثم ".join(_clean(block.get("assetId")) for block in blocks)
    head = [
        f"# دفعة توليد يدوي — {ids}",
        "",
        "> ولّد الصفحة الأولى بس، ابعتها، استنى التأكيد، وبعدين الصفحة اللي بعدها.",
        "",
        _SEPARATOR,
        "",
    ]
    parts = [block.get("instruction", "") for block in blocks]
    return "\n".join(head) + ("\n\n" + _SEPARATOR + "\n\n").join(parts).rstrip() + "\n"


def render_character_sheet_instruction(
    prompt: Mapping[str, Any], *, asset_id: str = "character-sheet", hero_only: bool = True
) -> str:
    """Handoff §8 I8 — hero sheet is solo, supporting cast share one sheet."""
    angles = "، ".join(doctrine.character_sheet_angles())
    subject = "البطل لوحده" if hero_only else "كل الشخصيات المساندة مع بعض في شيت واحد"
    lines = [
        f"# تعليمة توليد شيت شخصية — {asset_id}",
        "",
        f"- الشيت ده لـ: {subject}.",
        f"- أربع زوايا في نفس الشيت: {angles}.",
        f"- الاتجاه: {doctrine.required_orientation()} {doctrine.required_aspect_ratio()}.",
        "- خلفية بيضا/محايدة، من غير أي كتابة ولا أرقام ولا تسميات.",
        "- نفس اللبس الثابت في كل الزوايا.",
        "",
        "## المرجع",
    ]
    attachments = reference_attachments(prompt)
    if attachments:
        lines.extend(f"{i}. [{a['role']}] {a['path']}" for i, a in enumerate(attachments, start=1))
    else:
        lines.append("1. ارفق صور الطفل الحقيقية")
    lines.extend(
        [
            "",
            "حوّل الطفل لشخصية كرتونية مطابقة، وثبّت الملامح دي كمرجع نهائي لكل صفحات الكتاب.",
            "",
            "## الألوان",
            doctrine.print_safe_clause("ar"),
            "",
            _SEPARATOR,
            f"ولّد {asset_id} بس، وابعته، واستنى تأكيدي.",
        ]
    )
    return "\n".join(lines) + "\n"
