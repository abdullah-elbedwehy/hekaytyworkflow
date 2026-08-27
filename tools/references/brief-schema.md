# brief.json (client `input/brief.json`)

For newly generated files, `language` is always the canonical label
`natural Egyptian Arabic`. Accepted aliases are import compatibility only.

```json
{
  "project": "<ABS>/Rawy/Clients/<slug>",
  "language": "natural Egyptian Arabic",
  "targetAge": 5,
  "languageProfileId": "age-3-5",
  "purpose": "adventure",
  "storyGoal": null,
  "pageCount": 24,
  "title": null,
  "outline": "عبدالله وسارة رايحين مغامرة",
  "templateSelection": null,
  "customizationNote": null,
  "personas": [
    {
      "id": "persona-01",
      "displayName": "عبدالله",
      "imagePath": "/ABS/personas/abdullah.png",
      "role": "hero",
      "fixedOutfit": null
    },
    {
      "id": "persona-02",
      "displayName": "سارة",
      "imagePath": "/ABS/personas/sara.png",
      "role": "companion",
      "fixedOutfit": null
    }
  ],
  "guestCharacters": [],
  "mustShow": [],
  "avoid": ["identity swap between personas"],
  "themeId": "storybook",
  "visualStyle": "premium whimsical children's storybook digital illustration, magical realism, cinematic lighting",
  "personalization": {
    "habitFocus": null,
    "secondaryHabits": [],
    "traits": [],
    "requests": [],
    "updatedAt": null
  },
  "consent": { "confirmed": false, "statement": null }
}
```

## `storyGoal`

Set this before choosing a plot:

```bash
python3 tools/scripts/story_pipeline.py set-story-goal \
  --project /ABS/CLIENT \
  --mode educational \
  --goal "يتعلم يجهز شنطته وينزل المدرسة في ميعاده"
```

Modes are `educational` and `entertainment`. Educational may carry
`personalization.habitFocus`; entertainment may not. A ready-made template
must have the same `storyIntent` as this mode. `lock-story` also requires the
same mode and `goalAr` in `story.json`.

## `personalization`

Written only by `set-personalization` — never by hand, because it also refreshes
the tagged `mustShow` / `avoid` lines and the template note.

```json
{
  "habitFocus": {
    "personaId": "persona-01",
    "habitAr": "بيقضم ضوافره لما يتوتر",
    "type": "reduce",
    "targetBehaviorAr": "يمسك كورة الإسفنج ويعد لتلاتة",
    "triggerAr": "قبل ما يقف قدام الفصل"
  },
  "secondaryHabits": [],
  "traits": [{ "personaId": "persona-01", "textAr": "بيحب الديناصورات" }],
  "requests": [
    { "id": "req-01", "kind": "place", "textAr": "بيت جدته في إسكندرية", "required": true, "notesAr": null }
  ]
}
```

One `habitFocus` per book — it owns the story arc. `mustShow` / `avoid` entries
that start with `تخصيص:` are generated from this block and replaced on every
update; anything else in those lists is yours to keep.

Full contract, arc stages, and coverage rules: `personalization.md`.

For a ready-made story, `apply-template` fills:

```json
{
  "templateSelection": {
    "templateId": "thread-guardian-lantern-city",
    "titleAr": "عبدالله وحارس الخيوط في مدينة الفوانيس",
    "catalogVersion": 2,
    "storyIntent": "entertainment",
    "appliedAt": "2026-07-17T12:00:00+00:00",
    "customizationNote": "خلي البوصلة هدية من جدته",
    "targetAge": 5,
    "sourceLanguageProfileId": "age-3-5",
    "targetLanguageProfileId": "age-3-5",
    "requiresAgeAdaptation": false,
    "requiresRevision": true,
    "ageAdaptedAt": null,
    "customizedAt": null
  },
  "customizationNote": "خلي البوصلة هدية من جدته"
}
```

The selected template writes `input/story.json` reshaped to the handoff §7
structure (24 PDF assets), with the two missing story pages opened as
declared holes. If target
age selects a different language profile, `requiresAgeAdaptation` also blocks
lock until the page copy is rewritten, `review-story` meets the strict target
density, and `complete-template-customization` records completion. For a
cross-profile template, every interior page must fall inside the target page
range and total interior words must fall inside the recommended band; the usual
`page-below-target`, `page-above-target`, `story-thinner-than-profile`, and
`story-denser-than-profile` warnings become completion blockers. A note is a
tailoring instruction: revise only affected pages before `lock-story`. Use
`set-template-note` to add, replace, or clear it while the story is unlocked.
After revising, run `complete-template-customization`; story lock is blocked
until that confirmation clears `requiresRevision`.

`templateSelection` is workflow-owned mirrored state, not a brief-only note. If
it exists in any one file, the same object must exist in `input/brief.json`,
`input/story.json`, and `output/book.json`. These fields must match across all
three: `templateId`, `titleAr`, `catalogVersion`, `storyIntent`, `appliedAt`,
`customizationNote`, `targetAge`, `sourceLanguageProfileId`,
`targetLanguageProfileId`, `requiresAgeAdaptation`, `requiresRevision`,
`ageAdaptedAt`, and `customizedAt`. Do not edit them by hand.

The selection's `targetAge` equals `brief.targetAge` and `story.targetAge` and
resolves to `targetLanguageProfileId`. That profile equals
`brief.languageProfileId`, `story.languageProfileId`, and
`book.settings.languageProfileId`; source and target IDs must be registered
profiles. Source equal to target means `requiresAgeAdaptation: false`. While a
cross-profile change is pending, both revision flags stay true. Successful
completion clears both, records `ageAdaptedAt`, and records `customizedAt`.

`languageProfileId` is derived, never guessed: exact ages 1–2 → `age-1-2`, 3–5
→ `age-3-5`, and 6–8 → `age-6-8`. Source and rules:
`story-language/age-profiles.json`.

`themeId` = art theme from `$TOOLS/references/themes/catalog.json` (`storybook` | `cartoony` | `fairytale-glow` | `feature-cgi` | `enchanted-glow` | `wonder-trail`).  
`visualStyle` = catalog `visualStyle` for that theme (keep in sync).  
Apply: `apply-theme --project <ABS> --theme <themeId>`.

`pageCount` = total PDF pages (cover + middle + back cover). For custom stories,
change it with `set-pages` before locking. Applying a ready-made template safely
syncs the project to the handoff §7 page count (24); it cannot be changed after
template application.

Multi-persona: `init` discovers every image under `personas/` (or project root). Interview must replace garbage filenames with real Arabic `displayName` + `fixedOutfit` per person.
