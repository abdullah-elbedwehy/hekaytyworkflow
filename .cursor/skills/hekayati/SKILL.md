---
name: hekayati
description: >-
  Cursor entry for Hekayati Arabic children's books. Multi-persona OK. On ابدأ /
  start, ask whether the goal is educational or entertainment, then offer only
  matching ready story-templates + ALL art themes, or custom interview. Then
  story, mandatory user-edited Markdown review, JSON prompts folder (write all
  in parallel), Codex $imagegen via generate-book-images (character then all
  pages parallel), draft PDF, auto review rubrics, iterate. Client folder holds
  all artifacts; tools/ is scripts only. Use when user points at a
  persona/client folder or says ابدأ / Hekayati / حكايتي.
---

# Hekayati (Cursor)

**Source of truth: `$TOOLS/references/handoff.md`.** Everything below descends
from it; if they disagree, the handoff wins. Read the rulebook with
`show-doctrine`, check a story against it with `check-doctrine`. Enforcement map:
`$TOOLS/references/handoff-enforcement.md`.

**Read next:** `$TOOLS/references/agent-core.md` (baked parallel + multi-persona + routing).

## Hard rules

| Location | Role |
|---|---|
| `hekaytyworkflow/tools/` | Scripts + schemas only |
| Client project | **All** run data (`input/` + `output/`) |
| `~/.cursor/skills/codex-imagegen` | User-installed image dispatch (Codex `$imagegen` only) |

- Never write client artifacts into `hekaytyworkflow/`.
- **Book shape is fixed:** 24 PDF assets — `cover`, `page-01` الإهداء,
  `page-02`…`page-21` (20 story pages), `page-22` «قصص تانية», `back-cover`.
  Fixed copy comes from `apply-fixed-pages`, never from you.
- **Story type first:** A (تصحيح سلوك) / B (تشجيع على مكان) / C (مغامرة) —
  `set-story-type`. A needs a magical companion + a `setback` beat; B forbids a
  magical companion.
- **No literary metaphor for inner feelings.** Say it the way the child thinks
  it. Resolve emotion with a concrete event, not an inner shift.
- Never Gemini API / OpenAI Images API / key CSVs.
- Images use `generate-book-images` / the user-installed `codex-imagegen` skill
  only. Do not add a second provider lane.
- **Parallel by default** — all prompts in one pass; all pages in one Codex dispatch; reviews in parallel.

```text
<client>/
  personas/*.png          # 1..N people (multi-persona supported)
  input/{interview.md,requirements.md,brief.json,story.json,story-review.md,prompts/*.json}
  output/{book.json,images/,pdf/,reviews/}
```

`TOOLS` = absolute path to `hekaytyworkflow/tools`.

## Flow

```text
0) read the doctrine: show-doctrine (handoff.md is the rulebook)
1) init + identities; ASK GOAL FIRST: educational OR entertainment → set-story-goal
   then set-story-type --type A|B|C (handoff §5)
2) list only matching ready templates (drafts stay hidden) OR custom; pick art theme; consent
3) load exact age profile; ready-made: apply-template (+ optional note/age adaptation) → deterministic review-story → semantic story rubric → complete-template-customization
   custom: write story.json (incl. storyGoal + narrativeArc + locations[] bible) → deterministic review-story → semantic story rubric
3b) apply-fixed-pages (الإهداء + قصص تانية + الغلاف الخلفي) → check-doctrine
    merge the draft down to exactly 20 story pages first (handoff §7)
4) prepare-story-review → STOP; user edits input/story-review.md in Obsidian → re-read → approve-story-review → lock-story
5) write ALL input/prompts/ in one pass (character-sheet + location-sheets + every page)
   — rules: $TOOLS/references/prompt-rules.md (depth gate is enforced, not advisory)
6) preflight → one verdict listing every blocker at once (compiles + validates for you)
7) generate-book-images: [sheet + ALL location sheets together] → human accept → interior → covers LAST
8) build + verify draft → show PDF
9) auto reviews (4 rubrics parallel) + merge-reviews
10) fix loop → explicit final approval → final PDF
```

**Report the percent after every long step.** Every command returns a `progress`
block; paste `progress.messageAr` verbatim. Mid-render, answer «خلصنا كام؟» with
`progress --project <ABS>`. Never estimate by hand.

**Seven locks** (see `agent-core.md`): identity · place · shape · prompt · age
language · causal story spine · educational/entertainment goal.

**The doctrine gate** runs inside `review-story`, `prepare-story-review`,
`complete-template-customization`, `lock-story`, and `preflight`. A metaphor for
an inner feeling, a rewritten dedication, a missing `storyType`, a 19-page book,
or an unwritten expansion slot blocks the run before any image.

### Personalization mode

When the family describes the child instead of a plot — a habit, things they
love, "لازم بيت جدته يظهر" — run `set-personalization`. One habit per book owns
the arc (setup → challenge → turn → reinforce, the child decides on `turn`);
extra habits and traits become small beats; must-appear requests become
locations and recurring props. `lock-story` blocks until `story.personalization`
carries `habitArc` + `requestCoverage`. Contract: `$TOOLS/references/personalization.md`.

### Be helpful (book start)

On `ابدأ` / `start` / new book, ask one short question first:
`تحب القصة تساعد في سلوك/قيمة، ولا تبقى مغامرة للتسلية؟`

Record the answer before suggesting plots:

```bash
python3 $TOOLS/scripts/story_pipeline.py set-story-goal --project <ABS> \
  --mode educational --goal "يوصل المدرسة في ميعاده"
# OR: --mode entertainment --goal "يساعد بطل مقنّع ينقذ المدينة"

python3 $TOOLS/scripts/story_pipeline.py list-templates --intent educational
# OR: --intent entertainment
python3 $TOOLS/scripts/story_pipeline.py list-themes
```

Show every **ready** template in the chosen branch (Arabic title + one-line
summary) and every art theme (`labelAr` + short look). Draft/quarantined
templates are diagnostic only; never offer or apply them. Offer **قصة مخصوص**
as an option. Then confirm names/roles/outfits/age and apply choices.

### Smart function map

| Need | Command |
|---|---|
| First Mac machine | `setup` then `codex login` (check: `doctor`) |
| New project | `init --project <ABS> --pages N` |
| Decide story branch | `set-story-goal --project <ABS> --mode educational\|entertainment --goal …` |
| Family described the child (عادة / صفة / لازم يظهر) | `set-personalization --project <ABS> --json '{…}'` |
| Review what was captured | `show-personalization --project <ABS>` |
| Browse matching ready-made stories | `list-templates --intent educational\|entertainment` / `show-template --template ID` |
| Choose ready-made story | `apply-template --project <ABS> --template ID [--note …]` |
| Change template note before lock | `set-template-note --project <ABS> --note …` |
| Note incorporated in pages | `complete-template-customization --project <ABS>` |
| Export editable storyboard | `prepare-story-review --project <ABS>` → stop and show `input/story-review.md` |
| Check editor changes | `story-review-status --project <ABS>` |
| User approved storyboard | `approve-story-review --project <ABS> --statement "…"` → `lock-story` |
| Exact age voice/dictionary | `show-age-profile --age N` |
| Story wording/causality QA | `review-story --project <ABS>` |
| Browse art themes | `list-themes` |
| Art theme | `apply-theme --project <ABS> --theme <themeId>` |
| Famous character asked for | `list-guests` / `show-guest --guest <key>` |
| Prompts written | `preflight --project <ABS>` (compiles, validates, and lists every blocker in one call) |
| Ultra-detail bar | `validate-prompts --project <ABS> --min-depth 95` — requires lens, depth of field, colour script on every page |
| "خلصنا كام؟" mid-run | `progress --project <ABS>` → paste `progress.messageAr` |
| Images | `generate-book-images --project <ABS>` (Codex only) |
| Accept sheet | `character-review --project <ABS> --accept` |
| Draft PDF | `build` + `verify` `--edition draft` |
| Merge reviews | `merge-reviews --project <ABS>` |
| Attempt limit/manual issue | `resolve-manual-review --asset ID (--accept\|--image <ABS>) --statement "…"` |
| Read the rulebook | `show-doctrine [--section bookStructure\|storyTypes\|printSafeColor\|imageTool]` |
| Check one story against the handoff | `check-doctrine --project <ABS>` |
| Record the story type | `set-story-type --project <ABS> --type A\|B\|C` |
| Write the fixed pages | `apply-fixed-pages --project <ABS>` |
| Generate art on the phone | `manual-dispatch --project <ABS> --asset page-05 [--out DIR]` |
| Make a folder an Obsidian vault | `init-vault --project <ABS>` |
| Refresh the studio vault | `build-vault` |
| User approved verified draft | `approve-final --project <ABS> --statement "…"` |
| Final | `build` + `verify` `--edition final` |

Prefer batch/parallel commands. Do **not** first-pass pages via sequential `generate-asset`.

### 1. Init

```bash
python3 $TOOLS/scripts/story_pipeline.py init --project <ABS_CLIENT> --pages <N>
```

### 2. Interview + start menus

Egyptian Arabic. Helpful guide — log to `input/interview.md`. Update `brief.json` + `requirements.md`.  
Multi-persona: confirm **real name + role + fixed outfit** for each discovered photo (filenames often garbage).  
On `ابدأ` / `start`: set the educational/entertainment goal, run
`list-templates --intent <mode>` + `list-themes`, show all ready options in that
branch, then fill gaps and continue. Confirm consent before images.

Ready-made path: family chooses the goal → confirm real
persona names/roles/outfits and target age → show the matching template list →
`apply-template` → optional
tailoring note. Theme from the full `list-themes` menu via `apply-theme`.
Do not make them rebuild the plot. `apply-template` writes the complete
client `story.json` reshaped to the 22+2 structure (two story slots left for
you to write); review note-affected pages and adapt all copy when
the source/target age profiles differ, run `review-story`, then
`complete-template-customization`, the Markdown review gate, and `lock-story`.
Cross-profile completion
requires every interior page and the total interior copy to reach the target
recommended ranges, not merely stay under hard maxima. Story lock intentionally
blocks while either note or age adaptation is pending.

Template gate/provenance state is mirrored in `story.json`, `brief.json`, and
`book.json`. Exact target age, source/target profile IDs, profile fields,
revision/adaptation flags, and timestamps must agree; never edit gate fields by
hand. Generated brief/story files use the canonical label
`language: "natural Egyptian Arabic"`.

Details: `$TOOLS/references/interview.md`

### 3. Story + mandatory human review

Write `input/story.json` — including `storyGoal`, `narrativeArc`, age-selected
`languageProfileId`, and the `locations[]` bible — → `review-story` → apply the
story semantic rubric to the text-only draft → revise until it passes → export
the Markdown storyboard → stop for user edits/approval → sync and lock.

```bash
python3 $TOOLS/scripts/story_pipeline.py review-story --project <ABS_CLIENT>
python3 $TOOLS/scripts/story_pipeline.py prepare-story-review --project <ABS_CLIENT>
# STOP. User reviews/edits input/story-review.md, then explicitly confirms.
python3 $TOOLS/scripts/story_pipeline.py approve-story-review \
  --project <ABS_CLIENT> --statement "راجعت كل الصفحات وموافق"
python3 $TOOLS/scripts/story_pipeline.py lock-story --project <ABS_CLIENT>
```

The client folder itself may be opened as an Obsidian vault. The review file
contains each page's exact text plus its scene description. Preserve its HTML
markers. Any later edit invalidates approval and blocks the rest of the flow.

### 4. Prompts + images (sheets → interior → covers last)

Write every prompt JSON in one pass, then:

```bash
python3 $TOOLS/scripts/story_pipeline.py compile-prompts --project <ABS_CLIENT>
python3 $TOOLS/scripts/story_pipeline.py validate-prompts --project <ABS_CLIENT>
```

`lock-story` registers one `location-sheet-NN` asset per declared location — write a prompt for each.

The semantic pass happens **before** images because it tests meaning, not only
field shape:

- Both routes: write the `because → therefore` chain; reject a removable
  "and then" page and any guest/adult-owned climax.
- Educational: show the bad pattern, its cost, a child-owned replacement
  choice, and later proof. When `habitFocus` exists, its exact
  `targetBehaviorAr` must appear on at least one `turn` page and one
  `reinforce` page.
- Entertainment: deliver the fantasy promise early, escalate obstacles, let
  the child own the decisive action, and pay off the stated wish. Do not smuggle
  in a lesson the family did not request.

Skeletons: `prompt-template.json` (pages), `character-sheet-template.json` (all personas), `location-sheet-template.json` (one per place).  
Fill rules: `prompt-fill-guide.md`.
Ready-made story catalog: `$TOOLS/references/story-templates/catalog.json`.

```bash
python3 $TOOLS/scripts/story_pipeline.py generate-book-images --project <ABS_CLIENT>
python3 $TOOLS/scripts/story_pipeline.py character-review --project <ABS_CLIENT> --accept
python3 $TOOLS/scripts/story_pipeline.py generate-book-images --project <ABS_CLIENT>
```

Character-sheet acceptance is always human. Never auto-accept likeness.

Refs per asset (order matters — Codex accepts only the first 8):

| Asset | Refs |
|---|---|
| `character-sheet` | all persona photos |
| `location-sheet-NN` | style refs only (no people) |
| story page | on-page persona photos → character-sheet → that page's location-sheet → style |
| `cover` / `back-cover` | as above + up to 2 finished interior pages |

Workers: `min(N,6)` — one parallel Codex dispatch per wave. Ref-heavy page jobs
starve each other above that: 20-way fan-out timed out 20/22 pages on a real run.
See `codex-imagegen` skill.

### 5. PDF + auto review

```bash
python3 $TOOLS/scripts/story_pipeline.py build --project <ABS_CLIENT> --edition draft
python3 $TOOLS/scripts/story_pipeline.py verify --project <ABS_CLIENT> --edition draft
```

Show draft PDF, then run rubrics **in parallel**:

- [references/reviews/story.md](references/reviews/story.md)
- [references/reviews/arabic.md](references/reviews/arabic.md)
- [references/reviews/continuity.md](references/reviews/continuity.md)
- [references/reviews/pdf.md](references/reviews/pdf.md)

Save under `output/reviews/` → `merge-reviews` → regenerate failed only → rebuild.  
Every reviewer JSON must copy the exact `draftSha256` and `storySha256`
returned by `verify`; stale reviews are rejected.
If an asset reaches the attempt limit, never edit `book.json`: use
`resolve-manual-review` with an explicit accept or a manually corrected image.
Full loop: [references/review-loop.md](references/review-loop.md)

### 6. Final

```bash
python3 $TOOLS/scripts/story_pipeline.py approve-final \
  --project <ABS_CLIENT> --statement "راجعت النسخة التجريبية وموافق"
python3 $TOOLS/scripts/story_pipeline.py build --project <ABS_CLIENT> --edition final
python3 $TOOLS/scripts/story_pipeline.py verify --project <ABS_CLIENT> --edition final
```

## Prompt rules

- Follow `$TOOLS/references/agent-core.md` + `prompt-fill-guide.md`
- **Never hand-write `compiledPrompt`** — fill structured fields, run `compile-prompts`
- Version bumps: `.v02.json` (never overwrite)
- **One orientation** for the whole book — landscape 16:9 always (handoff §8 I5)
- **Print-safe colour** (handoff §9) is added to every compiled prompt automatically and `validate-prompts` rejects a prompt without it — do not strip it, and do not write a palette that fights it
- **Full scene:** FG / MG / BG / lighting / props
- **Text-free art:** no writing anywhere in the image; the bottom band stays calm and empty. `build` draws the Arabic as a real, editable PDF text layer
- **Multi-persona:** per-persona `identityLocks` / `fixedOutfits` / `actionAndEmotion`; `spatialStaging` when 2+; no identity swap
- **Every page names a `locationId`** from the story's `locations[]`
- **Every non-cover page belongs to ordered `narrativeArc`**; the child owns `choice` and `decisiveAction`
- **Every story fulfills `storyGoal`**: educational proof or entertainment
  payoff, checked semantically before images
- **One arc owner per page**; the only exception is exactly two adjacent owners
  declared in canonical-order `combinedArcStages`; every page keeps a distinct `beat`
- **Visible bridges:** a location change or full cast replacement requires a
  time/cause/movement bridge inside current `page.text`; any
  `transitionFromPrevious` must appear there verbatim
- **Refrains:** values are normalized-unique and maximum 8 words. `age-1-2`
  allows at most two exact full-page refrains used on 2–18 pages; older profiles
  allow one short refrain inside advancing text on 2–4 pages, never a duplicate
  or near-duplicate full page; duplicate beats remain invalid
- **Protected wording:** page entries are registry-only
  `{"registryId":"…"}` references to
  `age-profiles.json.protectedPhraseRegistry`; never free-form strings or
  `{text,kind,source}` objects
- **Exact target age selects the dictionary** in `story-language/age-profiles.json`; no formal/Egyptian register mixing. Reject grammatical tanween; allow only `sharedEgyptian.lexicalizedTanweenWords` or central protected wording
- **Famous guests:** describe look only — never franchise names, Latin or Arabic (`list-guests`)
- Character sheet = all personas multi-view; location sheet = empty place, no people; pages = story `participants` only

## More schemas

- `$TOOLS/references/agent-core.md` ← **baked operating prompts**
- `$TOOLS/references/copyright-safe-guests.md` ← famous characters = describe, never name
- `$TOOLS/references/project-layout.md`
- `$TOOLS/references/brief-schema.md`
- `$TOOLS/references/story-schema.md`
- `$TOOLS/references/prompt-fill-guide.md`
- `$TOOLS/references/style-lock.md`

## Handoff

Return absolute client paths: final PDF, `story.json`, `prompts/`, review notes.
