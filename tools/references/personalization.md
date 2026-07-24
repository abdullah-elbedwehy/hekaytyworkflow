# Personalization mode (وضع التخصيص)

Families do not arrive with a plot. They arrive with a child:

> «بيقضم ضوافره لما يتوتر، وبيحب الديناصورات، ولازم بيت جدته في إسكندرية يظهر،
> ودبدوبه البني يفضل معاه.»

That is a habit, a trait, a place request, and a thing request in one message.
Before this mode they all landed in a free-text note that nothing enforced, so
roughly half never reached the pages. Now they are captured structurally and
`lock-story` refuses to lock until the story proves it used them.

## The three inputs

| Input | Field | What the book does with it |
|---|---|---|
| **Habit** — one per book | `habitFocus` | Owns the story arc: setup → challenge → turn → reinforce |
| **Extra habits / traits** | `secondaryHabits[]`, `traits[]` | Colour the hero's behaviour; one visible beat each, no arc |
| **Requests** — place / thing / person / activity / moment | `requests[]` | Become locations, recurring props, or named page beats |

## One habit per book

Chosen deliberately. A book that chases three habits at once stops being a story
and becomes a lecture, and the child recognises the lecture. The extra habits the
family mentions are kept — they just do not get an arc.

`targetBehaviorAr` is required and must be a real replacement behaviour. "يبطل
قضم ضوافره" is not drawable; "يمسك كورة الإسفنج ويعد لتلاتة" is a beat an
illustrator can put on a page.

## Commands

```bash
python3 $TOOLS/scripts/story_pipeline.py set-personalization \
  --project /ABS/client --json '{
    "habitFocus": {
      "personaId": "persona-01",
      "habitAr": "بيقضم ضوافره لما يتوتر",
      "type": "reduce",
      "targetBehaviorAr": "يمسك كورة الإسفنج ويعد لتلاتة",
      "triggerAr": "قبل ما يقف قدام الفصل"
    },
    "traits": [{"personaId": "persona-01", "textAr": "بيحب الديناصورات"}],
    "requests": [
      {"kind": "place", "textAr": "بيت جدته في إسكندرية"},
      {"kind": "thing", "textAr": "دبدوبه البني"},
      {"kind": "moment", "textAr": "لقطة قبل النوم", "required": false}
    ]
  }'

python3 $TOOLS/scripts/story_pipeline.py show-personalization --project /ABS/client
```

- `--file /ABS/payload.json` instead of `--json` for long payloads.
- Calls **merge** by default (families remember things late). `--replace` rewrites
  the block.
- Blocked after `lock-story` — behaviour fixes go through the review loop.
- `type`: `reduce` (soften a habit) or `build` (grow one).
- `kind`: `place` · `thing` · `person` · `activity` · `moment`.
- `required` defaults to `true`; pass `false` for nice-to-have.

### What it writes

| Target | Effect |
|---|---|
| `brief.personalization` | The normalized block, requests numbered `req-01…` |
| `brief.mustShow` | One tagged line per obligation (`تخصيص: …`) |
| `brief.avoid` | Anti-shaming bans (see below) |
| `story.personalization` | Same block + your `habitArc` / `requestCoverage` |
| `story.continuity.avoid` | The same bans, so they reach every page prompt |
| Template note | Refreshes the `[تخصيص]` block, sets `requiresRevision` |

Tagged lines are replaced, never stacked, when you re-run the command. The
family's own note text is left untouched.

## Story obligations

### `habitArc` — required whenever `habitFocus` is set

```json
"personalization": {
  "habitArc": {
    "setup": ["page-02"],
    "challenge": ["page-05", "page-06"],
    "turn": ["page-11"],
    "reinforce": ["page-15", "page-17"]
  }
}
```

| Stage | The beat |
|---|---|
| `setup` | The habit is simply shown, mid-adventure, with no judgment attached |
| `challenge` | It costs something real inside the story — a missed clue, a slower friend |
| `turn` | **The child chooses** the replacement behaviour. Not an adult, not magic |
| `reinforce` | The new behaviour holds a second time, calmly, and is noticed |

Enforced by `lock-story`:

- All four stages non-empty, every id a real page.
- Stages strictly ordered — `setup` ends before `challenge` starts, and so on.
- The habit's persona is a participant on every arc page.
- The cover is not an arc page: it promises the adventure, it does not work.
- At least 4 distinct pages total, so the change is earned rather than announced.

### `requestCoverage` — required for every `required` request

```json
"requestCoverage": {
  "req-01": {"pages": ["page-03", "page-04"], "locationId": "grandma-house"},
  "req-02": {"pages": ["page-01", "page-11", "page-17"]}
}
```

- `place` requests need a `locationId` from `locations[]`, and the listed pages
  must actually be set there — the place then gets its own reference sheet.
- Required `thing` requests must appear in `continuity.recurringProps`; a keepsake
  that changes shape between pages reads as a different object.
- Optional requests may be skipped; if you do cover them, the same rules apply.

## Anti-shaming bans (added automatically)

Any habit work adds these to `avoid`, and they flow into every page prompt:

- وصف البطل بصفة سلبية (شقي / وحش / كسول)
- عقاب أو تخويف أو سخرية كحل للعادة
- شخص كبير يحل المشكلة بدل البطل
- صفحة وعظ مباشر بدل ما العادة تتحل بالحدث

A habit book that shames the child is worse than no book. The child is the one
who solves it; adults may notice and be glad, nothing more.

## Route interaction

**Custom story** — write `habitArc` and `requestCoverage` into `story.json` as you
expand the outline, then `lock-story`.

**Ready-made template** — the template ships 20 finished pages, so personalization
reopens the revision gate:

1. `set-personalization` (before or after `apply-template`).
2. The generated `[تخصيص]` note is merged into `customizationNote` and
   `requiresRevision` flips to `true`.
3. Tailor the affected beats, add `habitArc` + `requestCoverage`.
4. `complete-template-customization` → `lock-story`.

## Interview shape

Ask for the habit in the family's own words, then push once for the replacement:

> - في عادة حابين القصة تساعده فيها؟
> - بيحصل إمتى بالظبط؟ (قبل النوم / لما يتوتر / في المدرسة)
> - لو مش هيعملها، تحبوه يعمل إيه بدلها؟   ← this becomes `targetBehaviorAr`
> - في مكان أو حاجة أو حد لازم يظهر في الكتاب؟

If the family lists several habits, name the one you are giving the arc and say
plainly that the rest will show up as small moments — one book, one change.
