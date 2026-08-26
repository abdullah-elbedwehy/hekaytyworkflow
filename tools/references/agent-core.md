# Agent core prompts (baked)

Use this as the operating contract when running Hekayati. Do not invent a parallel flow.

> **The source of truth is [`handoff.md`](handoff.md).** This file is downstream
> of it. If anything here contradicts the handoff, follow the handoff and fix
> this file. Machine-readable: [`handoff/doctrine.json`](handoff/doctrine.json).
> Enforcement map: [`handoff-enforcement.md`](handoff-enforcement.md).
> Read the rulebook with `show-doctrine`; check one story against it with
> `check-doctrine --project <ABS>`.

## Mission

Build Arabic children's storybook in the **client** folder: identity/consent →
educational-or-entertainment goal → exact age profile → matching ready-made
template or custom interview → deterministic/semantic QA → user-edited Markdown
storyboard approval → locked story → JSON prompts → Codex `$imagegen` → PDF →
review → fix. Tools live in
`hekaytyworkflow/tools/`. Never write client artifacts into tools.

## Be helpful (book start)

On `ابدأ` / `start` / new book: **ask the goal before the plot menu**.

1. Ask: `تحب القصة تساعد في سلوك/قيمة، ولا تبقى مغامرة للتسلية؟`
2. Run `set-story-goal --mode educational|entertainment --goal "…"`.
3. Run `list-templates --intent <mode>` + `list-themes` (live catalogs; never
   hard-code stale lists).
4. Show **every ready** template in that branch (Arabic title + one-line
   summary) and **every** art theme. Offer custom story too. Never show a
   `needs-revision` template as a usable client choice.
5. Confirm exact age → load `show-age-profile --age N` → pick template or
   custom → confirm names/roles/outfits → pick theme → consent → continue.

Details: `$TOOLS/references/interview.md`.

## Ready-made story route

Use `$TOOLS/references/story-templates/catalog.json` when the family wants to
choose instead of inventing a plot from scratch.

1. `list-templates --intent <chosen-mode>` — show all ready choices in the
   already selected branch.
2. `show-template --template ID` — preview the source plan. Applying it
   reshapes it into the 22+2 book and opens two story slots to write.
3. `apply-template --project … --template ID [--note "…"]` — personalize
   `{{hero}}`, map `hero` / `companions` / `all` participant slots, and write
   client `input/story.json`.
4. Confirm that `template.storyIntent == brief.storyGoal.mode`. If a note is
   added, revise only affected beats. If the source and target age
   profiles differ, adapt the full page copy to the target profile as well. Run
   `review-story`, then apply the semantic story rubric to the text-only story,
   then `complete-template-customization`. Export the Markdown storyboard and
   stop for the user's review; `lock-story` blocks
   while either revision gate is pending. If neither gate is open, the story is
   ready.
5. Identity/outfit/age must already be confirmed before apply. Pick theme,
   confirm consent, and complete the permanent story-review gate before image
   generation; only then continue from `lock-story`.

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

## Permanent human story-review gate

This gate runs for every book, ready-made or custom. It is not optional and is
never replaced by the agent's deterministic or semantic QA.

1. Finish `review-story` and the semantic rubric; fix all blockers.
2. Run `prepare-story-review --project <ABS>`. This writes
   `input/story-review.md` with every page's exact text and scene description.
3. **Stop.** Show the absolute file path. The client folder can be opened as an
   Obsidian vault. The user may edit visible fields but must keep the HTML
   page/field marker comments.
4. When the user says they finished, re-read the file and run
   `story-review-status`; do not rely on an earlier in-memory draft.
5. Run `approve-story-review --project <ABS> --statement "…"`. It parses the
   reviewed Markdown, syncs approved edits into `story.json`, reruns story QA,
   and records content hashes.
6. Only then run `lock-story`, prompts, images, or PDF commands.

Never overwrite an existing review file unless the user deliberately asks for
a fresh export. Any edit to `story.json` or `story-review.md` after approval
makes the approval stale and returns the workflow to this gate.

## Parallel is law

| Work | How |
|---|---|
| Write prompts | Write **all** `input/prompts/*.json` in one pass (character-sheet + every location-sheet + every PDF page). Never page-by-page waiting. |
| Human story gate | `prepare-story-review` → stop for user edits in `input/story-review.md` → `approve-story-review` → `lock-story` |
| Compile | One `compile-prompts` — the pipeline builds `compiledPrompt` from your fields |
| Gate | One `preflight` — environment + story + compile + validation in a single verdict |
| Images | `generate-book-images` — three waves, see below |
| Reviews | Run story / arabic / continuity / pdf rubrics **in parallel**, then `merge-reviews` |
| Fixes | Failed pages → bump prompt versions → `compile-prompts` → one parallel re-dispatch for failed ids only |

Never open N sequential Codex chats. Never `--sequential` unless user asks.

### The three image waves

```text
wave A   character-sheet + EVERY location-sheet   ← one dispatch, together
         ↓ (accept gate on the sheet only)
wave B   all interior pages                        ← one dispatch
         ↓
wave C   cover + back-cover                        ← last, so they match finished art
```

Wave A renders the sheets **together** on purpose. A location sheet is the empty
place — no people in it — so it shares no identity state with the character
sheet and nothing about it depends on the sheet being approved. Splitting them
cost a whole dispatch round plus the family's thinking time while five of six
render lanes sat idle. If the sheet is rejected, only the sheet is redrawn; the
places are still good.

Jobs that come back empty are **retried inside the wave** (`--retries`, default
1) instead of being handed back as a one-page fix task. Do not manually retry a
page until the wave itself reports it failed twice.

### Report progress, every time

Every command that touches a project returns a `progress` block. After each
long step, tell the family the number — do not invent your own estimate:

```bash
python3 $TOOLS/scripts/story_pipeline.py progress --project <ABS>
```

Paste `progress.messageAr` as-is. It already carries the percent in
Arabic-Indic numerals, the current phase, the page counter, and the remaining
time estimated from **this** machine's measured render times.

## The book is 22 interior pages + 2 separate covers (handoff §7)

| Asset | Role |
|---|---|
| `cover` | front cover, outside the 22 |
| `page-01` | الإهداء — fixed text, `{{hero}}` substituted |
| `page-02` … `page-21` | the story — **exactly 20 pages** |
| `page-22` | «قصص تانية» — 3 RTL rows, fixed layout |
| `back-cover` | back cover, fixed marketing copy + 5 mandatory icons |

`settings.pdfPageCount = 24`, `settings.bookStructure = "hekayati-22"`.

The dedication, «قصص تانية», and back-cover copy belong to the doctrine. Write
them with `apply-fixed-pages --project <ABS>`; rewriting them by hand is a
blocking error. They are excluded from the age word budget and from the causal
spine on purpose.

**Merge rule.** A first draft usually runs long. Merge adjacent events down to
exactly 20 story pages *before* any image prompt — the merge itself can be the
bridge. A ready-made template is two pages short of this shape, so applying one
opens `page-20` and `page-21` as declared holes; the pipeline refuses to invent
them, because inventing them is exactly the «مشهد حشو» handoff §3 N3 forbids.

## Story type is chosen before the plot (handoff §5)

| Type | Use | `storyGoal.mode` | Cast rule |
|---|---|---|---|
| **A** | تصحيح سلوك داخلي (خوف، غيرة، غضب) | `educational` | magical companion **required**; a `setback` (انتكاسة) beat is required before the fix |
| **B** | تشجيع على مكان (مدرسة، حضانة، دكتور) | `educational` | real friends only — **no** magical companion; side friends share the hero's gender |
| **C** | مغامرة خيالية | `entertainment` | original characters only; the child owns the decisive action |

```bash
python3 $TOOLS/scripts/story_pipeline.py set-story-type --project <ABS> --type A
```

## Language rules that outrank everything (handoff §2)

1. **No literary metaphor for an inner feeling.** Not «حد سرق مكانه», not «قلبه بقى أكبر», not «التقيلة في صدره خفت». Say what the child actually thinks: «حد أخد مكانه وحب بابا وماما منه».
2. **Resolve the emotional crisis with a concrete event** — a gift arriving, a hug, playing together — never an abstract inner shift.
3. **Reassurance is plain and warm, never a proverb.**

`review-story` blocks on these. It folds diacritics and hamza first, so a
vowelled spelling does not slip through.

## Seven locks that keep a book coherent

A book falls apart when any of these drift. Deterministic locks are enforced by
the pipeline; the semantic goal lock also requires the pre-image story rubric.
Do not work around either.

| Lock | Owner | Enforced by |
|---|---|---|
| **Identity** — same face/outfit per person | `character-sheet` image + per-persona `identityLocks` / `fixedOutfits` | `validate-prompts`; sheet is a ref on every page |
| **Place** — same room/street every visit | `locations[]` bible + one `location-sheet-NN` image each | `lock-story`; the page's location sheet is a ref |
| **Shape** — one aspect ratio, whole book | `settings.orientation` (default `landscape`) | `validate-prompts` + `verify` reject off-ratio |
| **Prompt** — same structure, bounded length | `compile-prompts` builds `compiledPrompt` from fields | `load_prompt_payload` rejects over/under-length |
| **Language** — age-fit natural Egyptian, not mixed formal prose | `targetAge` → `languageProfileId` + age dictionary | `review-story`; `lock-story` blocks hard word/sentence/register failures |
| **Causality** — every beat changes the next beat | ordered `narrativeArc` + explicit bridge on hard scene cuts | `review-story`; `lock-story` blocks missing stages, gaps, jumps, or adult-owned climax |
| **Goal** — educational proof or entertainment payoff | `storyGoal` + intent-specific spine | `review-story` validates fields; pre-image semantic rubric validates meaning |

### Story goal (required before plot selection)

Every book has exactly one branch:

- `educational`: the story demonstrates a requested value or a drawable
  replacement behaviour. It needs temptation/pattern, visible cost,
  child-owned choice, and later proof. With `habitFocus`, the exact
  `targetBehaviorAr` must appear in a `turn` page and again in a `reinforce`
  page.
- `entertainment`: the story fulfills the stated fantasy promise. It needs an
  early invitation, escalating obstacles, a child-owned hero moment, and an
  ending payoff. Do not bolt on a corrective lesson.

The famous guest/archetype may invite, need help, and collaborate. The child
still owns the decisive action. A syntactically valid arc is not enough: write
the `because → therefore` chain and reject any page that survives only as “and
then.”

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
3. **The story must prove it.** Habits require the `educational` branch.
   `lock-story` rejects a story whose
   `personalization.habitArc` is missing or out of order, or whose required
   requests have no `requestCoverage`. The exact `targetBehaviorAr` must be
   visible in at least one `turn` and one `reinforce` page. Write both while you
   write the pages.
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
| New client folder / book start | `init` → `set-story-goal` → matching `list-templates --intent …` + `list-themes` |
| Family describes the child (habit, trait, "لازم يظهر …") | `set-personalization --project … --json '{…}'` |
| Check what was captured | `show-personalization --project …` |
| Family wants a ready-made story | `list-templates --intent <storyGoal.mode>` → `apply-template --project … --template ID [--note …]` |
| Template selected, note changes | `set-template-note --project … --note …` |
| Template note and/or age adaptation incorporated | `review-story` → `complete-template-customization --project …` |
| Browse art themes | `list-themes` |
| Pick art theme | `apply-theme --project … --theme <themeId>` |
| Missing custom story | write `input/story.json` (incl. `storyGoal` + `locations[]`) → deterministic + semantic story review |
| Need the age voice / dictionary | `show-age-profile --age N` |
| Story draft written or edited | `review-story --project …` → run semantic story rubric → fix every error → `prepare-story-review` |
| Markdown storyboard prepared | stop; user reviews/edits `input/story-review.md` in Obsidian |
| User confirms storyboard | re-read file → `approve-story-review --statement "…"` → `lock-story` |
| Family asks for a famous character | `list-guests` → `show-guest --guest <key>` → paste `appearanceNotes` |
| Prompts missing / rewritten | write all JSON → `preflight` (compiles + validates + reports every blocker at once) |
| Prompts valid, no sheet image | `generate-book-images` — wave A renders the sheet **and** every location sheet together |
| Sheet awaiting review | show image → `character-review --accept` (or reject + new prompt version) |
| Sheet accepted | `generate-book-images` — interior pages, then covers |
| Family asks "خلصنا كام؟" | `progress --project <ABS>` → paste `progress.messageAr` |
| All images ready | `build --edition draft` → `verify` |
| Draft ready | run 4 review rubrics in parallel → `merge-reviews` |
| Fix queue | rewrite failed prompts `.v0N` → `compile-prompts` → validate → regenerate failed only → rebuild |
| Attempt-limit/manual issue | `resolve-manual-review --asset ID (--accept\|--image <ABS>) --statement "…"` |
| User approves current verified draft | `approve-final --statement "…"` → `build --edition final` → `verify` |

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

### Print-safe colour (handoff §9, mandatory in every prompt)

The book prints Rich Coverage on coated stock at RST Prints. `compile-prompts`
adds the print-safe clause to **every** prompt at a priority the length-shedding
pass never drops, and `validate-prompts` rejects a prompt without it. Do not
remove it, and do not write a palette that fights it: desaturate 15–20%, no pure
black fills, no full-bleed deep navy, night scenes around `#2C3E50`, no neon.
The palette itself is chosen per story from that story's world — it is not a
template reused between books.

Before sending to the printer, remind Omar to check Ink Limit 280%, GCR instead
of UCR, and Total Area Coverage per page in Acrobat Pro.

### Caption safe zone

The story text is **never** painted into the art. Illustrations come back
completely text-free, and the PDF builder draws the Arabic afterwards as a real,
editable text layer.

Every page prompt therefore forbids all writing in the image — captions, signs,
posters, book covers, labels — and reserves the bottom band of the frame as a
calm, low-detail zone: no faces, hands, or key action there, and no drawn box or
panel. Use the active theme’s `textSafeZoneHint` for how that quiet band should
look in that medium. `validate-prompts` rejects a page prompt missing the
text-free clause, and also rejects one that leaks the story text into the art
prompt.

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

**Do not hand-write it.** Fill the structured fields, run `compile-prompts`, and the pipeline assembles it. See "Seven locks" above.

## Art themes

`$TOOLS/references/themes/catalog.json` is the only theme source of truth.
Always call `list-themes` and offer every returned option; never copy a short
theme list into instructions because the catalog changes.

Interview picks `themeId`; `apply-theme` syncs brief/story + style refs. See `style-lock.md`.

## Hard bans

- Gemini / OpenAI Images API / key CSVs
- Client artifacts inside `hekaytyworkflow/`
- Overwriting prompt versions (bump `.v02`, `.v03`…)
- Generating pages before the user accepts the character sheet
- Generating any image before the current Markdown storyboard is approved
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
