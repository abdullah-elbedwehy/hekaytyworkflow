---
name: hekayati
description: >-
  Cursor entry for Hekayati Arabic children's books. Multi-persona OK. On ابدأ /
  start, offer ALL story-templates + ALL art themes (list-templates +
  list-themes), or custom interview. Then story, JSON prompts folder (write all
  in parallel), Codex $imagegen via generate-book-images (character then all
  pages parallel), draft PDF, auto review rubrics, iterate. Client folder holds
  all artifacts; tools/ is scripts only. Use when user points at a
  persona/client folder or says ابدأ / Hekayati / حكايتي.
---

# Hekayati (Cursor)

**Read first:** `$TOOLS/references/agent-core.md` (baked parallel + multi-persona + routing).

## Hard rules

| Location | Role |
|---|---|
| `hekaytyworkflow/tools/` | Scripts + schemas only |
| Client project | **All** run data (`input/` + `output/`) |
| `.cursor/skills/codex-imagegen` | Image dispatch (Codex `$imagegen` only) |

- Never write client artifacts into `hekaytyworkflow/`.
- Never Gemini API / OpenAI Images API / key CSVs.
- Images only via Codex `$imagegen` (`generate-book-images` / `codex-imagegen`).
- **Parallel by default** — all prompts in one pass; all pages in one Codex dispatch; reviews in parallel.

```text
<client>/
  personas/*.png          # 1..N people (multi-persona supported)
  input/{interview.md,requirements.md,brief.json,story.json,prompts/*.json}
  output/{book.json,images/,pdf/,reviews/}
```

`TOOLS` = absolute path to `hekaytyworkflow/tools`.

## Flow

```text
1) init + identities; BOOK START MENU = list-templates + list-themes (show ALL)
2) pick ready-made template OR custom; pick art theme; consent
3) load exact age profile; ready-made: apply-template (+ optional note/age adaptation) → review-story → complete-template-customization → lock-story
   custom: write story.json (incl. narrativeArc + locations[] bible) → review-story → lock-story
4) write ALL input/prompts/ in one pass (character-sheet + location-sheets + every page)
5) compile-prompts → validate-prompts
6) generate-book-images: sheet → accept → location sheets → interior pages → covers LAST
7) build + verify draft → show PDF
8) auto reviews (4 rubrics parallel) + merge-reviews
9) fix loop until تمام → final PDF
```

**Six locks** (see `agent-core.md`): identity · place · shape · prompt · age language · causal story spine.

### Personalization mode

When the family describes the child instead of a plot — a habit, things they
love, "لازم بيت جدته يظهر" — run `set-personalization`. One habit per book owns
the arc (setup → challenge → turn → reinforce, the child decides on `turn`);
extra habits and traits become small beats; must-appear requests become
locations and recurring props. `lock-story` blocks until `story.personalization`
carries `habitArc` + `requestCoverage`. Contract: `$TOOLS/references/personalization.md`.

### Be helpful (book start)

On `ابدأ` / `start` / new book: **surface full menus immediately** — warm Egyptian Arabic, clear next steps, no digging.

```bash
python3 $TOOLS/scripts/story_pipeline.py list-templates
python3 $TOOLS/scripts/story_pipeline.py list-themes
```

Show **every** story template (Arabic title + one-line summary) and **every** art theme (`labelAr` + short look). Offer **قصة مخصوص** as an option. Then confirm names/roles/outfits/age and apply choices.

### Smart function map

| Need | Command |
|---|---|
| First Mac machine | `setup` then `codex login` (check: `doctor`) |
| New project | `init --project <ABS> --pages N` |
| Family described the child (عادة / صفة / لازم يظهر) | `set-personalization --project <ABS> --json '{…}'` |
| Review what was captured | `show-personalization --project <ABS>` |
| Browse ready-made stories | `list-templates` / `show-template --template ID` |
| Choose ready-made story | `apply-template --project <ABS> --template ID [--note …]` |
| Change template note before lock | `set-template-note --project <ABS> --note …` |
| Note incorporated in pages | `complete-template-customization --project <ABS>` |
| Story ready | `lock-story --project <ABS>` |
| Exact age voice/dictionary | `show-age-profile --age N` |
| Story wording/causality QA | `review-story --project <ABS>` |
| Browse art themes | `list-themes` |
| Art theme | `apply-theme --project <ABS> --theme <themeId>` |
| Famous character asked for | `list-guests` / `show-guest --guest <key>` |
| Prompts written | `compile-prompts --project <ABS>` then `validate-prompts --project <ABS>` |
| Images | `generate-book-images --project <ABS>` |
| Accept sheet | `character-review --project <ABS> --accept` |
| Uninterrupted | `generate-book-images --project <ABS> --auto-accept-character` |
| Draft PDF | `build` + `verify` `--edition draft` |
| Merge reviews | `merge-reviews --project <ABS>` |
| Final | `build` + `verify` `--edition final` |

Prefer batch/parallel commands. Do **not** first-pass pages via sequential `generate-asset`.

### 1. Init

```bash
python3 $TOOLS/scripts/story_pipeline.py init --project <ABS_CLIENT> --pages <N>
```

### 2. Interview + start menus

Egyptian Arabic. Helpful guide — log to `input/interview.md`. Update `brief.json` + `requirements.md`.  
Multi-persona: confirm **real name + role + fixed outfit** for each discovered photo (filenames often garbage).  
On `ابدأ` / `start`: run `list-templates` + `list-themes`, show **all** options, then fill gaps and continue. Confirm consent before images.

Ready-made path: family picks from the full template list → confirm real
persona names/roles/outfits and target age → `apply-template` → optional
tailoring note. Theme from the full `list-themes` menu via `apply-theme`.
Do not make them rebuild the plot. `apply-template` writes the complete
20-page client `story.json`; review note-affected pages and adapt all copy when
the source/target age profiles differ, run `review-story`, then
`complete-template-customization` and `lock-story`. Cross-profile completion
requires every interior page and the total interior copy to reach the target
recommended ranges, not merely stay under hard maxima. Story lock intentionally
blocks while either note or age adaptation is pending.

Template gate/provenance state is mirrored in `story.json`, `brief.json`, and
`book.json`. Exact target age, source/target profile IDs, profile fields,
revision/adaptation flags, and timestamps must agree; never edit gate fields by
hand. Generated brief/story files use the canonical label
`language: "natural Egyptian Arabic"`.

Details: `$TOOLS/references/interview.md`

### 3. Story + prompts (parallel write)

Write `input/story.json` — including `narrativeArc`, age-selected `languageProfileId`, and the `locations[]` bible — → `review-story` → lock → **all** JSON under `input/prompts/` from templates (one pass) → compile → validate.

```bash
python3 $TOOLS/scripts/story_pipeline.py review-story --project <ABS_CLIENT>
python3 $TOOLS/scripts/story_pipeline.py lock-story --project <ABS_CLIENT>
python3 $TOOLS/scripts/story_pipeline.py compile-prompts --project <ABS_CLIENT>
python3 $TOOLS/scripts/story_pipeline.py validate-prompts --project <ABS_CLIENT>
```

`lock-story` registers one `location-sheet-NN` asset per declared location — write a prompt for each.

Skeletons: `prompt-template.json` (pages), `character-sheet-template.json` (all personas), `location-sheet-template.json` (one per place).  
Fill rules: `prompt-fill-guide.md`.
Ready-made story catalog: `$TOOLS/references/story-templates/catalog.json`.

### 4. Images (sheets → interior → covers last)

```bash
python3 $TOOLS/scripts/story_pipeline.py generate-book-images --project <ABS_CLIENT>
python3 $TOOLS/scripts/story_pipeline.py character-review --project <ABS_CLIENT> --accept
python3 $TOOLS/scripts/story_pipeline.py generate-book-images --project <ABS_CLIENT>
```

Uninterrupted: `--auto-accept-character`.

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
Full loop: [references/review-loop.md](references/review-loop.md)

### 6. Final

```bash
python3 $TOOLS/scripts/story_pipeline.py build --project <ABS_CLIENT> --edition final
python3 $TOOLS/scripts/story_pipeline.py verify --project <ABS_CLIENT> --edition final
```

## Prompt rules

- Follow `$TOOLS/references/agent-core.md` + `prompt-fill-guide.md`
- **Never hand-write `compiledPrompt`** — fill structured fields, run `compile-prompts`
- Version bumps: `.v02.json` (never overwrite)
- **One orientation** for the whole book (`settings.orientation`, default landscape)
- **Full scene:** FG / MG / BG / lighting / props
- **Blended text:** Arabic inside art; never hard white box
- **Multi-persona:** per-persona `identityLocks` / `fixedOutfits` / `actionAndEmotion`; `spatialStaging` when 2+; no identity swap
- **Every page names a `locationId`** from the story's `locations[]`
- **Every non-cover page belongs to ordered `narrativeArc`**; the child owns `choice` and `decisiveAction`
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
