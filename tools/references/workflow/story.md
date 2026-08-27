# Workflow · story

Load this file while choosing the goal, picking or writing the story, and
running the human story-review gate. Stop loading it once the story is locked.

> Law: [`../handoff.md`](../handoff.md). Enforcement:
> [`../handoff-enforcement.md`](../handoff-enforcement.md).
> Next command: `story_pipeline.py context --project <ABS>`.

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
3. **Stop.** Show the linked review from the matching Rawy client page. The
   user may edit visible fields in the Rawy vault but must keep the HTML
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

