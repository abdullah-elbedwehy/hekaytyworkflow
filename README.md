# Hekayati workflow

**Source of truth: [`tools/references/handoff.md`](tools/references/handoff.md).**
Every rule in this repository descends from that document. Where anything here
disagrees with it, the handoff wins. Machine-readable twin:
[`tools/references/handoff/doctrine.json`](tools/references/handoff/doctrine.json);
rule-by-rule enforcement map:
[`tools/references/handoff-enforcement.md`](tools/references/handoff-enforcement.md).

Hekayati builds personalized Arabic children's picture books with a mandatory
human story-review gate before any illustration is generated. The workflow
creates an Obsidian-friendly Markdown storyboard containing every page’s exact
Arabic text and scene description, stops, and waits for the family/editor to
review it.

The repository contains workflow code only. Create each client project outside
this repository; child photos and generated books must never be committed.

## Setup

macOS:

```bash
bash tools/scripts/setup-mac.sh
codex login
python3 tools/scripts/story_pipeline.py doctor
```

The setup installs Python dependencies plus the PDF inspection/rendering tools.
Image generation uses the user-installed Codex `imagegen` skill only.

## Permanent story-review gate

Initialize a client folder outside this checkout and draft or apply a story:

```bash
python3 tools/scripts/story_pipeline.py init --project /ABS/CLIENT --pages 20
python3 tools/scripts/story_pipeline.py prepare-story-review --project /ABS/CLIENT
```

Open `/ABS/CLIENT` itself as an Obsidian vault, then edit
`input/story-review.md`. Keep the page/field marker comments intact; change the
visible page text and scene description only. The workflow will not lock the
story or start an image job while this review is pending or stale.

After the editor confirms the file:

```bash
python3 tools/scripts/story_pipeline.py story-review-status --project /ABS/CLIENT
python3 tools/scripts/story_pipeline.py approve-story-review \
  --project /ABS/CLIENT \
  --statement "راجعت كل الصفحات وموافق على النص والمشاهد"
python3 tools/scripts/story_pipeline.py lock-story --project /ABS/CLIENT
```

Approval is bound to the reviewed Markdown and normalized `story.json` hashes.
Any later story or review-file edit makes the approval stale and blocks prompts,
images, PDF building, and preflight until the review is prepared and approved
again.

The rest of the production flow is:

```text
goal + age + personas + consent
→ story draft
→ Markdown/Obsidian review and explicit approval
→ story lock
→ prompt preflight
→ Codex image generation
→ draft PDF and four review rubrics
→ explicit final approval
→ final PDF
```

Every book is **24 PDF assets** (handoff §7): a separate front cover, 22
interior pages — `page-01` الإهداء, `page-02`…`page-21` the 20 story pages,
`page-22` «قصص تانية» — and a separate back cover. The dedication, the
«قصص تانية» page, and the back-cover marketing copy are fixed text owned by the
doctrine; write them with `apply-fixed-pages`, never by hand. Art themes always come
from the live theme catalog; do not hard-code a short menu. Illustrations are
text-free: the PDF builder adds the exact Arabic as a real text layer.

## Tests

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tools/tests -p 'test_*.py' -v
git diff --check
```

## The handoff doctrine

```bash
python3 tools/scripts/story_pipeline.py show-doctrine
python3 tools/scripts/story_pipeline.py show-doctrine --section bookStructure
python3 tools/scripts/story_pipeline.py set-story-type --project /ABS/CLIENT --type A
python3 tools/scripts/story_pipeline.py apply-fixed-pages --project /ABS/CLIENT
python3 tools/scripts/story_pipeline.py check-doctrine --project /ABS/CLIENT
```

`review-story`, `lock-story`, and `preflight` all carry the doctrine verdict, so
a metaphor for an inner feeling, a rewritten dedication, a missing story type, or
a 19-page book blocks the run before any image is generated.

## Obsidian

The repository itself is an Obsidian vault. Open the repo folder in Obsidian and
start at [`vault/Home.md`](vault/Home.md) — doctrine notes, the two gate
checklists, the book tracker, and the runbooks are all generated from the
doctrine, so the checklist a human ticks is the rule the pipeline enforces.

```bash
python3 tools/scripts/story_pipeline.py build-vault
```

Each client project is a vault too. `init` scaffolds it; `init-vault` repairs an
older one.

## The manual image lane

Handoff §8 describes the phone tool Omar actually uses: no memory, one page per
reply, the reference sheet re-attached every time. Export paste-ready Arabic
instruction blocks with:

```bash
python3 tools/scripts/story_pipeline.py manual-dispatch \
  --project /ABS/CLIENT --asset page-05 --out /ABS/CLIENT/output/manual
```

The automated Codex lane is unchanged; this is the export for the manual one.

Detailed operating instructions are in
[`tools/references/agent-core.md`](tools/references/agent-core.md) and the Cursor
skill at [`.cursor/skills/hekayati/SKILL.md`](.cursor/skills/hekayati/SKILL.md).
The rulebook itself is [`tools/references/handoff.md`](tools/references/handoff.md).

