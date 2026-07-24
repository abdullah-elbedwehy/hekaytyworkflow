# story.json (client `input/story.json`)

Exactly `pageCount` pages. Example for 20:

ids in order: `cover`, `page-01` … `page-18`, `back-cover`.

For other N: `cover`, `page-01` … `page-(N-2)`, `back-cover`.

```json
{
  "title": "عنوان القصة",
  "targetAge": 5,
  "languageProfileId": "age-3-5",
  "language": "natural Egyptian Arabic",
  "themeId": "storybook",
  "visualStyle": "premium whimsical children's storybook digital illustration, magical realism, cinematic lighting",
  "purpose": "adventure",
  "pageCount": 20,
  "outline": "user outline",
  "templateSelection": null,
  "customizationNote": null,
  "personas": [
    {
      "id": "persona-01",
      "displayName": "عبدالله",
      "role": "hero",
      "fixedOutfit": "جاكيت أزرق فاتح، تيشرت أبيض، بنطلون جينز، حذاء رياضي"
    },
    {
      "id": "persona-02",
      "displayName": "سارة",
      "role": "companion",
      "fixedOutfit": "فستان أصفر، جاكيت أبيض، حذاء أبيض"
    }
  ],
  "guestCharacters": [
    {
      "id": "guest-web-swinger",
      "displayName": "سِراج",
      "appearanceNotes": "athletic young adult rooftop rescuer in a close-fitting deep-plum and mint-green suit with a thin gold thread pattern over the shoulders, full soft-cloth face mask with two large rounded amber lenses, short mint half-cape clipped at one shoulder, coil of braided golden rope at the hip, fingerless grey gloves, no emblem, no logo"
    }
  ],
  "locations": [
    {
      "id": "lantern-square",
      "nameAr": "ميدان الفوانيس",
      "visualDefinition": "A wide stone public square in a fantasy Arab city, ringed by three-storey sandstone buildings with carved wooden balconies, a low octagonal fountain of grey stone at the centre, rows of black iron lantern posts with clear glass panes, chipped grey flagstones, a mint-domed tower behind the north side.",
      "pageCue": "the small square with the round stone fountain, ficus trees and strings of flags overhead"
    }
  ],
  "continuity": {
    "recurringProps": [],
    "palette": "locked palette",
    "avoid": ["identity swap between personas"]
  },
  "narrativeArc": {
    "setup": ["page-01", "page-02"],
    "disruption": ["page-03"],
    "goal": ["page-04", "page-05"],
    "attempts": ["page-06", "page-07", "page-08", "page-09", "page-10"],
    "setback": ["page-11", "page-12"],
    "clue": ["page-13"],
    "choice": ["page-14"],
    "decisiveAction": ["page-15", "page-16", "page-17"],
    "payoff": ["page-18"],
    "resolution": ["back-cover"]
  },
  "refrainPhrases": ["هنجرب تاني!"],
  "personalization": {
    "habitFocus": { "personaId": "persona-01", "habitAr": "…", "type": "reduce", "targetBehaviorAr": "…" },
    "habitArc": {
      "setup": ["page-02"],
      "challenge": ["page-05"],
      "turn": ["page-11"],
      "reinforce": ["page-15", "page-17"]
    },
    "requestCoverage": {
      "req-01": { "pages": ["page-03"], "locationId": "grandma-house" },
      "req-02": { "pages": ["page-01", "page-11"] }
    }
  },
  "pages": [
    {
      "id": "page-03",
      "text": "بعد ما خرجوا من البيت، راحوا عند ميدان الفوانيس. وقال عبدالله: عِلْمًا نَافِعًا.",
      "beat": "the trip to the lantern square begins after the clue",
      "participants": ["persona-01", "persona-02"],
      "guests": [],
      "locationId": "lantern-square",
      "setting": "place",
      "action": "one drawable group action",
      "transitionFromPrevious": "بعد ما خرجوا من البيت، راحوا عند ميدان الفوانيس.",
      "protectedPhrases": [
        {
          "registryId": "dua-beneficial-knowledge"
        }
      ]
    }
  ]
}
```

## Exact age language profile (required)

`targetAge` selects exactly one profile from
`$TOOLS/references/story-language/age-profiles.json`:

- 1–2 → `age-1-2`
- 3–5 → `age-3-5`
- 6–8 → `age-6-8`

Run `show-age-profile --age N` before writing and `review-story` after writing.
The profile owns the word/sentence budget, Egyptian word choices, and required
arc stages. `lock-story` repeats that review and refuses hard failures.

Write `language` as the canonical label `natural Egyptian Arabic` in generated
`brief.json` and `story.json`. The validator accepts `Egyptian Arabic`,
`عامية مصرية طبيعية`, and `العامية المصرية الطبيعية` only for import
compatibility; do not emit those aliases in new work.

### `protectedPhrases[]` (registry-only narrow exception)

Every page entry is an object whose only field is one reviewed `registryId`, for
example `{"registryId":"dua-beneficial-knowledge"}`. String entries,
unregistered IDs, extra fields, and page-level free-form `{text,kind,source}`
objects are invalid. The ID must exist in
`age-profiles.json.protectedPhraseRegistry`; that central entry owns the exact
`text`, `kind`, and `source`. Use the same ID at most once on a page, and put its
registered text visibly and verbatim **exactly once** inside that page's `text`.

| `kind` | Maximum words/tokens |
|---|---:|
| `religious-quote` | 25 |
| `fixed-religious-phrase` | 12 |
| `scientific-term` | 4 |

No other registry kind is accepted. Registry text is unique across the
registry and capped at 200 characters; its reviewed source is at least 12
trimmed characters. The validator removes only the
registered narrow span before formal-register, tanween, and Latin-text checks.
Keep exact religious wording or a necessary scientific term, then explain
around it in simple Egyptian; do not use `protectedPhrases` as a bypass for a
formal narration page or create an ad-hoc source to protect one.

Ordinary Egyptian prose still rejects grammatical tanween case endings. A tiny
reviewed list in `sharedEgyptian.lexicalizedTanweenWords` allows fixed spoken
words such as `شكرًا` and `طبعًا`; any other tanween needs a legitimate central
protected-phrase registry entry, not page-owned metadata.

## Narrative arc and no-jump rule (required)

Every non-cover page must appear in `narrativeArc`; stages must follow page
order. A page normally belongs to exactly one stage. If one page deliberately
carries exactly two adjacent stages, its page object must declare
`combinedArcStages` equal to those two owner stages in canonical
`arcStageOrder`; otherwise review blocks. Three owners, non-adjacent owners,
and declarations on a single-owner page are invalid. Older profiles require
`setback` and `clue` as well. The hero must be
present and acting in `choice` and `decisiveAction`. Every page also needs a
distinct `beat`; declaring a refrain does not permit a repeated beat.

Every page has one drawable `action` and one visible change. If a cut changes
the `locationId` **or** fully replaces the visible cast (`participants` plus
`guests` has no overlap with the prior page), the current page's visible `text`
must contain a meaningful bridge of at least three Arabic words with a real
time, cause, or movement cue. Keeping the hero while teleporting to a new place
still needs a bridge. `transitionFromPrevious` is optional metadata; when
present, its full wording must appear verbatim in `page.text`. Hidden metadata
never repairs a jump. Use `فجأة` at most once in a whole story and only for a
real surprise; it cannot replace a causal bridge.

### Refrains and duplicate text

Declare intentional repetition at story level in `refrainPhrases`.
Each phrase must be non-empty, normalized-unique, and at most 8 Arabic words.
`age-1-2` allows at most two declared refrains, each visibly used on 2–18
non-cover pages; every other profile allows one used on 2–4 pages. Duplicate
normalized full-page text across non-cover pages, including the back cover, is
blocking for ages 3–8. For `age-1-2` only, exact full-page repetition is allowed
when the full text equals a valid declared refrain. A refrain never exempts a
repeated `beat`; for older profiles it repeats as a short phrase inside otherwise
advancing page text.

Deletion test: remove the page mentally. If the next page still works unchanged,
the page is filler or its result has not been carried forward.

## Locations bible (required)

`locations[]` is what stops the art reinventing the world every page. Free-text
`setting` per page was never enough — the image model had no shared definition
of "the square", so it drew a different square each time.

| Rule | Why |
|---|---|
| 1–8 locations per book | A picture book reuses a few places. A new place per page reads as disconnected. |
| `visualDefinition` ≥ 120 chars | Architecture, materials, colors, 2–3 fixed landmarks — enough to redraw from any angle. |
| `pageCue` one short line | What pages quote. See below. |
| Every page needs a `locationId` | It selects which location sheet gets attached as an image reference. |
| Every location must be used | Each one costs a generated reference sheet. |

### Where each field goes

`visualDefinition` is long on purpose, but it belongs in **one** place: the
location-sheet prompt. Pasting it into all 22 page prompts blows the compiled
prompt past its cap and buries the identity locks and Arabic text behind
architecture the model can already see in the attached sheet.

| Consumer | Uses |
|---|---|
| `location-sheet-NN` prompt | the full `visualDefinition` — this image defines the place |
| every page prompt | `nameAr` + `pageCue` + "match the attached location reference sheet" |

The sheet image carries the geometry; the page prompt only has to say which
place it is and what changes (camera angle, hour, weather).

`lock-story` creates one `location-sheet-NN` asset per entry. Those images are
generated before any story page and passed as refs to every page set there.
Vary camera angle and time of day between pages — never the geometry.

Ready-made stories use the same final schema. `apply-template` resolves
`{{hero}}`, converts template participant slots (`hero`, `companions`, `all`) to
real persona ids, copies original guests, and records provenance:

```json
{
  "templateSelection": {
    "templateId": "thread-guardian-lantern-city",
    "titleAr": "عبدالله وحارس الخيوط في مدينة الفوانيس",
    "catalogVersion": 2,
    "appliedAt": "2026-07-17T12:00:00+00:00",
    "customizationNote": null,
    "targetAge": 5,
    "sourceLanguageProfileId": "age-3-5",
    "targetLanguageProfileId": "age-3-5",
    "requiresAgeAdaptation": false,
    "requiresRevision": false,
    "ageAdaptedAt": null,
    "customizedAt": null
  },
  "customizationNote": null
}
```

Template catalog source:
`$TOOLS/references/story-templates/catalog.json`. Once a template is applied,
the workflow gate and provenance are mirrored across `input/story.json`,
`input/brief.json`, and `output/book.json`. If any selection exists, all three
must contain `templateSelection`, and these fields must match exactly:
`templateId`, `titleAr`, `catalogVersion`, `appliedAt`, `customizationNote`,
`targetAge`, `sourceLanguageProfileId`, `targetLanguageProfileId`,
`requiresAgeAdaptation`, `requiresRevision`, `ageAdaptedAt`, and `customizedAt`.
Do not hand-edit gate fields; use the template workflow commands. Page prose
continues to live in `story.json`, but it is not the sole owner of template
state.

`templateSelection.targetAge`, `story.targetAge`, and `brief.targetAge` must be
the same exact integer. It must resolve to `targetLanguageProfileId`, which must
also equal `story.languageProfileId`, `brief.languageProfileId`, and
`book.settings.languageProfileId`. Source and target profile IDs must be known.
If source equals target, `requiresAgeAdaptation` must be false. If adaptation is
pending, both `requiresAgeAdaptation` and `requiresRevision` stay true. On
successful completion, the workflow clears both flags and records durable
`ageAdaptedAt` and `customizedAt` timestamps.

Normal `review-story` reports target-range and recommended-total misses as
warnings. For a cross-profile template, `complete-template-customization` and
`lock-story` promote `page-below-target`, `page-above-target`,
`story-thinner-than-profile`, and `story-denser-than-profile` to blockers. Every
interior page and the total interior copy must therefore reach the selected
target profile's recommended range—not merely remain below its hard maximum.

`themeId` + `visualStyle` must match `brief.json` / `$TOOLS/references/themes/catalog.json`.  
When writing prompts, paste that theme’s `style.medium` / `style.finish` into every page JSON.

## Personalization block (when the family described the child)

`set-personalization` copies `habitFocus` / `secondaryHabits` / `traits` /
`requests` here. **You** add the two proof fields, and `lock-story` checks them:

| Field | Required when | Rule |
|---|---|---|
| `habitArc` | `habitFocus` is set | `setup` → `challenge` → `turn` → `reinforce`, strictly in page order, ≥4 pages, never the cover, hero present on every arc page |
| `requestCoverage` | any `required` request | Real page ids per request; `place` needs a matching `locationId`; required `thing` must be in `continuity.recurringProps` |

The `turn` stage is the child's own decision. An adult or a magic fix there is
the difference between a book that changes behaviour and one that lectures.

Details and interview wording: `personalization.md`.

## Multi-persona page rules

- `participants` = exact persona ids on that page (subset OK).
- Never list a persona who is off-camera.
- Cover / climax / back cover often include everyone; quiet beats may be solo.
- Each page `text` is in-image Arabic. Use the selected age profile; there is no
  single word cap shared by ages 1–8.
- Pipeline passes **only on-page persona photos** + character-sheet as image refs.

## Famous / franchise guests

- Put in `guestCharacters` / per-page `guests`, not personas.
- Image prompts: **detailed description only — never the real name** (avoids `$imagegen` blocks).
- See `$TOOLS/references/copyright-safe-guests.md`.

Reusable ready-made templates contain original guests only. Franchise-inspired
user requests must be converted into original archetypes before being saved to
the shared catalog or copied into image prompts.
