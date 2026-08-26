# Prompt fill guide

Copy `prompt-template.json` → `input/prompts/<assetId>.v0N.json`.  
Read `$TOOLS/references/agent-core.md` first (parallel + multi-persona + routing),
then **[prompt-rules.md](prompt-rules.md)** — the ultra-detail contract, with the
word floors and banned vocabulary that `validate-prompts` enforces mechanically.

This file says *which field goes where*. `prompt-rules.md` says *how specific
each field has to be*, and the pipeline blocks on it.

## You fill fields; the pipeline writes the prompt

`compiledPrompt` is **generated** by `compile-prompts` from the structured fields.
Do not hand-write it. Your job is to make every field concrete — the quality of
the image is now entirely a function of how well the fields are filled.

```bash
python3 $TOOLS/scripts/story_pipeline.py compile-prompts --project <ABS>
python3 $TOOLS/scripts/story_pipeline.py validate-prompts --project <ABS>
```

The compiler orders sections by importance and bounds the total length, because
image models weight the head of a prompt and drop the tail. If it reports the
prompt is over the cap, shorten the field it names.

## Parallel write rule

After `lock-story`, write **every** prompt file in one pass:

1. `character-sheet.v01.json` (all personas)
2. `location-sheet-01.v01.json` … one per declared location (empty place, no people)
3. `cover.v01.json` … `back-cover.v01.json` (all PDF pages)

Then one `compile-prompts`, then one `validate-prompts`. Never drip prompts page-by-page before generate.

## Quality bar (non-negotiable, and mechanically enforced)

`validate-prompts` scores every prompt 0-100 and blocks below **80** for pages,
**70** for sheets. It names the exact field and what it is missing. Full rules
and the word floors: [prompt-rules.md](prompt-rules.md).

0. **Depth score** — no CHANGE stubs, no filler words, every field over its word
   floor, every prop carrying a colour plus a material or a state.

1. **Scene depth** — FG + MG + BG + lighting + props, all concrete.
2. **Place lock** — every page carries the `locationId` its story page declares.
3. **Caption room** — text-free art leaves a calm bottom safe zone; `build` adds
   the exact Arabic later as a real PDF text layer. Never draw a box or caption.
4. **Multi-persona fidelity** — each on-page person matches **their** photo + outfit; no face swap.
5. **One orientation** — `composition.orientation` equals the book setting on every asset.
6. **Copyright-safe guests** — famous characters = detailed visual description only; **never** their real name, Latin or Arabic (`list-guests`).

Reject thin fills. Expand until a stranger could draw the page from the JSON alone.

## Keep every run (template constants)

- `schemaVersion`
- `useCase`
- `style.medium` / `style.finish` — paste from `$TOOLS/references/themes/catalog.json` for `brief.themeId` (same on every page; `immutable: true` = lock after theme chosen, not “always storybook”)
- `composition.captionSafeZone` (tune the quiet-band wording per theme `textSafeZoneHint`)
- `constraints` list
- `avoid` list (+ theme `avoidExtras`)
- `composition.orientation` = the book setting (default `landscape`) — identical on every asset

## Theme resolution (required)

1. Read `input/brief.json` → `themeId` (default `storybook`).
2. Load `$TOOLS/references/themes/catalog.json` → that theme.
3. Paste `style.medium` / `style.finish` into every prompt (sheet + pages).
4. The compiler pulls the style block from `style.medium` / `style.finish` — just paste them correctly.
5. Caption band: use theme `textSafeZoneHint` (cartoony = smooth out-of-focus 3D floor, not a painterly wash).
6. If theme has `styleRefDir` and `input/style/` empty: run `apply-theme --theme <themeId>` (or copy `themes/<id>/ref-*.png`).

| themeId | Fingerprint (must appear in `style.medium`) |
|---------|---------------------------------------------|
| `storybook` | `premium whimsical children's storybook digital illustration` |
| `cartoony` | `stylized 3D CGI children's animation` |

Cartoony style block example:

> stylized 3D CGI children's animation, smooth clean surfaces, large expressive glassy eyes with catchlights, stylized hair clumps, vibrant saturated color, soft cinematic sunlight, shallow depth of field, print-ready; match style reference images; NOT photoreal, NOT flat 2D clipart

No studio brand names in `$imagegen` prompts.


## Lock once, then paste verbatim every page

- `fixedOutfits.<personaId>` for **every** persona
- `identityLocks.<personaId>.*` for **every** persona
- `palette` (base)
- all persona photo paths (use subset in `inputImages` per page)
- accepted character-sheet path after gate

## Multi-persona rules

| Asset | Who appears | Refs `$imagegen` gets |
|---|---|---|
| `character-sheet` | **All** personas | All persona photos |
| `location-sheet-NN` | **Nobody** — empty place | Style refs only |
| Story page | Only `participants` with `onPage: true` (+ guests) | Those personas' photos → character-sheet → the page's location-sheet → style |
| `cover` / `back-cover` | Usually everyone | As above + up to 2 finished interior pages |

Codex accepts only the first **8** refs, so that order is load-bearing: identity
and place locks come first, style refs are what get trimmed.

### Per page checklist (2+ people)

- `participants` ids match `story.json` for that page
- `inputImages` includes only those persona photos (+ sheet)
- `identityLocks` + `fixedOutfits` + `actionAndEmotion` keyed by **each** on-page personaId
- `spatialStaging` states left/right/front and contact
- `compile-prompts` adds the no-identity-swap rule automatically once 2+ people are on the page
- Cover/group beats may include everyone; quiet beats may be solo — still lock outfits for returnees via continuity

## Copyright-safe famous characters

If story has Spider-Man, Elsa, Batman, etc.:

1. Run `list-guests` and pick the archetype matching what the family asked for.
2. `show-guest --guest <key>` → paste `appearanceNotes` **verbatim** into `guests[]` (not `personas`).
3. Never write the franchise name in any field — Latin or Arabic. `validate-prompts` scans them all.
4. The story/PDF caption may use a kid-friendly alias; generated art stays
   text-free and its prompt stays nameless.
5. Descriptions under 120 chars are rejected — vagueness is what triggers a refusal.

Library: `$TOOLS/references/guests/catalog.json`. Rules: `$TOOLS/references/copyright-safe-guests.md`.

**Bad:** `Spider-Man swings in` / `سبايدر مان بيتسلق`  
**Good:** `an athletic young adult rooftop rescuer in a deep-plum and mint suit with gold thread over the shoulders, full soft-cloth mask with two large amber lenses, coil of golden rope at the hip, swings in`

Both bad forms are rejected by `validate-prompts`, and both would be refused by the image model.

### Character sheet checklist

- One sheet, every persona
- Per persona: face close-up, front, three-quarter, side, full-body
- Separate zones, no labels/text, hands+shoes clear
- Outfits = locked forever

## Change per page only

| Field | Why |
|---|---|
| `assetId` / `version` | file identity |
| `narrativeBeat` | causal progress |
| `primaryRequest` | one drawable group action |
| `participants` / `guests` | who appears |
| `inputImages` | only on-page persona photos + sheet |
| `spatialStaging` | multi-person layout |
| `scene.*` | full place description (all layers) |
| `actionAndEmotion.*` | pose + feeling per person |
| `composition.shotScale` | must differ from adjacent — **enforced**: two adjacent pages sharing scale *and* viewpoint fail validation |
| `composition.viewpoint` | must differ from adjacent — see above |
| `composition.lens` | lens feel, e.g. `35mm-equivalent, slight wide, no edge distortion` |
| `composition.depthOfField` | what stays sharp, what falls soft |
| `colorScript` | how this beat leans the locked palette — never a new palette |
| `composition.captionSafeZone` | how the reserved quiet band reads in this theme |
| `continuity.fromPreviousPage` | carried state per returning person |
| `locationId` | which location-sheet gets attached as a reference |

## Scene writing rules

| Field | Require |
|---|---|
| `place` | Named spot + architecture/nature type |
| `timeOfDay` | Light hour + temperature (warm gold / cool blue) |
| `atmosphere` | Mood + weather + air |
| `lighting` | Key direction, color, shadow softness, rim/fill |
| `foreground` | Near objects: material, color, relative size |
| `midground` | Action stage |
| `background` | Depth layer |
| `propsInFrame` | Every visible prop with color + material + state |
| `backdropDetails` | 3–6 sensory bits |

**Good:** layered porch / doorway / street with materials  
**Bad:** `backdropDetails: home doorway morning light`

## Caption safe-zone rules

The Arabic is **not** in the image. `build` draws it as a real PDF text layer,
so the art only has to leave room for it.

Do: keep the bottom band calm and low-detail per the theme's `textSafeZoneHint`
— no faces, hands, or key action there.
Do not: any text, letters, numbers, captions, or signage anywhere in the frame;
any drawn box, band, or panel under the caption area. `validate-prompts` fails a
page prompt that omits the text-free clause, or that pastes the story text into
the art prompt.

## `compiledPrompt` assembly (done for you)

`compile-prompts` builds the string in this fixed order, dropping the least
important sections first if it runs long:

1. asset type + orientation + beat + primary request
2. per-persona identity locks + fixed outfits
3. staging + explicit no-identity-swap rule (2+ people)
4. per-persona action + emotion
5. guest descriptions
6. setting (place / time / lighting), then FG / MG / BG layers, then props
7. style block from the theme catalog
8. composition — scale, viewpoint, focal hierarchy, lens, depth of field
9. **text-free clause** — the art carries no text at all; the caption is a PDF layer
10. palette, colour script, carried continuity
11. avoid list

Sections 1, 2, 3, 4, 6-setting, 7 and 9 are never dropped. The avoid list goes
first, then palette/continuity, then props, then layers/composition.

Save JSON under the **client** `input/prompts/` folder only.
