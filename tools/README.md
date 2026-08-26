# Hekayati tools

Python helpers called by the Cursor skill `.cursor/skills/hekayati`.

**Source of truth: [`references/handoff.md`](references/handoff.md)** — Omar's
rulebook. Everything below implements it. Machine-readable twin:
[`references/handoff/doctrine.json`](references/handoff/doctrine.json). Which
rule is enforced where: [`references/handoff-enforcement.md`](references/handoff-enforcement.md).

```bash
python3 tools/scripts/story_pipeline.py show-doctrine
python3 tools/scripts/story_pipeline.py show-doctrine --section bookStructure
python3 tools/scripts/story_pipeline.py check-doctrine --project /ABS/client
```

Every book is 24 PDF assets: `cover`, `page-01` الإهداء, `page-02`…`page-21`
(exactly 20 story pages), `page-22` «قصص تانية», `back-cover`. The three fixed
pages are written by `apply-fixed-pages`, never by hand.

Not a standalone agent skill. Entry point:

```bash
python3 tools/scripts/story_pipeline.py <command> --project /ABS/client
```

## First-time Mac setup

One command installs Homebrew (if needed), Python 3.9+, Node, Codex CLI,
Poppler, qpdf, and the Python image/PDF/Arabic-shaping dependencies. It does
**not** run `codex login` (browser auth — you do that once).

```bash
python3 tools/scripts/story_pipeline.py setup
# or:
bash tools/scripts/setup-mac.sh
```

Check readiness anytime:

```bash
python3 tools/scripts/story_pipeline.py doctor
```

Then only:

```bash
codex login
```

Schemas and image-prompt skeletons live in `tools/references/`.

Rights-cleared ready-made stories live in
`references/story-templates/catalog.json`. `list` and `show` need no client
project; `apply` needs an initialized client project. The current catalog has
original entertainment plans authored before handoff §7, so `apply-template`
reshapes each one into the 22+2 structure and opens the two missing story pages
as declared holes. The pipeline will not invent them — writing a filler scene is
exactly what handoff §3 N3 forbids — so `complete-template-customization` and
`lock-story` block until a human writes them. Educational books use the custom-story
route until an original educational template is explicitly cleared. Choose the
goal first, show only matching `qualityStatus: ready` entries, personalize one
into the client project, add an optional note, then continue through the normal
story review/lock/image flow. Applying writes an unlocked `input/story.json`;
it does not generate images.

Age-specific Egyptian dictionaries and narration contracts live in
`references/story-language/age-profiles.json`. Select the exact profile before
writing; then run deterministic and semantic QA. Every book must then pass the
human Markdown gate before lock:

```bash
python3 tools/scripts/story_pipeline.py list-age-profiles
python3 tools/scripts/story_pipeline.py show-age-profile --age 5
python3 tools/scripts/story_pipeline.py review-story --project /ABS/client
python3 tools/scripts/story_pipeline.py prepare-story-review --project /ABS/client
# STOP: user reviews/edits /ABS/client/input/story-review.md.
python3 tools/scripts/story_pipeline.py approve-story-review \
  --project /ABS/client --statement "راجعت كل الصفحات وموافق"
python3 tools/scripts/story_pipeline.py lock-story --project /ABS/client
```

`review-story` checks word/sentence limits, Egyptian register, protected exact
quotations, ordered `narrativeArc`, hero-owned choice/action, and unbridged hard
scene cuts. Also apply the semantic story rubric to the text-only draft before
images: prove the educational change or deliver the entertainment fantasy.
The client project itself can be opened as an Obsidian vault. The Markdown file
contains each page's exact text and scene description. After the user edits it,
approval syncs the fields back to `story.json` and records both content hashes.
Any later story or Markdown edit makes the approval stale. `lock-story`,
preflight, image generation, and PDF building all block until the current
revision is approved.

```bash
python3 tools/scripts/story_pipeline.py set-story-goal \
  --project /ABS/client --mode educational \
  --goal "يتعلم يجهز شنطته وينزل المدرسة في ميعاده"
python3 tools/scripts/story_pipeline.py list-templates --intent educational
python3 tools/scripts/story_pipeline.py list-templates \
  --intent entertainment --category fantasy
python3 tools/scripts/story_pipeline.py show-template --template <ID>
python3 tools/scripts/story_pipeline.py apply-template \
  --project /ABS/client --template <ID>
python3 tools/scripts/story_pipeline.py prepare-story-review --project /ABS/client
# User reviews and explicitly approves the Markdown file, then:
python3 tools/scripts/story_pipeline.py lock-story --project /ABS/client
```

Add or replace the note before story lock:

```bash
python3 tools/scripts/story_pipeline.py set-template-note \
  --project /ABS/client --note "خلي المغامرة يوم عيد ميلاده"
# Tailor the affected story pages, then:
python3 tools/scripts/story_pipeline.py complete-template-customization \
  --project /ABS/client
python3 tools/scripts/story_pipeline.py prepare-story-review --project /ABS/client
# User review + approve-story-review comes here.
python3 tools/scripts/story_pipeline.py lock-story --project /ABS/client
```

The note is a requirement, not decoration. Tailor affected page beats, run
`complete-template-customization`, then lock. Pass `--note ''` to clear it.
`--force` may replace only a draft created before prompts or images exist.

Personalization — habits, traits, and must-appear places/things the family gives
about the child. A habit requires the educational branch. One habit per book
owns the story arc; `lock-story` refuses to lock until its exact replacement
behaviour appears in both a turn and a later reinforce page:

```bash
python3 tools/scripts/story_pipeline.py set-personalization \
  --project /ABS/client --json '{"habitFocus": {...}, "requests": [...]}'
python3 tools/scripts/story_pipeline.py show-personalization --project /ABS/client
```

Contract: `references/personalization.md`.

Validate catalog + workflow:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tools/tests -p 'test_*.py' -v
```

**Start here:** `references/agent-core.md` — baked multi-persona + parallel + function routing.

Key refs:

| File | Role |
|---|---|
| `agent-core.md` | Operating contract for the agent |
| `prompt-template.json` | Page prompt skeleton (multi-persona) |
| `character-sheet-template.json` | All-personas sheet |
| `location-sheet-template.json` | One empty place, multi-angle |
| `guests/catalog.json` | Vetted original guests (safe franchise stand-ins) |
| `prompt-fill-guide.md` | How to fill prompts — which field goes where |
| `prompt-rules.md` | Ultra-detail contract — word floors, banned vocabulary, the depth score |
| `interview.md` / `story-schema.md` / `brief-schema.md` | Contracts |
| `personalization.md` | Child habits, traits, must-appear requests |
| `story-language/age-profiles.json` | Age dictionaries, word budgets, required arc stages |
| `story-language/age-dictionaries-ar.md` | Human-readable Arabic word lists and narration style by age |
| `story-language/README.md` | Writing method, coherence gate, evidence notes |
| `story-templates/catalog.json` | Ready-made personalized adventures |
| `handoff.md` | **The rulebook.** Everything else is downstream of it |
| `handoff/doctrine.json` | Machine-readable rulebook read by `doctrine.py` |
| `handoff-enforcement.md` | Which handoff rule is enforced where, and what is left to humans |

Prompt flow — the agent fills structured fields, the pipeline writes the prompt:

```bash
python3 tools/scripts/story_pipeline.py preflight --project /ABS/client
python3 tools/scripts/story_pipeline.py generate-book-images --project /ABS/client
```

`preflight` compiles the prompts, validates them, checks the environment and the
Arabic font, and returns **every** blocker in one call — instead of surfacing one
failure per round trip. `compile-prompts` and `validate-prompts` are still there
when you want them individually.

Prompt quality is gated, not suggested. `validate-prompts` scores each prompt
0-100 and blocks vague fields, filler words, unfilled `CHANGE:` stubs, props with
no colour or material, and two adjacent pages sharing both shot scale and
viewpoint. The rules the score implements: `references/prompt-rules.md`.

```bash
# Default bar: 80 for pages, 70 for sheets.
python3 tools/scripts/story_pipeline.py validate-prompts --project /ABS/client
# Ultra-detail bar: also requires lens, depth of field, and colour script per page.
python3 tools/scripts/story_pipeline.py validate-prompts --project /ABS/client --min-depth 95
```

How far along a book is, and how much longer it has to run:

```bash
python3 tools/scripts/story_pipeline.py progress --project /ABS/client
```

Every command that takes `--project` also attaches the same `progress` block to
its own output, so the agent can report the percent after each step without an
extra call. The ETA is extrapolated from the render times this book actually
measured, not a fixed guess.

## Obsidian

The repository is a vault; `vault/` holds notes generated from the doctrine.

```bash
python3 tools/scripts/story_pipeline.py build-vault
python3 tools/scripts/story_pipeline.py init-vault --project /ABS/client
```

`init` already scaffolds the client vault, so `input/story-review.md` opens in a
proper RTL vault with a dashboard beside it.

## Manual image lane (handoff §8)

```bash
python3 tools/scripts/story_pipeline.py manual-dispatch \
  --project /ABS/client --asset page-05 --asset page-06 \
  --out /ABS/client/output/manual
```

One self-contained Arabic message per page: reference-sheet clause, full scene,
landscape 16:9, print-safe palette, and an explicit stop. Two pages per file
maximum, one page per reply — the phone tool has no memory.

Safe guest lookup when a family asks for a famous character:

```bash
python3 tools/scripts/story_pipeline.py list-guests
python3 tools/scripts/story_pipeline.py show-guest --guest web-swinger
```
