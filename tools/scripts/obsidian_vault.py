"""Build the Obsidian vaults — the studio rulebook and each client project.

Two vaults, one rulebook:

* **Studio vault** — the repository itself. `vault/` holds notes generated from
  `handoff/doctrine.json`, so the checklists a human ticks are literally the
  rules the pipeline enforces. Regenerate with `build-vault`; never hand-edit a
  file marked `generated: true`.
* **Client vault** — each client project gets its own `.obsidian` config and a
  dashboard next to `input/story-review.md`, so the review gate opens in a
  proper RTL vault instead of a bare folder.

Only core Obsidian plugins are configured. A vault that needs a community
plugin installed before it works is not "ready to use".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import doctrine

GENERATED_MARKER = "hekayati-generated"

# Core plugins only — everything below ships with Obsidian.
_CORE_PLUGINS = {
    "file-explorer": True,
    "global-search": True,
    "switcher": True,
    "graph": True,
    "backlink": True,
    "outgoing-link": True,
    "tag-pane": True,
    "page-preview": True,
    "templates": True,
    "note-composer": True,
    "command-palette": True,
    "editor-status": True,
    "bookmarks": True,
    "outline": True,
    "word-count": True,
    "file-recovery": True,
}

_IGNORE_FILTERS = [
    ".venv/",
    ".git/",
    "node_modules/",
    "__pycache__/",
    ".pytest_cache/",
    "tools/.corpus/",
    "output/images/",
    "output/renders/",
    "output/contact-sheets/",
]


class VaultError(RuntimeError):
    pass


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = text if text.endswith("\n") else text + "\n"
    path.write_text(payload, encoding="utf-8")
    return path


def _write_json(path: Path, payload: Any) -> Path:
    return _write(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _front_matter(title: str, *, tags: Iterable[str], generated: bool = True) -> str:
    tag_list = ", ".join(sorted({str(tag) for tag in tags}))
    lines = [
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"tags: [{tag_list}]",
    ]
    if generated:
        lines.extend(
            [
                "generated: true",
                f"generated_by: {GENERATED_MARKER}",
                f"doctrine_version: {json.dumps(doctrine.load_doctrine()['doctrineVersion'])}",
            ]
        )
    lines.append("---")
    if generated:
        lines.extend(
            [
                "",
                "> [!info] ملف متولّد",
                "> الملف ده بيتكتب من `tools/references/handoff/doctrine.json`. "
                "لو عايز تغيّر قاعدة، غيّرها في الدكترين وشغّل `build-vault` تاني — "
                "أي تعديل يدوي هنا هيتمسح.",
            ]
        )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# .obsidian configuration
# --------------------------------------------------------------------------


def write_obsidian_config(
    vault_root: Path,
    *,
    template_folder: str | None = None,
    ignore_filters: Iterable[str] | None = None,
    base_font_size: int = 17,
) -> list[Path]:
    """Write a ready-to-open `.obsidian` config: RTL on, core plugins only."""
    config = vault_root / ".obsidian"
    written = [
        _write_json(
            config / "app.json",
            {
                "rightToLeft": True,
                "readableLineLength": True,
                "alwaysUpdateLinks": True,
                "newLinkFormat": "shortest",
                "useMarkdownLinks": False,
                "attachmentFolderPath": "./",
                "showUnsupportedFiles": True,
                "strictLineBreaks": False,
                "showLineNumber": False,
                "spellcheck": False,
                "livePreview": True,
                "userIgnoreFilters": list(ignore_filters or []),
            },
        ),
        _write_json(
            config / "appearance.json",
            {
                "theme": "system",
                "baseFontSize": base_font_size,
                "textFontFamily": "",
                "monospaceFontFamily": "",
                "cssTheme": "",
                "showViewHeader": True,
            },
        ),
        _write_json(config / "core-plugins.json", dict(_CORE_PLUGINS)),
        _write_json(config / "community-plugins.json", []),
        _write_json(config / "hotkeys.json", {}),
        _write_json(
            config / "graph.json",
            {"showTags": True, "showAttachments": False, "showOrphans": True},
        ),
    ]
    if template_folder:
        written.append(_write_json(config / "templates.json", {"folder": template_folder}))
    return written


def write_bookmarks(vault_root: Path, items: list[dict[str, str]]) -> Path:
    payload = {
        "items": [
            {"type": "file", "path": item["path"], "title": item["title"]} for item in items
        ],
    }
    return _write_json(vault_root / ".obsidian" / "bookmarks.json", payload)


# --------------------------------------------------------------------------
# Studio vault (the repository itself)
# --------------------------------------------------------------------------


def _rule_table(rows: Iterable[Mapping[str, Any]], id_key: str = "id", text_key: str = "ruleAr") -> str:
    lines = ["| ID | القاعدة |", "|---|---|"]
    for row in rows:
        rule = str(row.get(text_key) or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| **{row.get(id_key)}** | {rule} |")
    return "\n".join(lines)


def _checkbox_list(items: Iterable[str]) -> str:
    return "\n".join(f"- [ ] {item}" for item in items)


def _doctrine_note_rulebook() -> str:
    d = doctrine.load_doctrine()
    literal = d["literalLanguage"]
    return "\n".join(
        [
            _front_matter("قواعد الـHandoff", tags=["doctrine", "handoff"]),
            "",
            "# قواعد الـHandoff",
            "",
            "المصدر الكامل: [[handoff|handoff.md]] · التنفيذ: [[handoff-enforcement]]",
            "",
            "## 2) اللغة الحرفية — الأولوية القصوى",
            "",
            _rule_table(literal["rules"]),
            "",
            "### أنماط ممنوعة بيتلقطها الـvalidator",
            "",
            "| ID | بيلقط إيه | الخطورة |",
            "|---|---|---|",
            *[
                f"| `{p['id']}` | {p['messageAr']} | {p['severity']} |"
                for p in [*literal["metaphorPatterns"], *literal["wisdomPatterns"]]
            ],
            "",
            "## 3) البنية الحكائية",
            "",
            _rule_table(d["narrativeStructure"]["rules"]),
            "",
            "## 4) القيود الثقافية",
            "",
            _rule_table(d["culturalConstraints"]["rules"]),
            "",
            "## 6) اللهجة",
            "",
            *[f"- {note}" for note in d["dialect"]["notesAr"]],
            "",
            "### استبدالات إلزامية",
            "",
            "| بدل ما تكتب | اكتب | ليه |",
            "|---|---|---|",
            *[
                f"| {r['term']} | **{r['useInstead']}** | {r['reason']} |"
                for r in d["dialect"]["registerReplacements"]
            ],
            "",
            "```query",
            'tag:#doctrine',
            "```",
        ]
    )


def _doctrine_note_book_structure() -> str:
    structure = doctrine.book_structure()
    slots = doctrine.structure_slots(structure["pdfPageCount"])
    return "\n".join(
        [
            _front_matter("هيكل الكتاب", tags=["doctrine", "structure"]),
            "",
            "# هيكل الكتاب — 22 صفحة + غلافين",
            "",
            f"- `settings.pdfPageCount` = **{structure['pdfPageCount']}**",
            f"- صفحات داخلية = **{structure['interiorPageCount']}**",
            f"- صفحات قصة = **{structure['storyPageCount']}** بالظبط",
            "",
            "| الترتيب | assetId | الدور |",
            "|---|---|---|",
            "| الغلاف الأمامي | `cover` | منفصل، برة الـ22 |",
            f"| صفحة 1 | `{slots['dedication']}` | الإهداء |",
            f"| صفحات 2 → 21 | `{slots['storyPages'][0]}` … `{slots['storyPages'][-1]}` | القصة ({slots['storyPageCount']} صفحة) |",
            f"| صفحة 22 | `{slots['otherStories']}` | قصص تانية ({doctrine.other_stories_row_count()} صفوف، RTL) |",
            "| الغلاف الخلفي | `back-cover` | منفصل، برة الـ22 |",
            "",
            "## قاعدة الدمج",
            "",
            f"> {structure['mergeRuleAr']}",
            "",
            "## الإهداء (نص ثابت)",
            "",
            "```",
            structure["dedicationTemplateAr"].replace("{{hero}}", "[اسم الطفل]"),
            "```",
            "",
            "## الغلاف الخلفي (نص ثابت)",
            "",
            "```",
            doctrine.back_cover_text(),
            "```",
            "",
            f"**الأيقونات الخمسة إلزامية:** {doctrine.back_cover_icon_line()}",
            "",
            "الصفحتين الثابتين بيتكتبوا آليًا:",
            "",
            "```bash",
            "python3 tools/scripts/story_pipeline.py apply-fixed-pages --project /ABS/CLIENT",
            "```",
        ]
    )


def _doctrine_note_story_types() -> str:
    types = doctrine.story_types()
    rows = [
        "| النوع | الاستخدام | `storyGoal.mode` | رفيق سحري | انتكاسة إلزامية |",
        "|---|---|---|---|---|",
    ]
    for key in sorted(types):
        entry = types[key]
        companion = (
            "إلزامي"
            if entry.get("requiresMagicalCompanion")
            else ("ممنوع" if entry.get("allowsMagicalCompanion") is False else "اختياري")
        )
        rows.append(
            f"| **Type {key}** — {entry['labelAr']} | {entry['usageAr']} | "
            f"`{entry['storyGoalMode']}` | {companion} | "
            f"{'أيوه' if entry.get('requiresRelapseBeat') else 'لأ'} |"
        )
    detail: list[str] = []
    for key in sorted(types):
        entry = types[key]
        detail.extend(["", f"### Type {key} — {entry['labelAr']}", ""])
        detail.extend(f"- {item}" for item in entry.get("requires") or [])
    return "\n".join(
        [
            _front_matter("تصنيف القصص", tags=["doctrine", "story-type"]),
            "",
            "# تصنيف القصص (A / B / C)",
            "",
            "`story.storyType` لازم يتحدد قبل أي كتابة، وبيتفرض في `review-story` و`lock-story`.",
            "",
            *rows,
            *detail,
        ]
    )


def _doctrine_note_print() -> str:
    section = doctrine.load_doctrine()["printSafeColor"]
    return "\n".join(
        [
            _front_matter("ألوان آمنة للطباعة", tags=["doctrine", "print"]),
            "",
            "# ألوان آمنة للطباعة",
            "",
            f"**المطبعة:** {section['printer']} · **التصنيف:** {section['coverageClass']} · "
            f"**الورق:** {section['stock']}",
            "",
            _rule_table(section["rules"]),
            "",
            "## الأرقام اللي بتتحط في التصدير",
            "",
            f"- Ink Limit: **{section['inkLimitPercent']}%**",
            f"- فصل الألوان: **{section['separationMethod']}** (مش UCR)",
            f"- نص مطبوع: **{section['textBlack']}**",
            f"- ليل: `{section['nightSceneHex']}` — مش `{section['bannedNightSceneHex']}`",
            f"- تقليل التشبع: **{section['saturationReductionPercent'][0]}–{section['saturationReductionPercent'][1]}%**",
            "",
            "## الجملة اللي بتتلزق في كل برومبت",
            "",
            "```text",
            section["promptClauseEn"],
            "```",
            "",
            "```text",
            section["promptClauseAr"],
            "```",
        ]
    )


def _doctrine_note_image_tool() -> str:
    tool = doctrine.load_doctrine()["imageTool"]
    games = tool["gamePages"]
    return "\n".join(
        [
            _front_matter("قواعد أداة الصور", tags=["doctrine", "images"]),
            "",
            "# قواعد أداة الصور",
            "",
            f"**اللاين اليدوي:** {tool['primaryLaneAr']}",
            "",
            _rule_table(tool["lessons"], text_key="ruleAr"),
            "",
            "## جملة المرجع (بتتلزق حرفيًا في كل رسالة)",
            "",
            "```text",
            tool["referenceSheetClauseAr"],
            "```",
            "",
            "## صفحات الألعاب",
            "",
            f"- **متاهة:** {games['mazeAr']}",
            f"- **دور على حاجات / اختلافات:** {games['spotTheThingAr']}",
            f"- **المكان:** {games['placementAr']}",
            f"- **الرفيق:** {games['companionAr']}",
            "",
            "## توليد التعليمات",
            "",
            "```bash",
            "python3 tools/scripts/story_pipeline.py manual-dispatch \\",
            "  --project /ABS/CLIENT --asset page-05",
            "python3 tools/scripts/story_pipeline.py manual-dispatch \\",
            "  --project /ABS/CLIENT --asset page-05 --asset page-06 --out /ABS/CLIENT/output/manual",
            "```",
            "",
            "→ [[Manual Image Lane]]",
        ]
    )


def _checklist_pre_prompt() -> str:
    return "\n".join(
        [
            _front_matter("جيت ما قبل البرومبتات", tags=["checklist", "gate"]),
            "",
            "# جيت ما قبل البرومبتات",
            "",
            "ماتطلعش أي برومبت صورة قبل ما كل بند هنا يبقى متعلّم.",
            "",
            "## النص",
            "",
            _checkbox_list(
                [
                    "نص القصة كامل اتبعت لعمر واتوافق عليه صراحة",
                    "مفيش مجاز أدبي لوصف مشاعر داخلية (L1)",
                    "حل الأزمة العاطفية بفعل ملموس مش تحول داخلي (L3)",
                    "كلام الطمأنة مباشر ومش حكمة (L4)",
                    "جملة الجسر لحظة التحول موجودة (N1)",
                    "الخوف/الغيرة خطاب مباشر للشخص المعني (N2)",
                    "المكافأة مربوطة بفعل أثبته البطل (N4)",
                    "وعد الأهل اتحقق فعلاً قرب النهاية (N6)",
                    "الأصحاب لاحظوا علامة خارجية مش بالسحر (N8)",
                    "«ماما»/«بابا» مش «أمه»/«والده»",
                    "مفيش ظروف حشو زيادة",
                    "اتساق الضمائر مع المخاطَب",
                ]
            ),
            "",
            "## البنية",
            "",
            _checkbox_list(
                [
                    "22 صفحة داخلية + غلافين منفصلين",
                    "20 صفحة قصة بالظبط بعد الدمج",
                    "الإهداء مكتوب بالقالب الثابت",
                    "صفحة «قصص تانية» فيها 3 صفوف RTL",
                    "الغلاف الخلفي بالنص التسويقي الثابت + 5 أيقونات",
                    "مكان صفحة اللعبة منطقي حركيًا (N7)",
                ]
            ),
            "",
            "## الثقافي",
            "",
            _checkbox_list(
                [
                    "الأصحاب الجانبيين من نفس نوع البطل (C1)",
                    "مفيش لعب مختلط قريب متكرر (C2)",
                    "مفيش مشاركة أكل شخصية (C3)",
                ]
            ),
            "",
            "## التحقق الآلي",
            "",
            "```bash",
            "python3 tools/scripts/story_pipeline.py check-doctrine --project /ABS/CLIENT",
            "python3 tools/scripts/story_pipeline.py review-story --project /ABS/CLIENT",
            "python3 tools/scripts/story_pipeline.py preflight --project /ABS/CLIENT",
            "```",
        ]
    )


def _checklist_pre_print() -> str:
    section = doctrine.load_doctrine()["printSafeColor"]
    return "\n".join(
        [
            _front_matter("جيت ما قبل المطبعة", tags=["checklist", "print", "gate"]),
            "",
            "# جيت ما قبل المطبعة",
            "",
            f"المطبعة: **{section['printer']}** ({section['coverageClass']})",
            "",
            _checkbox_list(
                [
                    "مفيش خلفية كحلي غامق أو أسود خالص full-bleed في أي صفحة",
                    "التشبع اتقلل 15–20% عن الافتراضي",
                    "مشاهد الليل على `#2C3E50` مش `#0A1633`",
                    "مفيش `#000000` كتعبئة في أي مكان",
                    "كل النص K-only (100K / 0C / 0M / 0Y) — مفيش Rich Black",
                    f"Ink Limit متظبط على {section['inkLimitPercent']}%",
                    f"{section['separationMethod']} مفعّل بدل UCR",
                    "كل صفحة اتفحصت في Acrobat Pro → Output Preview → Total Area Coverage",
                    "الغلافين متصدّرين منفصلين عن الـ22 صفحة",
                    "طبقة النص العربي حقيقية وقابلة للتحديد في الـPDF",
                ]
            ),
            "",
            "```bash",
            "python3 tools/scripts/story_pipeline.py verify --project /ABS/CLIENT --edition final",
            "```",
        ]
    )


def _checklist_page_review() -> str:
    return "\n".join(
        [
            _front_matter("مراجعة صفحة", tags=["checklist", "review"], generated=False),
            "",
            "# مراجعة صفحة — `{{page}}`",
            "",
            "> انسخ الملف ده لكل صفحة محتاجة مراجعة يدوية.",
            "",
            "**الكتاب:** ",
            "**الصفحة:** ",
            "**الدور في القصة:** ",
            "",
            "## النص",
            "",
            _checkbox_list(
                [
                    "مفيش مجاز",
                    "المشاعر مباشرة",
                    "اللهجة مصرية طبيعية",
                    "الصفحة بتخدم المشكلة السلوكية بتاعة القصة دي",
                ]
            ),
            "",
            "## الصورة",
            "",
            _checkbox_list(
                [
                    "الوجه مطابق للـReference Sheet (مفيش drift)",
                    "اللبس الثابت زي ما هو",
                    "Landscape 16:9",
                    "مفيش أي كتابة في الصورة",
                    "الشريط السفلي هادي وفاضي",
                    "الباليت آمن للطباعة",
                    "مفيش أشخاص زيادة",
                ]
            ),
            "",
            "## القرار",
            "",
            "- [ ] مقبولة",
            "- [ ] محتاجة إعادة توليد — السبب: ",
        ]
    )


def _status_note() -> str:
    status = doctrine.load_doctrine()["projectStatus"]
    brand = status["brandName"]
    rows = ["| القصة | النوع | الموضوع | الحالة |", "|---|---|---|---|"]
    for story in status["stories"]:
        marker = " 🔴" if story.get("active") else ""
        rows.append(
            f"| {story['titleAr']}{marker} | {story['type']} | {story['topicAr']} | {story['status']} |"
        )
    return "\n".join(
        [
            _front_matter("حالة المشروع", tags=["status"]),
            "",
            "# حالة المشروع",
            "",
            f"*آخر تحديث: {status['updatedAt']} — {status['note']}*",
            "",
            "## القصص",
            "",
            *rows,
            "",
            "🔴 = القصة النشطة حاليًا.",
            "",
            "## اسم البراند",
            "",
            f"- **الحالة:** {brand['status']}",
            f"- **الاتجاه:** {brand['directionAr']}",
            f"- **مرفوض:** {'، '.join(brand['rejected'])}",
            "",
            "→ [[Brand Names]]",
            "",
            "## المطبعة",
            "",
            f"- **{status['printer']['name']}** — {status['printer']['noteAr']}",
            "",
            "→ [[Print Handoff]] · [[جيت ما قبل المطبعة]]",
        ]
    )


def _brand_note() -> str:
    brand = doctrine.load_doctrine()["projectStatus"]["brandName"]
    rejected = "\n".join(f"| {name} | مرفوض | |" for name in brand["rejected"])
    return "\n".join(
        [
            _front_matter("أسماء البراند", tags=["status", "brand"], generated=False),
            "",
            "# أسماء البراند",
            "",
            f"**الاتجاه:** {brand['directionAr']}",
            "",
            "معايير الاختيار:",
            "",
            "- مخترع بالكامل، من غير معنى سابق بالعربي أو الإنجليزي",
            "- ينطق بسهولة بالمصري وبالإنجليزي",
            "- الدومين `.com` متاح",
            "- ماشي مع حساب إنستجرام بنفس الاسم",
            "- مش قريب من علامة قايمة في نفس المجال",
            "",
            "| الاسم | الحالة | ملاحظات |",
            "|---|---|---|",
            rejected,
            "",
            "> الجدول ده يدوي — ضيف المرشحين الجداد تحت وحدّث الحالة.",
        ]
    )


def _runbook_new_book() -> str:
    order = doctrine.load_doctrine()["workflowOrder"]
    return "\n".join(
        [
            _front_matter("رن بوك — كتاب جديد", tags=["runbook"]),
            "",
            "# رن بوك — كتاب جديد",
            "",
            "## الترتيب الإلزامي",
            "",
            *[f"{index}. {step}" for index, step in enumerate(order, start=1)],
            "",
            "## الأوامر بالترتيب",
            "",
            "```bash",
            "TOOLS=/Users/abdullah/Desktop/hekaytyworkflow/tools",
            "CLIENT=/ABS/PATH/TO/CLIENT",
            "",
            "# 1. مشروع جديد بهيكل الـhandoff (24 asset = 22 داخلية + غلافين)",
            "python3 $TOOLS/scripts/story_pipeline.py init --project $CLIENT",
            "python3 $TOOLS/scripts/story_pipeline.py init-vault --project $CLIENT",
            "",
            "# 2. النوع والهدف",
            "python3 $TOOLS/scripts/story_pipeline.py set-story-type --project $CLIENT --type A",
            "python3 $TOOLS/scripts/story_pipeline.py set-story-goal --project $CLIENT \\",
            '  --mode educational --goal "..."',
            "",
            "# 3. النص، وبعدين الصفحتين الثابتين",
            "python3 $TOOLS/scripts/story_pipeline.py apply-fixed-pages --project $CLIENT",
            "python3 $TOOLS/scripts/story_pipeline.py check-doctrine --project $CLIENT",
            "python3 $TOOLS/scripts/story_pipeline.py review-story --project $CLIENT",
            "",
            "# 4. جيت المراجعة البشرية",
            "python3 $TOOLS/scripts/story_pipeline.py prepare-story-review --project $CLIENT",
            "#    STOP — عمر يفتح الفولت ويعدّل input/story-review.md",
            "python3 $TOOLS/scripts/story_pipeline.py approve-story-review --project $CLIENT \\",
            '  --statement "راجعت كل الصفحات وموافق"',
            "python3 $TOOLS/scripts/story_pipeline.py lock-story --project $CLIENT",
            "",
            "# 5. البرومبتات والصور",
            "python3 $TOOLS/scripts/story_pipeline.py preflight --project $CLIENT",
            "python3 $TOOLS/scripts/story_pipeline.py generate-book-images --project $CLIENT",
            "",
            "# 6. الـPDF والمراجعات",
            "python3 $TOOLS/scripts/story_pipeline.py build --project $CLIENT --edition draft",
            "python3 $TOOLS/scripts/story_pipeline.py verify --project $CLIENT --edition draft",
            "```",
            "",
            "→ [[جيت ما قبل البرومبتات]] · [[جيت ما قبل المطبعة]]",
        ]
    )


def _runbook_manual_lane() -> str:
    tool = doctrine.load_doctrine()["imageTool"]
    return "\n".join(
        [
            _front_matter("Manual Image Lane", tags=["runbook", "images"]),
            "",
            "# اللاين اليدوي لتوليد الصور",
            "",
            f"الأداة: {tool['primaryLaneAr']}. مالهاش ذاكرة — كل رسالة لازم تبقى كاملة بذاتها.",
            "",
            "## القواعد اللي بتحكم كل رسالة",
            "",
            f"- صفحة واحدة بس في كل رد (`maxPagesPerMessage = {tool['maxPagesPerMessage']}`)",
            f"- ملف الدفعة فيه صفحتين بحد أقصى (`maxPagesPerFile = {tool['maxPagesPerFile']}`)",
            f"- الاتجاه: {tool['orientation']} {tool['aspectRatio']} دايمًا",
            "- الـReference Sheet مرفق في كل رسالة، والصور المولّدة قبل كده ممنوعة كمرجع",
            "- مشهد واحد = صورة واحدة، من غير تقسيم لقطات",
            "",
            "## توليد الملفات",
            "",
            "```bash",
            "# صفحة واحدة على الشاشة",
            "python3 tools/scripts/story_pipeline.py manual-dispatch \\",
            "  --project $CLIENT --asset page-05",
            "",
            "# دفعة صفحتين لملف Markdown جوه الفولت",
            "python3 tools/scripts/story_pipeline.py manual-dispatch \\",
            "  --project $CLIENT --asset page-05 --asset page-06 \\",
            "  --out $CLIENT/output/manual",
            "",
            "# كل الكتاب، ملف لكل دفعة صفحتين",
            "python3 tools/scripts/story_pipeline.py manual-dispatch \\",
            "  --project $CLIENT --all --out $CLIENT/output/manual",
            "```",
            "",
            "الملفات بتتكتب في `output/manual/` جوه فولت العميل، فتقدر تفتحها على "
            "الموبايل وتنسخ الرسالة زي ما هي.",
            "",
            "## ترتيب التوليد",
            "",
            "1. شيت البطل (4 زوايا، لوحده)",
            "2. شيت الشخصيات المساندة (كلهم في شيت واحد، 4 زوايا)",
            "3. صفحات الأماكن",
            "4. صفحات القصة بالترتيب",
            "5. **الأغلفة في الآخر** عشان تطلع شبه الفن النهائي",
            "",
            "→ [[قواعد أداة الصور]]",
        ]
    )


def _runbook_print() -> str:
    section = doctrine.load_doctrine()["printSafeColor"]
    return "\n".join(
        [
            _front_matter("Print Handoff", tags=["runbook", "print"]),
            "",
            f"# تسليم المطبعة — {section['printer']}",
            "",
            f"التصنيف: **{section['coverageClass']}** على ورق **{section['stock']}**. "
            "التصنيف ده هو سبب كل قواعد الألوان الآمنة.",
            "",
            "## قبل التصدير",
            "",
            "- الفن كله خالي من أي كتابة؛ العربي طبقة نص حقيقية في الـPDF",
            f"- كل النص K-only ({section['textBlack']})",
            f"- Ink Limit {section['inkLimitPercent']}% · {section['separationMethod']} بدل UCR",
            "",
            "## الفحص",
            "",
            "Adobe Acrobat Pro → **Output Preview** → **Total Area Coverage** → "
            f"حط الحد على {section['inkLimitPercent']}% وشوف أي منطقة بتضوي.",
            "",
            "## اللي بيتبعت",
            "",
            "1. ملف الداخل: 22 صفحة",
            "2. ملف الغلاف: أمامي + خلفي منفصلين",
            "3. مواصفة الورق والتجليد",
            "",
            "→ [[جيت ما قبل المطبعة]] · [[ألوان آمنة للطباعة]]",
        ]
    )


def _book_note(story: Mapping[str, Any]) -> str:
    type_id = str(story.get("type") or "")
    try:
        type_entry = doctrine.story_type(type_id)
        type_label = f"Type {type_id} — {type_entry['labelAr']}"
        mode = type_entry["storyGoalMode"]
    except doctrine.DoctrineError:
        type_label = f"Type {type_id}"
        mode = "?"
    return "\n".join(
        [
            _front_matter(story["titleAr"], tags=["book", f"type-{type_id.lower()}"], generated=False),
            "",
            f"# {story['titleAr']}",
            "",
            f"- **النوع:** {type_label} (`{mode}`)",
            f"- **الموضوع:** {story['topicAr']}",
            f"- **الحالة:** {story['status']}",
            "- **مسار المشروع:** ",
            "",
            "## الحالة",
            "",
            _checkbox_list(
                [
                    "النص كامل واتوافق عليه",
                    "الدمج لـ20 صفحة قصة",
                    "الإهداء + صفحة «قصص تانية» + الغلاف الخلفي",
                    "شيت البطل معتمد",
                    "شيت الشخصيات المساندة",
                    "صفحات القصة",
                    "الأغلفة",
                    "PDF مسودة + مراجعة",
                    "فحص TAC/GCR",
                    "اتبعت للمطبعة",
                ]
            ),
            "",
            "## ملاحظات",
            "",
            "",
        ]
    )


def _book_tracker(stories: list[Mapping[str, Any]]) -> str:
    rows = ["| القصة | النوع | الحالة |", "|---|---|---|"]
    for story in stories:
        rows.append(f"| [[{story['titleAr']}]] | {story['type']} | {story['status']} |")
    return "\n".join(
        [
            _front_matter("متابعة الكتب", tags=["book", "tracker"]),
            "",
            "# متابعة الكتب",
            "",
            *rows,
            "",
            "## كل الكتب في الفولت",
            "",
            "```query",
            "tag:#book",
            "```",
            "",
            "## بنود لسه مفتوحة",
            "",
            "```query",
            'task-todo:""',
            "```",
        ]
    )


def _home_note() -> str:
    d = doctrine.load_doctrine()
    status = d["projectStatus"]
    active = next((s for s in status["stories"] if s.get("active")), None)
    return "\n".join(
        [
            _front_matter("Hekayati — البيت", tags=["home"]),
            "",
            "# Hekayati — لوحة التحكم",
            "",
            f"> **مصدر الحقيقة:** [[handoff|handoff.md]] · نسخة الدكترين `{d['doctrineVersion']}`",
            "",
            (
                f"**القصة النشطة:** [[{active['titleAr']}]] — {active['status']}"
                if active
                else "**القصة النشطة:** مفيش"
            ),
            "",
            "## ابدأ من هنا",
            "",
            "| عايز تعمل إيه | روح فين |",
            "|---|---|",
            "| تبدأ كتاب جديد | [[رن بوك — كتاب جديد]] |",
            "| تعرف القواعد | [[قواعد الـHandoff]] |",
            "| تختار نوع القصة | [[تصنيف القصص]] |",
            "| تعرف شكل الكتاب | [[هيكل الكتاب]] |",
            "| تولّد صور بالموبايل | [[Manual Image Lane]] |",
            "| تجهّز للمطبعة | [[Print Handoff]] |",
            "| تشوف حالة المشروع | [[حالة المشروع]] |",
            "",
            "## الجيتين اللي مايتعديش عليهم",
            "",
            "- [[جيت ما قبل البرومبتات]] — قبل أي برومبت صورة",
            "- [[جيت ما قبل المطبعة]] — قبل أي إرسال للمطبعة",
            "",
            "## أوامر سريعة",
            "",
            "```bash",
            "python3 tools/scripts/story_pipeline.py show-doctrine",
            "python3 tools/scripts/story_pipeline.py check-doctrine --project $CLIENT",
            "python3 tools/scripts/story_pipeline.py progress --project $CLIENT",
            "```",
            "",
            "## بنود لسه مفتوحة في الفولت كله",
            "",
            "```query",
            'task-todo:""',
            "```",
        ]
    )


def _template_new_book() -> str:
    return "\n".join(
        [
            "---",
            "title: كتاب جديد",
            "tags: [book]",
            "---",
            "",
            "# {{title}}",
            "",
            "- **النوع:** Type ",
            "- **الطفل:** ",
            "- **السن:** ",
            "- **الموضوع/السلوك:** ",
            "- **مسار المشروع:** ",
            "- **بدأ:** {{date}}",
            "",
            "## الحالة",
            "",
            "- [ ] النص كامل واتوافق عليه",
            "- [ ] الدمج لـ20 صفحة قصة",
            "- [ ] الصفحات الثابتة (إهداء / قصص تانية / غلاف خلفي)",
            "- [ ] شيت البطل معتمد",
            "- [ ] شيت الشخصيات المساندة",
            "- [ ] صفحات القصة",
            "- [ ] الأغلفة",
            "- [ ] PDF مسودة + مراجعة",
            "- [ ] فحص TAC/GCR",
            "- [ ] اتبعت للمطبعة",
            "",
            "## ملاحظات",
            "",
        ]
    )


def _template_manual_batch() -> str:
    return "\n".join(
        [
            "---",
            "title: دفعة توليد يدوي",
            "tags: [images, manual-dispatch]",
            "---",
            "",
            "# دفعة {{date}}",
            "",
            "**الكتاب:** ",
            "**الصفحات:** ",
            "",
            "> صفحة واحدة في كل رد. الـReference Sheet مرفق في كل رسالة.",
            "",
            "## الحالة",
            "",
            "- [ ] الصفحة الأولى اتولدت واتقبلت",
            "- [ ] الصفحة التانية اتولدت واتقبلت",
            "",
            "## إعادة المحاولات",
            "",
            "| الصفحة | المحاولة | المشكلة |",
            "|---|---|---|",
            "|  |  |  |",
        ]
    )


def build_studio_vault(repo_root: Path) -> dict[str, Any]:
    """Generate the repository studio vault. Idempotent."""
    repo_root = Path(repo_root).resolve()
    vault = repo_root / "vault"
    doctrine.load_doctrine(refresh=True)
    status = doctrine.load_doctrine()["projectStatus"]

    written: list[Path] = []
    written.extend(
        write_obsidian_config(
            repo_root,
            template_folder="vault/90-Templates",
            ignore_filters=_IGNORE_FILTERS,
        )
    )

    notes: list[tuple[str, str]] = [
        ("Home.md", _home_note()),
        ("00-Doctrine/قواعد الـHandoff.md", _doctrine_note_rulebook()),
        ("00-Doctrine/تصنيف القصص.md", _doctrine_note_story_types()),
        ("00-Doctrine/هيكل الكتاب.md", _doctrine_note_book_structure()),
        ("00-Doctrine/ألوان آمنة للطباعة.md", _doctrine_note_print()),
        ("00-Doctrine/قواعد أداة الصور.md", _doctrine_note_image_tool()),
        ("01-Checklists/جيت ما قبل البرومبتات.md", _checklist_pre_prompt()),
        ("01-Checklists/جيت ما قبل المطبعة.md", _checklist_pre_print()),
        ("01-Checklists/مراجعة صفحة.md", _checklist_page_review()),
        ("02-Books/_متابعة الكتب.md", _book_tracker(status["stories"])),
        ("03-Status/حالة المشروع.md", _status_note()),
        ("03-Status/Brand Names.md", _brand_note()),
        ("04-Runbook/رن بوك — كتاب جديد.md", _runbook_new_book()),
        ("04-Runbook/Manual Image Lane.md", _runbook_manual_lane()),
        ("04-Runbook/Print Handoff.md", _runbook_print()),
        ("90-Templates/كتاب جديد.md", _template_new_book()),
        ("90-Templates/دفعة توليد يدوي.md", _template_manual_batch()),
    ]
    for relative, body in notes:
        written.append(_write(vault / relative, body))

    # One note per known book — never clobber notes the owner has edited.
    for story in status["stories"]:
        path = vault / "02-Books" / f"{story['titleAr']}.md"
        if not path.exists():
            written.append(_write(path, _book_note(story)))

    written.append(
        write_bookmarks(
            repo_root,
            [
                {"path": "vault/Home.md", "title": "🏠 البيت"},
                {"path": "tools/references/handoff.md", "title": "📜 handoff"},
                {"path": "vault/01-Checklists/جيت ما قبل البرومبتات.md", "title": "✅ قبل البرومبتات"},
                {"path": "vault/01-Checklists/جيت ما قبل المطبعة.md", "title": "🖨️ قبل المطبعة"},
                {"path": "vault/03-Status/حالة المشروع.md", "title": "📊 الحالة"},
            ],
        )
    )

    return {
        "vault": str(repo_root),
        "notesRoot": str(vault),
        "written": [str(path) for path in written],
        "openWith": f"Obsidian → Open folder as vault → {repo_root}",
    }


# --------------------------------------------------------------------------
# Client vault
# --------------------------------------------------------------------------


def _client_home(project: Path, book: Mapping[str, Any] | None) -> str:
    settings = (book or {}).get("settings") or {}
    page_count = settings.get("pdfPageCount")
    slots = None
    if isinstance(page_count, int) and page_count >= 5:
        try:
            slots = doctrine.structure_slots(page_count)
        except doctrine.DoctrineError:
            slots = None
    structure_rows: list[str] = []
    if slots:
        structure_rows = [
            "",
            "## هيكل الكتاب ده",
            "",
            f"- إجمالي أصول الـPDF: **{slots['pdfPageCount']}**",
            f"- الإهداء: `{slots['dedication']}`",
            f"- القصة: `{slots['storyPages'][0]}` → `{slots['storyPages'][-1]}` "
            f"({slots['storyPageCount']} صفحة)",
            f"- قصص تانية: `{slots['otherStories']}`",
            "- الأغلفة: `cover` + `back-cover` (منفصلين)",
        ]
    return "\n".join(
        [
            "---",
            f"title: {json.dumps(project.name, ensure_ascii=False)}",
            "tags: [client, home]",
            "---",
            "",
            f"# {project.name}",
            "",
            "> الفولدر ده فولت Obsidian كامل. افتحه من Obsidian → Open folder as vault.",
            "",
            "## الملفات اللي بتتعامل معاها",
            "",
            "| الملف | إيه ده |",
            "|---|---|",
            "| [[story-review]] | **الملف اللي بتراجعه وتعدّل فيه.** عدّل جوه الخانات بس. |",
            "| [[interview]] | سجل الأسئلة والإجابات |",
            "| [[requirements]] | المتطلبات المتفق عليها |",
            "| [[_مراجعتي]] | ملاحظاتك أثناء المراجعة |",
            "",
            "> [!warning] قاعدة المراجعة",
            "> في `story-review.md` ماتغيّرش ولا تمسح أي علامة HTML بتبدأ بـ `hekayati:` — "
            "دي اللي بتخلي التعديلات ترجع للنظام صح.",
            *structure_rows,
            "",
            "## بعد ما تخلص المراجعة",
            "",
            "```bash",
            f"CLIENT={project}",
            "python3 $TOOLS/scripts/story_pipeline.py story-review-status --project $CLIENT",
            "python3 $TOOLS/scripts/story_pipeline.py approve-story-review --project $CLIENT \\",
            '  --statement "راجعت كل الصفحات وموافق"',
            "```",
            "",
            "## بنود لسه مفتوحة",
            "",
            "```query",
            'task-todo:""',
            "```",
        ]
    )


def _client_review_notes() -> str:
    return "\n".join(
        [
            "---",
            "title: مراجعتي",
            "tags: [client, review]",
            "---",
            "",
            "# ملاحظات المراجعة",
            "",
            "> اكتب هنا اللي عايز يتغير. الملف ده ملكك — النظام مابيقراهوش.",
            "",
            "## صفحات محتاجة تعديل",
            "",
            "| الصفحة | المشكلة | التعديل المطلوب |",
            "|---|---|---|",
            "|  |  |  |",
            "",
            "## القواعد اللي بأراجع بيها",
            "",
            "- [ ] مفيش مجاز أدبي لوصف مشاعر داخلية",
            "- [ ] المشاعر مقولة مباشرة زي ما الطفل بيفكر",
            "- [ ] حل الأزمة بفعل ملموس",
            "- [ ] كلام الطمأنة مباشر مش حكمة",
            "- [ ] «ماما»/«بابا» مش «أمه»/«والده»",
            "- [ ] جملة الجسر في لحظة التحول موجودة",
            "- [ ] المكافأة مربوطة بفعل أثبته البطل",
            "- [ ] وعد الأهل اتحقق قرب النهاية",
            "- [ ] الأصحاب الجانبيين من نفس نوع البطل",
            "- [ ] مفيش مشاركة أكل شخصية",
            "- [ ] 20 صفحة قصة بالظبط",
        ]
    )


def scaffold_client_vault(project: Path, book: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Make one client project openable as an Obsidian vault."""
    project = Path(project).resolve()
    if not project.is_dir():
        raise VaultError(f"Project folder does not exist: {project}")

    written = write_obsidian_config(
        project,
        ignore_filters=[
            "output/images/",
            "output/renders/",
            "output/contact-sheets/",
            "input/style/",
            "__pycache__/",
        ],
        base_font_size=18,
    )
    home = project / "Home.md"
    written.append(_write(home, _client_home(project, book)))
    notes = project / "_مراجعتي.md"
    if not notes.exists():
        written.append(_write(notes, _client_review_notes()))
    (project / "output" / "manual").mkdir(parents=True, exist_ok=True)

    written.append(
        write_bookmarks(
            project,
            [
                {"path": "Home.md", "title": "🏠 البيت"},
                {"path": "input/story-review.md", "title": "📝 مراجعة القصة"},
                {"path": "_مراجعتي.md", "title": "🗒️ ملاحظاتي"},
            ],
        )
    )

    return {
        "project": str(project),
        "written": [str(path) for path in written],
        "home": str(home),
        "reviewNotes": str(notes),
        "manualDispatchDir": str(project / "output" / "manual"),
        "openWith": f"Obsidian → Open folder as vault → {project}",
    }
