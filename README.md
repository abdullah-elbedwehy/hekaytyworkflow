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

The repository contains the portable workflow and the Rawy Obsidian interface.
Private client projects live only under the Git-ignored
`Rawy/Clients/<slug>/` tree; child photos and generated books must never be
committed.

## Setup

macOS:

```bash
bash tools/scripts/setup-mac.sh
codex login
python3 tools/scripts/story_pipeline.py doctor
```

The setup installs Python dependencies plus the PDF inspection/rendering tools.
Image generation uses Codex `imagegen` through the bundled repository
dispatcher. No separate Hekayati or image-dispatch skill installation is
needed.

## Permanent story-review gate

Create a Rawy client and draft or apply a story in its private folder:

```bash
python3 tools/scripts/story_pipeline.py rawy-new-client \
  --name "NAME" --phone "PHONE" --request "REQUEST" --slug CLIENT
python3 tools/scripts/story_pipeline.py init \
  --project "$PWD/Rawy/Clients/CLIENT" --pages 24
python3 tools/scripts/story_pipeline.py prepare-story-review \
  --project "$PWD/Rawy/Clients/CLIENT"
```

Open `Rawy/` as the Obsidian vault, enter the client page, then edit the linked
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
from the live theme catalog; do not hard-code a short menu. The image model draws
each page's approved Arabic **inside** the illustration, on a surface that belongs
to the scene, so the words live in the picture — never as a caption overlay. The
PDF carries the same string invisibly so copy, search and `verify` keep working.

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

## Rawy in Obsidian

Open [`Rawy/Dashboard.md`](Rawy/Dashboard.md) as the vault home. The dashboard
carries two links and two tables: what needs attention, and every client. Each
client page links directly to its available story review and PDFs. Doctrine,
technical JSON, prompts, caches, and heavy image folders stay outside the
visible operator navigation.

Rawy uses Obsidian core Bases, search, and bookmarks only — the community-plugin
list is empty and no plugin has to be installed. Every action on the dashboard is
a plain link core Obsidian can follow, and every editable field is a note
property, editable in the properties panel or straight in the Bases table.
`build-vault` remains a compatibility alias for a full Rawy refresh; `init-vault`
refreshes one Rawy client.

## The manual image lane

Handoff §8 describes the phone tool Omar actually uses: no memory, one page per
reply, the reference sheet re-attached every time. Export paste-ready Arabic
instruction blocks with:

```bash
python3 tools/scripts/story_pipeline.py manual-dispatch \
  --project /ABS/CLIENT --asset page-05 --out /ABS/CLIENT/output/manual
```

The automated Codex lane is unchanged; this is the export for the manual one.

## Where the instructions live

One chain, no duplicates:

| File | Owns |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Operator contract — privacy, client data, how to behave. `CLAUDE.md` and the Cursor rule only point here. |
| [`.agents/skills/hekayati/SKILL.md`](.agents/skills/hekayati/SKILL.md) | The router: the ten production gates and what to load when. |
| [`tools/references/workflow/`](tools/references/workflow) | Stage detail — `routing.md`, `story.md`, `prompts.md`. Loaded per step, not per session. |
| [`tools/references/reviews/`](tools/references/reviews) | The four post-draft rubrics. |
| [`tools/references/handoff.md`](tools/references/handoff.md) | The law. Wins every conflict. |

A session orients with one command instead of reading the stack:

```bash
python3 tools/scripts/story_pipeline.py context --project /ABS/CLIENT
```

It returns the open gate, the exact next command, and the two or three files
worth reading for that step.
