# Ready-made story templates

`catalog.json` contains 15 original personalized entertainment adventures.
Only entries with `qualityStatus: "ready"` appear in the normal menu or may be
applied. Educational books remain fully supported through the custom-story
path, but this reusable catalog intentionally contains no sourced adaptations.

The current ready menu contains 15 original entertainment adventures. Source
copy is `age-3-5`; ages 6-8 trigger required copy adaptation and story review
before lock. Generated client files use the canonical language label `natural
Egyptian Arabic`.

These are story templates, not art themes. Art still comes from
`../themes/catalog.json`.

## Template index

| ID | Arabic title | Category | Core value |
|---|---|---|---|
| `thread-guardian-lantern-city` | `{{hero}} وحارس الخيوط في مدينة الفوانيس` | masked-city-rescue | calm courage and observation |
| `princess-lujain-seven-doors` | `{{hero}} ولُجين في قصر الأبواب اللي بتسمع` | original-princess-palace | listening and inclusive hospitality |
| `frost-palace-warm-star` | `{{hero}} ونجمة الدفا في قصر الصقيع` | winter-princess-adventure | patience and flexible thinking |
| `coral-cartographer-map` | `{{hero}} وخريطة مرجانة تحت البحر` | underwater-mermaid-adventure | care for nature and close observation |
| `lost-cloud-train` | `{{hero}} وقطار الغيوم التايه` | sky-train-adventure | persistence and pattern reading |
| `gentle-dragon-first-flight` | `{{hero}} وزُهَير في مدرسة التنانين` | gentle-dragon-adventure | encouragement without pressure |
| `little-dinosaur-island` | `{{hero}} وتيتو في جزيرة الديناصورات` | dinosaur-exploration | evidence, patience, and animal care |
| `story-moon-rescue` | `{{hero}} وإنقاذ قمر الحكايات` | space-rescue | curiosity and experimentation |
| `awake-toy-town` | `{{hero}} وليلة في مدينة الألعاب` | living-toys-adventure | reuse and shared contribution |
| `captain-lemon-treasure` | `{{hero}} وكنز القبطانة ليمونة` | friendly-pirate-treasure | sharing and true value |
| `whispering-forest-secret` | `{{hero}} وسر غابة الهمسات` | enchanted-forest-adventure | listening before reacting |
| `light-crew-mission` | `{{hero}} ومهمة فرقة الضوء` | original-superhero-team | ordinary skills matter |
| `animal-city-clock-mystery` | `{{hero}} ولغز ساعة مدينة الحيوانات` | gentle-detective-mystery | evidence before judgment |
| `cloud-stadium-final` | `{{hero}} ونهائي ملعب السحاب` | football-sports-adventure | teamwork and fair play |
| `colored-dream-gate` | `{{hero}} وبوابة الأحلام الملوّنة` | dream-emotion-adventure | every feeling has a useful message |

There are currently no ready-made educational templates. Set an educational
goal, author the client-specific story, then send it through the same quality
and human-review gates. Do not import or lightly rewrite third-party stories
into this shared catalog.

## Catalog contract

Top level:

```json
{
  "schemaVersion": 3,
  "catalogVersion": 2,
  "templates": {},
  "defaultTemplateId": "thread-guardian-lantern-city",
  "defaultLanguageProfileId": "age-3-5",
  "defaultNarrativeArc": {}
}
```

Every `templates` key equals its entry's `templateId`. Every entry contains:

- `templateId`, `titleAr`, `titleEn`, `category`, `summaryAr`, and `purpose`.
- `storyIntent`: exactly `educational` or `entertainment`.
- `qualityStatus`: `ready` or `needs-revision`. Blocked entries need a
  non-empty `qualityIssuesAr`; ready entries have no quality issues.
- Educational entries have `moral`, `premiseAr`, `temptationAr`, `costAr`, and
  `endingProofAr`.
- Entertainment entries have `fantasyPromiseAr`, `heroWantAr`, `stakesAr`,
  `heroMomentAr`, and `endingPayoffAr`.
- `ageRange` with integer `min` and `max`.
- Source `languageProfileId` (or root `defaultLanguageProfileId`) and a target
  profile derived from the client's exact age.
- `tagsAr`, `mustShow`, and `avoid` string lists.
- `pageCount: 20` — this describes the **source** template, not the finished
  book. Handoff §7 fixes a book at 24 PDF assets, so `apply-template`
  reshapes the template and opens the two missing story pages as declared
  holes a human must write. See [`../handoff.md`](../handoff.md).
- `guestCharacters`, each with a unique `id`, `displayName`, and detailed
  original `appearanceNotes`.
- `continuity.palette`, `continuity.recurringProps`, and `continuity.avoid`.
- `locations[]` (1-8 reusable place bibles) and a valid `locationId` on every
  page.
- `narrativeArc` or root `defaultNarrativeArc`, covering every non-cover page.
- Exactly 20 source pages in this order:
  `cover`, `page-01` through `page-18`, `back-cover`. On apply these become
  `cover`, `page-02`…`page-19`, `back-cover`, with `page-01` الإهداء,
  `page-22` «قصص تانية», and empty `page-20`/`page-21` added.
- Every page has `id`, short Egyptian-Arabic `text`, `beat`,
  `participantSlots`, `guests`, concrete `setting`, and drawable `action`.

The only catalog placeholder is `{{hero}}`. Do not add generic name tokens such
as `{{name}}`, guest-name tokens, or note tokens.

## Persona role slots

`participantSlots` uses only these values:

- `hero`: the primary persona.
- `companions`: every non-hero persona; this can resolve to an empty list.
- `all`: every persona in the client project.

Use `all` alone. Use `hero` and `companions` together only when the scene works
with no companion personas. Original declared guests must still make the action
read naturally for a one-person book.

`pages[].guests` contains only IDs declared in the same template's
`guestCharacters`. Every visible human, animal, robot, talking tree, or creature
must be declared and listed on that page. Do not hide invented background people
inside `setting` or `action`.

## Use in the workflow

List and preview:

```bash
python3 tools/scripts/story_pipeline.py list-templates --intent entertainment
python3 tools/scripts/story_pipeline.py show-template \
  --template thread-guardian-lantern-city
```

`list-templates --intent educational` returns an empty menu and directs the
operator to the custom-story path; it does not disable educational books.

The story goal must be set before apply and must match the template:

```bash
python3 tools/scripts/story_pipeline.py set-story-goal \
  --project /ABS/CLIENT \
  --mode entertainment \
  --goal "يساعد بطل مقنّع ينقذ المدينة"
```

Apply to an initialized client project:

```bash
python3 tools/scripts/story_pipeline.py apply-template \
  --project /ABS/CLIENT \
  --template thread-guardian-lantern-city \
  --note "خلي البوصلة هدية من جدته"
```

The template owns its 20-page source count; the finished book is always 24. `apply-template` personalizes
`{{hero}}`, expands the persona slots, copies original guests, and writes the
derived client `input/story.json`. Per-family changes belong in that client
story, not back in this shared catalog.

`apply-template` rejects `needs-revision` entries even if someone knows the ID.
`list-templates --include-drafts` exists only for authoring/audit work.

The note is optional. Age adaptation is not: when source and target language
profiles differ, rewrite the full page copy to the target dictionary and
**target** page/total budget, then run `review-story`. Normal density warnings
become blockers during cross-profile completion: every interior page must fall
within the target range and the total interior copy must fall within the
recommended band, not merely stay below hard maxima. When a note is present:

1. Weave it into one to three relevant pages. Preserve the main causal arc.
2. Keep the persona as the decisive problem-solver.
3. Add any newly visible character to `guestCharacters` and the affected
   `pages[].guests`.
4. Keep every page ID, order, and total count unchanged.
5. Run `complete-template-customization`, then `lock-story`.

Good notes add a hobby, favorite color, small fear, family object, preferred
football position, calming routine, or desired lesson. Reject or safely rewrite
notes containing real addresses, schools, contact details, unsafe acts, adult
themes, humiliation, or frightening violence.

## Mirrored template-selection state

`apply-template` writes the same `templateSelection` into `input/story.json`,
`input/brief.json`, and `output/book.json`. If one copy exists, all three must
exist and these workflow-owned fields must match exactly:

- `templateId`, `titleAr`, `catalogVersion`, `storyIntent`, `appliedAt`, and
  `customizationNote`.
- `targetAge`, `sourceLanguageProfileId`, and `targetLanguageProfileId`.
- `requiresAgeAdaptation`, `requiresRevision`, `ageAdaptedAt`, and
  `customizedAt`.

The selection's `targetAge` must equal both story and brief ages and resolve to
its `targetLanguageProfileId`. That profile must equal
`story.languageProfileId`, `brief.languageProfileId`, and
`book.settings.languageProfileId`; source and target IDs must both exist in the
language catalog. If source equals target, `requiresAgeAdaptation` is false. A
pending cross-profile change keeps both `requiresAgeAdaptation` and
`requiresRevision` true. After strict review passes,
`complete-template-customization` clears them, records `ageAdaptedAt`, and
records `customizedAt`. Use template commands rather than editing these gate
fields by hand. Page prose is edited in `story.json`, while gate/provenance
state stays mirrored across all three files.

## Copyright-safe guest rule

Every catalog guest is original. The masked rescuer, princesses, mermaid,
talking toys, hero team, and animal city intentionally satisfy familiar
adventure wishes without copying protected characters.

- Never replace an original guest with a franchise name inside the catalog.
- Never add brand logos, signature emblems, famous catchphrases, or an
  unmistakable costume/color arrangement.
- Keep `appearanceNotes` concrete enough for stable generation and distinct
  enough to remain original.
- If a family asks for a famous character, retain the story function but create
  a new name, silhouette, palette, outfit, props, and behavior.

## Content-quality checks

Before publishing or changing a template, verify:

- Intent promise first. Educational stories prove the requested value or
  replacement behaviour; entertainment stories deliver the stated fantasy and
  payoff without turning into a hidden lesson.
- Cause and effect reaches setup, disruption, goal, attempt, setback,
  observation, meaningful choice, decisive hero action, payoff, and resolution.
- Guest characters guide or collaborate; they never solve the climax for the
  persona.
- Egyptian-Arabic copy is natural, positive, and inside the selected age
  profile's page budget. Never apply one generic 24-word rule to ages 1-8.
- No grammatical case endings in Egyptian narration. The only ordinary
  exceptions are fixed spoken forms in `sharedEgyptian.lexicalizedTanweenWords`
  such as `شكرًا`; exact religious/scientific wording uses a reviewed
  `protectedPhraseRegistry` ID, then a simple explanation. Page-level strings
  or free-form `{text,kind,source}` objects are invalid.
- Every non-cover page belongs to one ordered causal-arc stage. If a page
  deliberately owns two stages, `combinedArcStages` must exactly match its
  owners in canonical order. Every page keeps a distinct `beat`.
- A cut that changes `locationId` **or** fully replaces the visible cast puts a
  real bridge in the current page's visible `text`. If
  `transitionFromPrevious` is supplied, its full wording is verbatim visible in
  that text; hidden metadata does not repair the jump.
- Duplicate and near-duplicate full-page text is blocked for ages 3–8; one
  short declared refrain may recur inside advancing text on 2–4 pages. Only
  `age-1-2` may repeat an exact full page that equals one of at most two
  declared refrains (used on 2–18 pages). Entries are normalized-unique, at
  most 8 Arabic words, and never permit a duplicate `beat`.
- `فجأة` appears at most once and never hides a missing cause.
- Every page shows one concrete, drawable action and a visible change from the
  prior page.
- Adjacent pages vary location, staging, action, or viewpoint.
- Single-persona projects remain grammatical and visually complete.
- Every visible non-persona is declared. Guest IDs never drift between pages.
- Recurring outfits, guest appearance, props, and palette stay locked.
- Stakes remain age-appropriate: no combat, weapons, falls, drowning,
  humiliation, villains, or punishment framing.
- The moral emerges from the persona's choice. Avoid lecture-like ending copy.
- For habit stories, exact `targetBehaviorAr` is visible on at least one `turn`
  page and one later `reinforce` page.
- Custom notes change details, not safety rules, identity locks, or the core
  20-page source structure.

Run the catalog/unit validation after every edit:

```bash
python3 -m unittest tools.tests.test_story_templates
```
