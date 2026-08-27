"""Render one self-contained image instruction for the manual image lane.

Handoff §8 I1: the image tool has no state. Every message must carry the whole
job on its own — which files to attach, the prompt itself, the Arabic that has
to appear inside the artwork, and the one-page-per-reply stop.

The block is deliberately thin. Everything about *the picture* — scene layers,
staging, camera, style, palette, constraints — is already compiled into the
prompt at the end of the message, in the phrasing the chosen tool reads best.
Restating all of it in Arabic above the prompt doubled the length of every
dispatch and, worse, drifted: the Arabic wrapper and the English prompt started
giving the tool opposite instructions about the page text. So the wrapper now
carries only what the *operator* does — attach, paste, check, stop — and the
prompt carries the page.

That also makes the block portable. Nothing in it depends on this repository,
this machine, or this conversation, so the same message works pasted into
ChatGPT, into Nano Banana, or handed to somebody else's agent.
"""

from __future__ import annotations

from typing import Any, Mapping

import doctrine
import prompt_targets


class ManualDispatchError(RuntimeError):
    pass


_SEPARATOR = "─" * 46

ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _is_placeholder(value: str) -> bool:
    """True for a template field nobody filled in (`CHANGE: …`)."""
    return value.upper().startswith("CHANGE")


def _ar(number: Any) -> str:
    return str(number).translate(ARABIC_INDIC)


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
            if not path or _is_placeholder(path):
                continue
            attachments.append({"role": role, "path": path})
    if character_sheet_path and not any(
        item["role"] == "character-sheet" for item in attachments
    ):
        attachments.append({"role": "character-sheet", "path": _clean(character_sheet_path)})
    return attachments


def _placement_line(
    asset_id: str, role_label: str, page_number: Any, page_total: Any
) -> str:
    """Where this asset sits in the finished book.

    Somebody generating art outside the pipeline gets a folder of images with no
    order in it. Naming the slot in the title is what lets them file the result
    without asking.
    """
    title = f"# {asset_id} · {role_label}"
    try:
        number = int(page_number)
        total = int(page_total)
    except (TypeError, ValueError):
        return title
    if number <= 0 or total <= 0:
        return title
    return f"{title} — الصفحة {_ar(number)} من {_ar(total)} في الـPDF"


def _in_image_text(prompt: Mapping[str, Any]) -> str:
    """The exact Arabic the artwork has to contain (handoff §7)."""
    value = prompt.get("inImageText")
    text = str(value).strip() if isinstance(value, str) else ""
    return "" if _is_placeholder(text) else text


def _text_block(prompt: Mapping[str, Any], page_text: str | None) -> list[str]:
    """The in-image copy section, or a loud gap if the prompt lost the copy."""
    copy = _in_image_text(prompt)
    approved = _clean(page_text)
    if not copy:
        if approved:
            # validate-prompts refuses this, so it should never reach an
            # operator. If it does, saying so beats shipping a page that
            # silently prints without its story text.
            return [
                "- ⚠️ الصفحة ليها نص معتمد بس البرومبت مش شايله. "
                "شغّل `compile-prompts` تاني قبل ما تولّد أي حاجة.",
            ]
        return ["- الصورة دي بترجع من غير أي كتابة — كل سطح في الكادر فاضي."]
    surface = _clean(prompt.get("textSurface"))
    where = f"على «{surface}»" if surface and not _is_placeholder(surface) else "على سطح موجود في المشهد"
    return [
        f"- النص العربي متكتوب جوه الرسمة نفسها {where}، حرف بحرف زي ما هو تحت:",
        "",
        "```",
        copy,
        "```",
        "",
        "- ممنوع شريط سفلي، ولا بانل، ولا طبقة نص فوق الصورة. الكلام جزء من الرسمة.",
    ]


def _acceptance_block(
    prompt: Mapping[str, Any], page_text: str | None, *, has_people: bool
) -> list[str]:
    """What to look at before accepting the render — one line per failure mode."""
    rows: list[str] = []
    if _in_image_text(prompt):
        rows.append(
            "- [ ] النص العربي مطابق حرف بحرف: مش معكوس، الحروف موصولة، "
            "مفيش كلمة زايدة ولا ناقصة، ومفيش كلام خارج حدود السطح."
        )
    if has_people:
        rows.append(
            "- [ ] وش وشعر ولبس كل شخص زي الـReference Sheet بالظبط، "
            "ومحدش خد ملامح حد تاني."
        )
    canary = prompt_targets.tail_check(prompt)
    if canary:
        # Both tools silently ignore the tail of a long instruction, and a
        # dropped tail is invisible — the art still looks finished. So the
        # operator gets one element the page already requires to look for.
        rows.append(
            f"- [ ] «{canary}» ظاهر في الصورة. لو مش موجود، الأداة قصّت آخر "
            "التعليمة — ابعت الرسالة تاني كاملة من غير أي حذف."
        )
    rows.append(f"- [ ] الألوان: {doctrine.print_safe_clause('ar')}")
    rows.append("- [ ] مفيش أشخاص زيادة عن المذكورين، ومفيش أي علامة تجارية.")
    return rows


def _shape_rows(profile: prompt_targets.TargetProfile) -> list[str]:
    orientation = doctrine.required_orientation()
    ratio = doctrine.required_aspect_ratio()
    line = f"- الاتجاه: {orientation} {ratio} — ممنوع بالطول."
    if profile.aspect_ratio_in_prompt:
        line += f" والنسبة مكتوبة جوه البرومبت نفسه: aspect ratio {ratio}."
    return [
        line,
        "- مشهد واحد في صورة واحدة، full-bleed لصفحة كاملة. ممنوع فريم مقسوم أو لقطتين.",
    ]


def render_manual_instruction(
    prompt: Mapping[str, Any],
    *,
    asset_id: str,
    page_text: str | None = None,
    page_role: str = "story",
    page_number: Any = None,
    page_total: Any = None,
    character_sheet_path: str | None = None,
    next_asset_id: str | None = None,
    target: str = prompt_targets.DEFAULT_TARGET,
) -> str:
    """One paste-ready Arabic message for a single page (handoff §8 I1/I3/I5/I7).

    ``target`` chooses which image tool the message is written for. Only the
    pasted prompt changes with it — the operator steps are the same everywhere,
    which is what keeps the two lanes from drifting apart.
    """
    if not isinstance(prompt, Mapping):
        raise ManualDispatchError("prompt payload must be an object")
    asset_id = _clean(asset_id)
    if not asset_id:
        raise ManualDispatchError("asset_id is required")
    try:
        profile = prompt_targets.profile(target)
    except prompt_targets.TargetError as exc:
        raise ManualDispatchError(str(exc)) from exc

    role_label = doctrine.role_label_ar(page_role)
    lines: list[str] = [
        _placement_line(asset_id, role_label, page_number, page_total),
        "",
        f"> الأداة: **{profile.label}**.",
        "> الرسالة دي كاملة بذاتها. الأداة مش شايفة أي رسالة قبل كده، "
        "فمتعتمدش على أي حاجة اتقالت قبل الرسالة دي.",
        "",
        "## ١) ارفع المرفقات بالترتيب ده",
    ]

    attachments = reference_attachments(prompt, character_sheet_path=character_sheet_path)
    rows = [f"[{item['role']}] {item['path']}" for item in attachments]
    # handoff §8 I3: the accepted sheet goes on every single message. If its path
    # is not known yet, say so loudly instead of shipping a message that silently
    # omits the one attachment that stops identity drift.
    if not any(item["role"] == "character-sheet" for item in attachments):
        rows.append("⚠️ ارفق شيت الشخصية المعتمد — إلزامي في كل رسالة")
    lines.extend(f"{index}. {row}" for index, row in enumerate(rows, start=1))
    lines.extend(
        [
            "",
            f"**قاعدة المرجع (إلزامية في كل رسالة):** {doctrine.reference_sheet_clause()}",
            "لو حصل تعارض بين «الواقعية» و«مطابقة الـReference Sheet» → المطابقة تكسب.",
            "",
        ]
    )

    try:
        compiled = prompt_targets.compiled_for(prompt, target)
    except prompt_targets.TargetError:
        compiled = ""
    if not compiled:
        raise ManualDispatchError(
            f"{asset_id} has no compiled prompt for target '{profile.id}'. "
            "Run compile-prompts before dispatching."
        )
    lines.extend(
        [
            "## ٢) الزق البرومبت ده زي ما هو، من غير أي حذف ولا اختصار",
            "",
            "```text",
            compiled,
            "```",
            "",
            "## ٣) اللي لازم يرجع",
            *_shape_rows(profile),
        ]
    )
    lines.extend(_text_block(prompt, page_text))

    participants = prompt.get("participants")
    has_people = bool(
        isinstance(participants, list)
        and [
            entry
            for entry in participants
            if isinstance(entry, Mapping) and entry.get("onPage") is not False
        ]
    )
    lines.extend(
        [
            "",
            "## ٤) اتأكد من ده قبل ما تقبل الصورة",
            *_acceptance_block(prompt, page_text, has_people=has_people),
            "",
            _SEPARATOR,
            "## اوقف هنا",
            f"ولّد **{asset_id}** بس، وابعت الصورة، واستنى تأكيدي.",
        ]
    )
    if next_asset_id:
        lines.append(f"متولّدش {_clean(next_asset_id)} غير لما أقولك.")
    lines.append("ممنوع توليد أكتر من صفحة في نفس الرد.")

    return "\n".join(lines).rstrip() + "\n"


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
    prompt: Mapping[str, Any],
    *,
    asset_id: str = "character-sheet",
    hero_only: bool = True,
    target: str = prompt_targets.DEFAULT_TARGET,
) -> str:
    """Handoff §8 I8 — hero sheet is solo, supporting cast share one sheet.

    A sheet is the one asset that carries no copy at all: it exists to lock
    faces and outfits, and any writing on it would be copied onto every page
    that later uses it as a reference.
    """
    try:
        profile = prompt_targets.profile(target)
    except prompt_targets.TargetError as exc:
        raise ManualDispatchError(str(exc)) from exc
    angles = "، ".join(doctrine.character_sheet_angles())
    subject = "البطل لوحده" if hero_only else "كل الشخصيات المساندة مع بعض في شيت واحد"
    lines = [
        f"# {asset_id} · شيت شخصية — مرجع ثابت لكل صفحات الكتاب",
        "",
        f"> الأداة: **{profile.label}**.",
        "> الرسالة دي كاملة بذاتها.",
        "",
        "## ١) ارفع المرفقات بالترتيب ده",
    ]
    attachments = reference_attachments(prompt)
    if attachments:
        lines.extend(
            f"{index}. [{item['role']}] {item['path']}"
            for index, item in enumerate(attachments, start=1)
        )
    else:
        lines.append("1. ارفق صور الطفل الحقيقية")
    lines.extend(["", "حوّل الطفل لشخصية كرتونية مطابقة، وثبّت الملامح دي كمرجع نهائي لكل صفحات الكتاب.", ""])

    try:
        compiled = prompt_targets.compiled_for(prompt, target)
    except prompt_targets.TargetError:
        compiled = ""
    if compiled:
        lines.extend(
            [
                "## ٢) الزق البرومبت ده زي ما هو",
                "",
                "```text",
                compiled,
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## ٣) اللي لازم يرجع",
            f"- {subject}.",
            f"- أربع زوايا في نفس الشيت: {angles}.",
            f"- الاتجاه: {doctrine.required_orientation()} {doctrine.required_aspect_ratio()}.",
            "- خلفية بيضا/محايدة، ونفس اللبس الثابت في كل الزوايا.",
            "- الشيت من غير أي كتابة ولا أرقام ولا تسميات — أي كلام هنا هيتنسخ "
            "على كل صفحة بتستعمل الشيت ده كمرجع.",
            "",
            "## ٤) اتأكد من ده قبل ما تقبل الصورة",
            "- [ ] الأربع زوايا كلهم ظاهرين ونفس الشخصية في الأربعة.",
            "- [ ] مفيش أي كتابة ولا لوجو ولا واترمارك.",
            f"- [ ] الألوان: {doctrine.print_safe_clause('ar')}",
            "",
            _SEPARATOR,
            "## اوقف هنا",
            f"ولّد **{asset_id}** بس، وابعته، واستنى تأكيدي.",
        ]
    )
    return "\n".join(lines) + "\n"
