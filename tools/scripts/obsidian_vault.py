"""Make one client project openable as an Obsidian vault.

Each client folder gets its own `.obsidian` config and a small dashboard next to
`input/story-review.md`, so the human review gates open in a proper RTL vault
instead of a bare folder.

The studio-side rulebook notes that used to live here are gone: the operator
surface is Rawy now (`rawy_vault.py`, reached through `build-vault`), and the
doctrine notes this module generated had drifted into describing text handling
the pipeline stopped doing two doctrine changes ago.

Only core Obsidian plugins are configured. A vault that needs a community plugin
installed before it works is not "ready to use".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import doctrine

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
