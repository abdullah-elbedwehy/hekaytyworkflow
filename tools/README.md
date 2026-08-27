# Hekayati tools

Python helpers called by the repository-owned skill
`.agents/skills/hekayati` (Cursor and Claude Code load thin adapters that point
at it).

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
Open `Rawy/` as the Obsidian vault and follow the review link from the matching
client page. The Markdown file contains each page's exact text and scene description. After the user edits it,
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

**Start here:** `story_pipeline.py context --project /ABS/client`. It returns the
open gate, the next command, and the short list of reference files worth
loading for that step. `references/agent-core.md` is the index of everything
else; the stage files under `references/workflow/` hold the detail.

Key refs:

| File | Role |
|---|---|
| `agent-core.md` | Index of the stage files, schemas and skeletons |
| `workflow/routing.md` | State → command table, parallel law, image waves, hard bans |
| `workflow/story.md` | Goal, templates, the human story gate, structure, language, the seven locks |
| `workflow/prompts.md` | Prompt depth, staging, in-image Arabic, game pages, safe guests |
| `reviews/` | The four post-draft rubrics and the loop that merges them |
| `prompt-template.json` | Page prompt skeleton (multi-persona) |
| `character-sheet-template.json` | All-personas sheet |
| `location-sheet-template.json` | One empty place, multi-angle |
| `guests/catalog.json` | Vetted original guests (safe franchise stand-ins) |
| `prompt-fill-guide.md` | How to fill prompts — which field goes where |
| `prompt-rules.md` | Ultra-detail contract — word floors, banned vocabulary, the depth score |
| `prompt-targets.md` | One page, two image tools — what differs between the ChatGPT and Nano Banana renders and what never does |
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

## Colour: bright pages, fixed at generation

A picture book has to read as *light*. The generated art did not: measured
across this repo's books the median page arrived at a mean luminance of 115/255
with a fifth of its pixels below level 60, which prints heavy and muddy.

**The fix is in the prompt, not in the pixels.** The print-safe clause used to
say only "medium saturation, no pure black, no deep navy", which reads as an
instruction to be drab — and the art came back drab. It now asks for bright open
children's-book lighting, coloured shadows, and night scenes in readable moonlit
blue-grey, *before* the press constraints. Bright is not the opposite of
print-safe: an open page uses less ink than a dark one.

### Why there is no colour grading step

There was one, and it was removed. It graded every render onto brightness
targets and the numbers were excellent — across the 26-page book, mean luminance
118 → 146, pixels in shadow 19% → 2.7%, peak ink coverage 326% → 298%.

The pictures were wrong. Lifting a warm, lamp-lit room pushed it orange: on
page-19 the Lab **b\*** went from 25.6 to 40.0 and chroma rose 17 points. The
metric guarding against exactly that was mean hue, which reported under 1 degree
of drift and passed every page — blind by construction, because hue is an
*angle*, and the cast did not rotate the colour, it doubled its magnitude.

Turning off the chroma restore did not rescue it either: raising L raises Lab
chroma on its own (+7.3 with chroma at 1.00). No version of the grade left the
model's colour alone, so a page that comes back too dark is a page to
**regenerate**, not to doctor.

### Measuring instead

```bash
python3 tools/scripts/story_pipeline.py check-brightness --project /ABS/client
```

Reports every page's mean luminance, shadow share, and percentile spread, and
flags the ones that will print heavy. It never edits an image. The thresholds
are deliberately loose rather than a single number — a night scene is *supposed*
to sit darker than a picnic; what makes a page unprintable is being crushed into
the bottom of the range, not being dark.

## CMYK print export

The whole pipeline works in RGB: the art comes back RGB and the Arabic is
composed into it as RGB pixels. A press separates from CMYK, so the last step
rewrites the verified PDF into DeviceCMYK and then checks that it worked.

```bash
python3 tools/scripts/story_pipeline.py export-cmyk \
  --project /ABS/client --edition final
```

The output is always `<edition>-cmyk.pdf` next to the original, so the converted
file is impossible to confuse with the RGB master at the print shop. The export
refuses to leave that filename behind unless it verifies: every page reads back
as DeviceCMYK, no page is still DeviceRGB, and the page count is unchanged. A
failed or partial run deletes the file rather than handing a press something
that only looks converted.

| Flag | Effect |
|---|---|
| `--icc <path>` | Press-supplied output profile. Defaults to Coated FOGRA39, then US Web Coated SWOP, then the system generic profile |
| `--lossless` | Keep images Flate-encoded instead of letting Ghostscript re-encode them as JPEG |
| `--min-dpi N` | Warn below this effective page resolution (default 300) |
| `--no-preserve-black` | Allow near-black to separate as rich black instead of K-only |
| `--force` | Replace an existing export |

Black preservation is on by default (`-dKPreserve=2`): greys and near-blacks land
on the K plate instead of separating into four-colour rich black. That is what
keeps the Arabic composed into the art from becoming a registration problem
(handoff §9 P8). It is a best effort on baked-in pixels, not a guarantee — the
press still checks the separations.

### One illustration at a time

```bash
python3 tools/scripts/cmyk_export.py --image /ABS/page-19.v01.png
```

Writes `<name>-cmyk.tif` (CMYK, LZW, ICC embedded) and `<name>-cmyk-proof.png`.
The proof is that separation converted back to screen colour, so the drop in
saturation you see is the drop the press will print — comparing against the
original RGB tells you nothing useful. It also reports peak and mean total ink
coverage against the profile's own limit.

| Flag | Effect |
|---|---|
| `--intent relative` | Default. Keeps in-gamut colour where it is; only moves what the press cannot print |
| `--intent perceptual` | Compresses the whole gamut — protects gradients in very saturated art, shifts colours that would have printed fine |
| `--no-bpc` | Turn off black point compensation. Shadows plug; measured +8 mean TAC on this book |
| `--max-tac N` | Report against this ink limit instead of the profile's |

There is deliberately **no per-pixel K-only option**. Measured on page-19 of the
Abdullah book: the composed Arabic is rgb(30,35,38), the boy's denim is
rgb(37,43,47), his hair is rgb(27,21,17). The hair is darker and more neutral
than the jeans, so no threshold separates text from art — the attempt tore the
denim into grey speckle. Heavy-GCR separation via `--icc` is the lever that
works; genuinely K-only text needs the text to still be text at prepress.

Two things the export reports but cannot fix:

- **Effective resolution.** Colour conversion cannot add detail. If the warning
  says a page is below 300 dpi, the art has to be regenerated larger.
- **Total ink coverage.** Verify TAC against the press's own limit before the run.

Needs Ghostscript (`brew install ghostscript`); `doctor` checks for it.

## Obsidian

`Rawy/` is the one operator vault. Client projects live under the ignored
`Rawy/Clients/` folder; doctrine and tools remain outside the vault.

```bash
python3 tools/scripts/story_pipeline.py build-vault
python3 tools/scripts/story_pipeline.py init-vault \
  --project "$PWD/Rawy/Clients/client"
```

`build-vault` refreshes the core-only Obsidian config and every client page.
`init-vault` refreshes one client page. The dashboard links to
`input/story-review.md` in the same RTL vault. Rawy installs no community
plugin, so nothing has to be downloaded before the vault works.

### Moving around the vault

Every client note opens with a row of buttons (the `rawy-actions` callout, styled
by the vault CSS snippet — no community plugin involved):

- **🖼️ صور الكتاب / Book images** → that client's `Gallery.md`, regenerated on
  every `rawy-sync`: every asset that has an image on disk, embedded in book
  order (reference sheets, covers, then pages — `page-02` before `page-10`), each
  labelled with its asset id and status.
- **📄 / 📕 PDF** → the newest built edition.
- **🏠 Dashboard** and **📦 Archive**.

### Image review, before any PDF

The gallery is the review surface. Under every image is a comment box; the
operator writes an objection into the one they want changed, and the note is
read back and re-emitted on every `rawy-sync`, so it survives regenerating the
page. A written-in box renders expanded and outlined, and the flagged asset ids
are listed at the top of the gallery and counted on the client's gallery button.

```bash
python3 tools/scripts/story_pipeline.py image-notes --project /ABS/client
```

That reports exactly which assets to redo, so a rework pass touches only the
flagged pages instead of regenerating the book.

When nothing is outstanding, the operator signs off:

```bash
python3 tools/scripts/story_pipeline.py approve-images \
  --project /ABS/client --statement "شوفت الصور كلها وموافق"
```

`build --edition draft` refuses without that approval, and refuses again if any
image changed afterwards — the approval binds to the image bytes it was given,
the same way the story and final-PDF gates bind to theirs. `approve-images`
itself refuses while any image still carries a note, so the sign-off can never
contradict the gallery.

### Archive

Archiving is a property, not a folder move. Nothing is moved, renamed, or
deleted — the client note carries `archived: true`, every active view filters on
it, and `Archive.md` lists what those views are hiding.

Two doors onto the same switch:

- In Obsidian, tick `archived` in the client note's property editor.
- From the CLI (or by asking the agent):

```bash
python3 tools/scripts/story_pipeline.py rawy-archive --client /ABS/Rawy/Clients/<slug>
```

Add `--restore` to bring a client back. `Clients.base` gains an **Archived** view,
and an archived client stops reporting `needs_attention` however it was left, so
it drops out of the dashboard's attention list too.

`Rawy/Archive.md` is generated from client notes and therefore carries real
client names — it is Git-ignored alongside `Rawy/Clients/`.

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
