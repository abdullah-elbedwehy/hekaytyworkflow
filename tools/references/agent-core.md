# Agent core prompts (baked)

Use this as the operating contract when running Hekayati. Do not invent a parallel flow.

## Mission

Build Arabic children's storybook in the **client** folder: identity/consent → exact age profile → ready-made template or custom interview → causally locked story → JSON prompts → Codex `$imagegen` → PDF → review → fix. Tools live in `hekaytyworkflow/tools/`. Never write client artifacts into tools.

## Be helpful (book start)

On `ابدأ` / `start` / new book: **proactively offer full menus** — do not wait for the family to ask.

1. Run `list-templates` + `list-themes` (live catalogs; never hard-code stale lists).
2. Show **every** ready-made adventure (Arabic title + one-line summary) **and** **every** art theme (`labelAr` / `label` + short look). Offer custom story as an extra option.
3. Guide next step clearly: confirm exact age → load `show-age-profile --age N` → pick template or custom → confirm names/roles/outfits → pick theme → consent → continue.

Details: `$TOOLS/references/interview.md`.

## Ready-made story route

Use `$TOOLS/references/story-templates/catalog.json` when the family wants to
choose instead of inventing a plot from scratch.

1. `list-templates` — show **all** catalog choices (Arabic titles + summaries).
2. `show-template --template ID` — preview the complete 20-page plan.
3. `apply-template --project … --template ID [--note "…"]` — personalize
   `{{hero}}`, map `hero` / `companions` / `all` participant slots, and write
   client `input/story.json`.
4. If a note is added, revise only affected beats. If the source and target age
   profiles differ, adapt the full page copy to the target profile as well. Run
   `review-story`, then `complete-template-customization`; `lock-story` blocks
   while either revision gate is pending. If neither gate is open, the story is
   ready.
5. Identity/outfit/age must already be confirmed before apply. Pick theme and
   confirm consent before image generation, then continue from `lock-story`.

`set-template-note` may add, replace, or clear the note before `lock-story`.
Never silently replace an existing story; `--force` is valid only before prompt
or image work. Catalog guests are original characters, not franchise copies.

Template state is workflow-owned and mirrored across `input/story.json`,
`input/brief.json`, and `output/book.json`. If one has `templateSelection`, all
three must have it and every selection field—including exact `targetAge`, source
and target language profiles, revision/adaptation flags, and completion
timestamps—must match. `story.languageProfileId`, `brief.languageProfileId`,
and `book.settings.languageProfileId` must all equal the selection's target
profile. Use template commands; never hand-edit these gate fields.

For cross-profile adaptation, every interior page must reach the target page
range and total interior words must reach the target recommended band. The
usual density warnings become blockers for `complete-template-customization`
and `lock-story`; staying under hard maxima is not completion.

## Parallel is law

| Work | How |
|---|---|
| Write prompts | Write **all** `input/prompts/*.json` in one pass (character-sheet + every location-sheet + every PDF page). Never page-by-page waiting. |
| Compile | One `compile-prompts` — the pipeline builds `compiledPrompt` from your fields |
| Validate | One `validate-prompts` after all files exist |
| Images | `generate-book-images` — sheets first, then interior pages in one parallel dispatch, then covers |
| Reviews | Run story / arabic / continuity / pdf rubrics **in parallel**, then `merge-reviews` |
| Fixes | Failed pages → bump prompt versions → `compile-prompts` → one parallel re-dispatch for failed ids only |

Never open N sequential Codex chats. Never `--sequential` unless user asks.

## Six locks that keep a book coherent

A book falls apart when any of these drift. All six are enforced by the pipeline — do not work around them.

| Lock | Owner | Enforced by |
|---|---|---|
| **Identity** — same face/outfit per person | `character-sheet` image + per-persona `identityLocks` / `fixedOutfits` | `validate-prompts`; sheet is a ref on every page |
| **Place** — same room/street every visit | `locations[]` bible + one `location-sheet-NN` image each | `lock-story`; the page's location sheet is a ref |
| **Shape** — one aspect ratio, whole book | `settings.orientation` (default `landscape`) | `validate-prompts` + `verify` reject off-ratio |
| **Prompt** — same structure, bounded length | `compile-prompts` builds `compiledPrompt` from fields | `load_prompt_payload` rejects over/under-length |
| **Language** — age-fit natural Egyptian, not mixed formal prose | `targetAge` → `languageProfileId` + age dictionary | `review-story`; `lock-story` blocks hard word/sentence/register failures |
| **Causality** — every beat changes the next beat | ordered `narrativeArc` + explicit bridge on hard scene cuts | `review-story`; `lock-story` blocks missing stages, gaps, jumps, or adult-owned climax |

### Age language profile (required)

`targetAge` is an exact integer from 1 to 8. Resolve it before writing a line:

```bash
python3 $TOOLS/scripts/story_pipeline.py list-age-profiles
python3 $TOOLS/scripts/story_pipeline.py show-age-profile --age <N>
```

Source: `$TOOLS/references/story-language/age-profiles.json`. Writing rules and
research: `$TOOLS/references/story-language/README.md`. The dictionary is a
curated starting set, not a claim that children may use only those words.

Generated `brief.json` and `story.json` always use the canonical label
`language: "natural Egyptian Arabic"`. Other accepted labels exist only for
import compatibility.

- 1–2: one visible action, repetition, concrete words, tiny safe arc.
- 3–5: one goal, short attempts, direct dialogue, visible choice and result.
- 6–8: richer cause/effect, setback and clue, decisive child action, more copy.
- Exact reviewed religious/scientific wording may stay formal only by selecting
  a registry entry: `protectedPhrases: [{"registryId":"…"}]`. The registry in
  `age-profiles.json.protectedPhraseRegistry` owns its exact text, kind, and
  source; page-level free-form strings or `{text,kind,source}` objects are
  invalid. The registered text must be visibly present in that page's text and
  explained immediately in simple Egyptian.
- Never mix narration registers accidentally. `ذهب/وجد/ماذا/سوف` are not
  Egyptian narration just because the rest of the page is Egyptian.
- Block grammatical tanween endings. Only fixed spoken words listed in
  `sharedEgyptian.lexicalizedTanweenWords` (for example `شكرًا`) bypass that
  check; quotations still use the central protected registry.

### Causal story spine (required)

Every `story.json` carries `narrativeArc`. Assign every non-cover page to one
ordered stage. A short page may carry two deliberate adjacent stages only when
its page object declares `combinedArcStages` exactly matching those owner stages
in canonical order; no page may sit outside the spine. Every page needs a
distinct `beat`. For every page ask:

1. What caused this page?
2. What does the child do now?
3. What visible state changes?
4. What new need forces the next page?

Deletion test: if removing a page changes nothing after it, cut it or give it a
real causal job. Never solve the climax with an unintroduced power, prop,
helper, dream reset, or adult decision. Whenever `locationId` changes **or** the
visible cast is fully replaced, put a meaningful time/cause/movement bridge of
at least three Arabic words inside the current page's visible `text`. Keeping
the hero does not excuse a place jump. `transitionFromPrevious` is optional; if
present, its full wording must appear verbatim in `page.text`.

Duplicate visible page text is blocking. Only `age-1-2` may repeat an exact
full page when it equals a declared `refrainPhrases` entry; older profiles may
repeat one short refrain inside advancing text but never duplicate or nearly
duplicate the whole page. Values are normalized-unique, at most 8 Arabic words,
and visibly used on 2–18 pages for `age-1-2` or 2–4 pages otherwise. A refrain
never exempts a repeated `beat`.

### Locations bible (required)

`story.json` carries `locations[]`. Every page names one with `locationId`.

```json
"locations": [
  {
    "id": "lantern-square",
    "nameAr": "ميدان الفوانيس",
    "visualDefinition": "A wide stone public square in a fantasy Arab city, ringed by three-storey sandstone buildings with carved wooden balconies, a low octagonal fountain of grey stone at the centre, rows of black iron lantern posts with clear glass panes, chipped grey flagstones, a mint-domed tower behind the north side."
  }
]
```

- 1–8 locations per book. A new place every page is exactly what makes a book look disconnected — reuse a few and change camera/time of day instead.
- `visualDefinition` ≥ 120 chars: architecture, materials, colors, and 2–3 fixed landmarks. Concrete enough to redraw from any angle.
- `pageCue`: one short line naming the place's two or three signature features.
- Every declared location must be used by at least one page; each costs one image.
- `lock-story` registers a `location-sheet-NN` asset per location. Write a prompt for each from `location-sheet-template.json`.

**Put the long definition in the sheet, not the pages.** The location-sheet
prompt gets the full `visualDefinition`. Page prompts get
`nameAr` + `pageCue` + "match the attached location reference sheet exactly for
architecture, materials and landmarks". Repeating the full definition on 22
pages overruns the compiled-prompt cap and pushes the identity locks and the
Arabic text block down the prompt, which is where models stop reading.

### `compiledPrompt` is compiled, not written

Fill the **structured fields** well. Then run `compile-prompts`. The pipeline assembles the string in a fixed priority order and bounds it, because image models weight the head of a prompt and drop the tail — hand-written prompts kept losing the Arabic text rules off the end.

Priority: header → identity locks → actions → guests → setting → layers → style → composition → **Arabic text** → palette → avoid. Sections are shed from the least important end if it runs long. Identity, setting, style and the Arabic text block are never dropped.

If `compile-prompts` errors that a prompt is too long, shorten the verbose field it names — do not raise the cap.

## Personalization mode (the family describes the child, not a plot)

A parent who says «بيقضم ضوافره لما يتوتر، وبيحب الديناصورات، ولازم بيت جدته
يظهر» has just given you a habit, a trait, and a place request. Do **not** bury
that in a free-text note — capture it:

```bash
python3 $TOOLS/scripts/story_pipeline.py set-personalization \
  --project <ABS> --json '{"habitFocus": {...}, "traits": [...], "requests": [...]}'
```

1. **One habit per book.** `habitFocus` owns the arc; extra habits are kept as
   `secondaryHabits` and get one visible beat each, not an arc. Say this to the
   family plainly instead of silently dropping the rest.
2. **Always get the replacement behaviour.** "يبطل قضم ضوافره" is not drawable —
   `targetBehaviorAr` must be what the child does instead.
3. **The story must prove it.** `lock-story` rejects a story whose
   `personalization.habitArc` is missing or out of order, or whose required
   requests have no `requestCoverage`. Write both while you write the pages.
4. **The child solves it.** The `turn` page is the child's own decision — never an
   adult, never magic. Shaming, punishment, and lecture pages are auto-added to
   `avoid`.
5. **Template route:** personalization flips `requiresRevision` back on. Tailor
   the affected beats, then `complete-template-customization` → `lock-story`.

Full contract: `$TOOLS/references/personalization.md`.

## Multi-persona contract

1. Discover every image under `personas/` (or project root). Each = `persona-01…N`.
2. Interview: get **real Arabic display names + roles + fixed outfits** for every persona (filenames may be garbage).
3. `story.json` pages list exact `participants` ids for that beat — subset OK; never invent people.
4. **character-sheet** prompt: **all** personas, multi-view each, separate, same outfits forever.
5. **Page** prompts: only people in `participants` (+ guests if any). Per-persona `identityLocks`, `fixedOutfits`, `actionAndEmotion`.
6. Refs passed to `$imagegen`:
   - character-sheet → all persona photos
   - page → only on-page persona photos + accepted character-sheet + style refs
7. Continuity: same face/outfit/props across pages; never swap identities between personas.

## Smart function routing

Call pipeline only with absolute `--project`. Pick command by state:

| State | Call |
|---|---|
| New client folder / book start | `init` → `list-templates` + `list-themes` → show full menus |
| Family describes the child (habit, trait, "لازم يظهر …") | `set-personalization --project … --json '{…}'` |
| Check what was captured | `show-personalization --project …` |
| Family wants a ready-made story | `list-templates` → `apply-template --project … --template ID [--note …]` |
| Template selected, note changes | `set-template-note --project … --note …` |
| Template note and/or age adaptation incorporated | `review-story` → `complete-template-customization --project …` |
| Browse art themes | `list-themes` |
| Pick art theme | `apply-theme --project … --theme <themeId>` |
| Missing custom story | write `input/story.json` (incl. `locations[]`) → `lock-story` |
| Need the age voice / dictionary | `show-age-profile --age N` |
| Story draft written or edited | `review-story --project …` → fix every error → `lock-story` |
| Ready-made `story.json` reviewed | `lock-story` |
| Family asks for a famous character | `list-guests` → `show-guest --guest <key>` → paste `appearanceNotes` |
| Prompts missing / rewritten | write all JSON → `compile-prompts` → `validate-prompts` |
| Prompts valid, no sheet image | `generate-book-images` |
| Sheet awaiting review | show image → `character-review --accept` (or reject + new prompt version) |
| Sheet accepted | `generate-book-images` — location sheets, then interior, then covers |
| All images ready | `build --edition draft` → `verify` |
| Draft ready | run 4 review rubrics in parallel → `merge-reviews` |
| Fix queue | rewrite failed prompts `.v0N` → `compile-prompts` → validate → regenerate failed only → rebuild |
| User says تمام | `build --edition final` → `verify` |

Do **not** call `begin-asset` / `generate-asset` one-by-one for first-pass pages. Prefer `generate-book-images` / `generate-pages-parallel` / `generate-batch`.

## Baked prompt quality (every page JSON)

### Scene (must be drawable)

Fill all layers: `place`, `timeOfDay`, `atmosphere`, `lighting`, `foreground`, `midground`, `background`, `propsInFrame[]`, `backdropDetails`. Concrete materials/colors. No vague one-liners.

### Multi-person staging

When 2+ participants on page:
- State spatial relation (who left/right/front, who touches whom)
- One shared action beat; per-person pose + emotion
- Clear face visibility for every on-page persona
- No identity mix (name A must match photo A)

### Text blend

Exact Arabic from `story.json` once, RTL, connected, legible. Blend **inside** the art using the active theme’s `textBlendHint` (storybook: soft painted caption / sky wash; cartoony: soft 3D-integrated caption band). Never hard white box, sticker, or speech bubble (unless story asks). Quiet zone away from faces.

### Copyright-safe famous characters

Naming a franchise character gets the image **refused** — the job fails and the page comes back empty. Describing the look works fine. This is tested: an identical scene generated cleanly with a described guest and was refused when the character was named.

1. `list-guests` → find the archetype matching what the family asked for.
2. `show-guest --guest <key>` → paste `appearanceNotes` **verbatim** into `story.json` `guestCharacters[]` and each page's `guests[]`.
3. Never write the franchise name in **any** image-bound field. `validate-prompts` scans `compiledPrompt`, `narrativeBeat`, `primaryRequest`, `spatialStaging`, `palette`, every `scene.*` field, `propsInFrame[]`, participant/guest `displayName`, `identityLocks.*` and `actionAndEmotion.*` — in Latin **and Arabic** (`سبايدر مان`, `إلسا`, `ميكي ماوس`, …).
4. A thin guest description (< 120 chars) is rejected: vagueness is what makes the model reach for the franchise it recognizes.

Library: `$TOOLS/references/guests/catalog.json`. Rules: `$TOOLS/references/copyright-safe-guests.md`.

Ready-made/public catalog entries use original guest characters only. If a user
requests a franchise by name, convert it into an original archetype before it
enters reusable catalog or image-prompt text.

### `compiledPrompt`

**Do not hand-write it.** Fill the structured fields, run `compile-prompts`, and the pipeline assembles it. See "Six locks" above.

## Art themes

`$TOOLS/references/themes/catalog.json` — offer **all** via `list-themes`:

| `themeId` | Look |
|---|---|
| `storybook` (default) | ستوري بوك رسمة — painterly whimsical |
| `cartoony` | كرتوني ثلاثي الأبعاد — stylized 3D CGI |
| `fairytale-glow` | توهج الحكايات — soft fairy-tale animation |
| `feature-cgi` | ثلاثي أبعاد سينمائي — feature-film 3D CGI |
| `enchanted-glow` | توهج ساحر — night fairy-tale 3D glow |
| `wonder-trail` | درب العجائب — vibrant painterly adventure |

Interview picks `themeId`; `apply-theme` syncs brief/story + style refs. See `style-lock.md`.

## Hard bans

- Gemini / OpenAI Images API / key CSVs
- Client artifacts inside `hekaytyworkflow/`
- Overwriting prompt versions (bump `.v02`, `.v03`…)
- Generating pages before character-sheet accepted (unless `--auto-accept-character`)
- Generating pages before every location sheet exists
- Generating covers before the interior is finished
- Franchise names in any image-bound field, Latin or Arabic
- Mixing orientations inside one book
- Extra people not in participants/guests
- Thin scenes / boxed text
- Story copy written before selecting the exact age profile
- Missing/gapped `narrativeArc`, repeated `فجأة` as transition glue, or an unbridged hard scene cut
- Multiple arc owners without exact `combinedArcStages`, repeated beats, or
  undeclared duplicate visible page text
- Free-form protected strings/objects; select reviewed registry IDs only
- Formal case endings in Egyptian narration; exact protected quotations are the exception

## Templates to copy

- Personalization (habits / traits / must-appear requests): `$TOOLS/references/personalization.md`
- Age dictionaries + narration contracts: `$TOOLS/references/story-language/age-profiles.json`
- Writing/research guide: `$TOOLS/references/story-language/README.md`
- Ready-made stories: `$TOOLS/references/story-templates/catalog.json`
- Pages: `$TOOLS/references/prompt-template.json`
- Character sheet: `$TOOLS/references/character-sheet-template.json`
- Location sheet: `$TOOLS/references/location-sheet-template.json`
- Safe guests: `$TOOLS/references/guests/catalog.json`
- Fill rules: `$TOOLS/references/prompt-fill-guide.md`
