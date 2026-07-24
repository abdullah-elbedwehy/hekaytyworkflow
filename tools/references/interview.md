# Interview contract

Log every turn in the **client** file `input/interview.md`.

## Style (be helpful)

- Egyptian Arabic. Warm, clear, guide the family — do not make them dig.
- Prefer one question per turn; if user dumps many answers, record all and ask next missing field only.
- On book start (`ابدأ` / `start` / new book): **proactively offer full menus** (templates + themes) before deep interview questions.
- Stop asking when user says `ابدأ`, `start`, `كمل`, or `اختار إنت` — fill remaining gaps with sensible defaults and proceed.

## Book-start menu (mandatory)

Right after persona discovery (or on `ابدأ` / `start`), run both catalogs and show **everything** in one helpful reply:

```bash
python3 $TOOLS/scripts/story_pipeline.py list-templates
python3 $TOOLS/scripts/story_pipeline.py list-themes
```

Present:

1. **مغامرات جاهزة** — every template: Arabic title + one-line summary (+ English title if useful). Offer **قصة مخصوص** as last option.
2. **ستايل الرسم** — every theme: `labelAr` / `label` + short look line from fingerprint/`visualStyle`. Mark catalog default.

Do **not** hide choices behind “say if you want options.” Surface the full lists first; then confirm names/roles/outfits/age and proceed.

## First branch: ready-made or custom

After showing the menus, ask: `تحب تختار مغامرة جاهزة من اللي فوق، ولا نعمل قصة مخصوص؟`

- Ready-made: confirm real persona names/roles/outfits and exact target age,
  run `show-age-profile --age N`, then run `apply-template --template ID`. Ask
  one optional follow-up:
  `تحب تضيف ملاحظة أو حاجة مخصوصة جوه القصة؟`
- Custom: continue through the full outline questions below.

A selected template already provides title, purpose, outline, original guests,
continuity, and 20 complete page beats. Do not ask the user to re-invent them.
Confirm persona names/roles/outfits and target age before apply because those
values are baked into the personalized `story.json`. Consent and art theme must
still be resolved before generation; if changed after apply, sync both brief
and story.
If the target age profile differs from the template's source profile, adapt the
page copy and run `review-story`. Cross-profile completion is strict: every
interior page must reach the target word range and total interior words must
reach the profile's recommended band. If a note exists, tailor only affected
pages. Then run `complete-template-customization` and `lock-story`.

After template application, never hand-edit selection gates. The complete
`templateSelection`—including exact `targetAge`, source/target profile IDs,
adaptation/revision flags, and completion timestamps—must stay identical in
`story.json`, `brief.json`, and `book.json`. Their age and language-profile
fields must match the selection target too.

## Collect (or default)

1. **All personas** — confirm real Arabic `displayName` + `role` (hero/companion/…) for every discovered photo. Filenames may be Instagram junk; never keep numeric stems as names.
2. Consent (user + guardians) — required before any Codex `$imagegen` call.
3. Story route: ready-made template (from full `list-templates` menu) or custom story.
4. `pageCount` for custom stories (total PDF pages: cover + story + back cover). Default 20. Ready-made templates supply 20 pages.
5. Exact target age (integer 1–8). Immediately run
   `show-age-profile --age N`; record its `languageProfileId`, page budget,
   dictionary, and required arc stages. Never write one generic voice for all
   ages. Write the canonical `language` label `natural Egyptian Arabic` in both
   brief and story; accepted aliases are only for importing older files.
6. Custom route only: story purpose / outline (can be short; expand later). Mention how the personas relate (siblings, friends, …).
7. Guest characters if any (only if user asked). **Famous ones** (Spider-Man, Elsa, …): run `list-guests`, pick the archetype that satisfies the same wish, and paste its `appearanceNotes`. Never put the franchise name — Latin or Arabic — into any prompt field. See `copyright-safe-guests.md`.
   Tell the family plainly: naming the character makes the image fail; a described version of the same hero works and looks the way they want.
8. **Fixed outfit per persona** + must-show / avoid.
8b. **Personalization** — habits, traits, and must-appear places/things. Ask
   these even if the family picked a ready-made template; they are what makes it
   *this* child's book. Record with `set-personalization`, never as loose prose:

   - في عادة حابين القصة تساعده فيها؟ (واحدة بس هي اللي هتاخد قوس القصة)
   - بتحصل إمتى؟ (قبل النوم / لما يتوتر / في المدرسة) → `triggerAr`
   - تحبوه يعمل إيه بدلها؟ → `targetBehaviorAr` **(مطلوب — لازم حاجة تترسم)**
   - بيحب إيه؟ بيخاف من إيه؟ → `traits[]`
   - في مكان أو حاجة أو حد لازم يظهر في الكتاب؟ → `requests[]`

   If the family lists several habits: name the one taking the arc, and tell them
   the rest will appear as small moments. One book, one change.
   Contract: `personalization.md`.
9. **Art theme** — run `list-themes` and show the family **every** option, then
   `apply-theme --theme <id>`. The catalog is the source of truth; never recite a
   hardcoded list here — it goes stale. Default is `storybook`.
   Themes range from painterly storybook and 3D CGI to anime, watercolour,
   cut-paper, clay stop-motion, felt craft, crayon, comic, retro cartoon,
   pixel art and chalk pastel.
10. Custom route only: title (or derive).

## Multi-persona interview beats

Ask once per person if missing:

- اسمه إيه في القصة؟
- دوره إيه؟ (بطل / صاحب / أخ / …)
- لبسه الثابت إيه طول الكتاب؟

If user says ابدأ with names missing: invent clear Arabic names from context and note them in `requirements.md`.

## On ابدأ

First: show full template + theme menus if not already shown this session.

Ready-made route: keep the applied complete `story.json`, adapt it when the
target language profile differs, incorporate any customization note into
affected pages, run `review-story`, then `complete-template-customization`, and
fill missing outfit/theme fields.

Either route, if personalization exists: write `personalization.habitArc`
(setup → challenge → turn → reinforce) and `personalization.requestCoverage`
into `story.json` before locking — `lock-story` rejects the story without them.

Custom route: fill missing outfits, title, palette, and expand outline into full `story.json` with exactly `pageCount` beats plus ordered `narrativeArc`. Write every page from the selected age dictionary.  
Each page `participants` = subset of persona ids present in that beat (cover/back cover often all; quiet beats may be solo).  
Also write the **`locations[]` bible**: pick 1–8 places the story reuses, give each a concrete `visualDefinition`, and set a `locationId` on every page. Do not ask the family for this — derive it from the outline and confirm only the place names in Arabic.  
Give every non-cover page one arc owner. If one compact page deliberately owns
exactly two adjacent stages, declare both in canonical-order
`combinedArcStages`. Put a
visible time/cause/movement bridge inside the current `page.text` whenever the
location changes or the visible cast is fully replaced; any supplied
`transitionFromPrevious` must appear there verbatim. In top-level
`refrainPhrases`, ages 1–2 may declare exact full-page repetition; older ages
may declare only a short phrase repeated inside advancing text. Duplicate beats
remain invalid. For reviewed fixed wording, select registry-only entries such as
`protectedPhrases: [{"registryId":"dua-beneficial-knowledge"}]`; never invent
page-level text/kind/source metadata.
Write `input/requirements.md` summary. Then `review-story` → fix every error → lock-story → **write all prompts in one pass** → `compile-prompts` → `validate-prompts` → generate.
