# Hekayati story language system

This directory is the writing reference for age-fit Egyptian-Arabic story text.
It applies to the exact Arabic caption stored in `story.json` and rendered later
as a real, editable **PDF text layer**. Illustration images stay text-free. It
does not replace the story-template catalog, prompt compilation, or any
reviewer.

- Machine-readable profiles: `age-profiles.json`
- Arabic quick-use dictionary: `age-dictionaries-ar.md`
- Evidence and derivation notes: `research-notes.md`

The pipeline reads this file for age-profile listing/showing, story review, and
story lock. A selected ready-made template must be adapted to the resolved age
profile before it can pass `lock-story`.

## Canonical language label

Write `language` as exactly `natural Egyptian Arabic` in every newly generated
`brief.json` and `story.json`. The validator also recognizes `Egyptian Arabic`,
`عامية مصرية طبيعية`, and `العامية المصرية الطبيعية` for compatible imports,
but generators and agents must emit the canonical English label.

## Profile selection

Pick one profile from the child's confirmed age:

| Profile | Age | Target words per interior page | Hard page maximum | Max sentences/page | Hard words/sentence |
|---|---:|---:|---:|---:|---:|
| `age-1-2` | 1-2 | 2-6 | 10 | 1 | 6 |
| `age-3-5` | 3-5 | 7-16 | 22 | 2 | 10 |
| `age-6-8` | 6-8 | 14-24 | 32 | 3 | 16 |

The target is the normal working range. The hard maximum is a rejection gate,
not an alternate target. Count Arabic word tokens after replacing the persona
placeholder. Punctuation does not add another word.

`recommendedTotalMin` and `recommendedTotalMax` assume the current 18 interior
story pages (`page-02` through `page-21`). They exclude the cover title, the
doctrine-owned الإهداء / «قصص تانية» / back-cover copy,
`back-cover` line, legal text, and credits. A deliberate picture-only pause can
lower the total, but it cannot justify overloading another page.

These budgets are **Hekayati product heuristics**, tuned for the PDF caption
zone, page legibility, and the 20-story-page book of handoff §7. They are not
clinical language-development norms and are not copied from a publisher.

For ordinary custom-story review, missing a target page range or recommended
story total is a warning while crossing a hard limit is blocking. Cross-profile
template adaptation is intentionally stricter: before
`complete-template-customization` or `lock-story`, every interior page must sit
inside the selected target range and total interior words must sit inside its
recommended band. The four warning codes `page-below-target`,
`page-above-target`, `story-thinner-than-profile`, and
`story-denser-than-profile` become completion blockers. Staying under the hard
maximum alone is not enough.

## Goal-specific proof

The common causal spine is necessary but not sufficient:

- `educational`: show the unwanted pattern or temptation, a visible cost, the
  child's alternative choice/action, and later proof that the change holds.
  If `habitFocus` exists, exact `targetBehaviorAr` must be visible in a `turn`
  page and again in a `reinforce` page.
- `entertainment`: establish the fantasy promise early, let obstacles escalate,
  make the child own the decisive hero moment, and visibly deliver the ending
  payoff. Do not turn the ending into a lesson the family did not request.

## Story spine

`arcStageOrder` defines the full causal order:

1. `setup` - establish the hero, normal world, and one relevant trait or need.
2. `disruption` - one visible change breaks the normal state.
3. `goal` - the hero wants a concrete, drawable result.
4. `attempts` - the hero tries; every attempt changes the situation.
5. `setback` - an attempt fails or creates a harder problem.
6. `clue` - a previously seeded detail gives the hero usable information.
7. `choice` - the hero decides what to do; no adult or magic makes the decision.
8. `decisiveAction` - the hero performs the action that can solve the problem.
9. `payoff` - the promised result appears visibly.
10. `resolution` - relationships, location, props, and emotional state settle.

Each profile's `requiredArcStages` is the minimum, not permission to scramble
the order. Younger profiles compress stages into simpler beats. They do not
remove cause and effect.

Every non-cover page belongs to one stage by default. If a deliberately compact
page owns exactly two adjacent stages, add `combinedArcStages` and list exactly
those two owners in canonical `arcStageOrder`. Undeclared double ownership,
three owners, non-adjacent owners, and declarations on a single-owner page all
block review. Every page still needs its own distinct `beat`.

### Default placement across the 20 story pages

The catalog's `defaultNarrativeArc` describes the **source** template (`page-01`…`page-18`); every id shifts one place right when the template is
reshaped into the handoff §7 book, which is the numbering shown here:

| Pages | Full `age-6-8` arc |
|---|---|
| `cover` | Promise the story, without adding new plot facts |
| `page-02` to `page-03` | `setup` |
| `page-04` | `disruption` |
| `page-05` to `page-06` | `goal` |
| `page-07` to `page-11` | `attempts` |
| `page-12` to `page-13` | `setback` |
| `page-14` | `clue` |
| `page-15` | `choice` |
| `page-16` to `page-18` | `decisiveAction` |
| `page-19` to `page-21` | `payoff` |
| `back-cover` | `resolution`: one warm emotional echo; no new event or lecture |

For `age-1-2`, use one small attempt and an immediate visible payoff. For
`age-3-5`, use two or three attempts and make the child's choice unmistakable.

## Page test

Every interior page must pass all checks before story lock:

1. **Because:** this page happens because of a visible prior event or stated goal.
2. **Want:** the hero's current want is still clear, or this page clearly changes it.
3. **Action:** one main action can be drawn in a single frozen illustration.
4. **Change:** the page ends in a different physical or emotional state.
5. **Next:** that change creates the next action; it does not merely decorate the theme.
6. **Seed:** every helper, tool, clue, place, and solution appeared before its payoff.
7. **Close:** every promise, question, recurring prop, and introduced problem is closed.
8. **Picture match:** text and image describe the same people, object state, place, and moment.
9. **Age fit:** words, sentence length, dialogue, and emotional intensity match the profile.
10. **Dialect fit:** the line sounds like natural Egyptian when read aloud.
11. **Text fit:** the page stays in the target range and never crosses the hard maximum.
12. **Truth and safety:** scientific, medical, religious, and safety claims are accurate and reviewed.

### Delete test

Temporarily remove the page. If the next page still makes complete sense and no
goal, state, clue, or relationship changes, the page is filler. Cut it or give
it a real causal job.

## Continuity rules

- One main goal per book. Secondary habits get one supporting beat, not a
  competing story.
- Reuse a few declared locations. A new location needs an explicit bridge and a
  real plot purpose.
- Never introduce a character, animal, tool, gift, magic power, or solution on
  the page where it solves the problem.
- Carry the exact state forward: who has the prop, what is broken, who knows the
  clue, current outfit, time of day, and emotional state.
- Put a bridge in the current page's visible `text` whenever `locationId`
  changes **or** the visible cast is fully replaced (`participants` plus
  `guests` has no overlap with the previous page). A shared hero does not excuse
  a place jump. The bridge needs at least three Arabic words and a real time,
  cause, or movement cue such as `بعد ما...`, `وهما راجعين...`, or
  `تاني يوم...`.
- `transitionFromPrevious` is optional. If present, its full text must be
  verbatim visible inside `page.text`; metadata that the child cannot read does
  not bridge an event.
- The child makes the climactic choice and performs the decisive action. A
  guide can help the child notice; the guide cannot solve the climax.
- Do not replace consequence with coincidence, a sudden unseeded power, or a
  late "it was a dream" reset.
- Use `فجأة` at most once, only for a genuine turning point.
- End with the goal's proof: changed behaviour/repaired relationship for an
  educational story, or the promised fantasy payoff for entertainment. Do not
  paste a moral paragraph after the plot is already over.

## Clear Egyptian-Arabic text

### Register

- Write the whole narrative in natural Egyptian Arabic. Do not write Modern
  Standard Arabic and swap isolated words.
- Use the spellings in `sharedEgyptian.canonicalSpellings` consistently:
  `ده`, `دي`, `كده`, `دلوقتي`, `إزاي`, `ليه`, `عشان`, `لسه`, `أوي`.
- Keep negative `ما` separate in the reference style: `ما بقتش`, `ما كانش`.
- Grammatical tanween case endings are blocked. The small
  `sharedEgyptian.lexicalizedTanweenWords` list keeps reviewed spoken forms such
  as `شكرًا` and `طبعًا`; it is not permission to add case endings to narration.
- Prefer concrete verbs: `جرى`, `مسك`, `فتح`, `دوّر`, `اختار`. Avoid stacked
  verbal nouns and abstract labels.
- Name the character again when a pronoun could point to more than one person.
- Read every page aloud. Split any line that needs a second breath.
- `sentenceBudget.maxSentencesPerPage` caps sentence count on one page.
- `sentenceBudget.hardMaxWordsPerSentence` caps the words in each sentence.

### Dialogue

- Dialogue must change the action, reveal a choice, or expose a clue.
- Give characters different voices. A tree, child, parent, and scientist must
  not all speak like the same textbook narrator.
- One turn carries one idea. Break explanations across action and pages.
- For `age-1-2`, keep dialogue to a call, answer, sound, or repeated phrase.
- For `age-3-5`, prefer one short turn per speaker in a page.
- For `age-6-8`, allow a brief exchange, but never an encyclopedia paragraph.

### Fixed and specialist language

- Preserve Quran, hadith, prayer wording, and fixed religious phrases exactly;
  never convert the quoted words into dialect. Explain around them in Egyptian.
- Keep a necessary scientific term correct. Show the concrete example first,
  name the term second, and add no more than one new concept on the same page.
- Declare each exception in the same page's `protectedPhrases` with a reviewed
  registry-only object such as
  `{ "registryId": "dua-beneficial-knowledge" }`. Strings and page-level
  free-form `{text,kind,source}` objects are invalid, as are unregistered IDs or
  extra fields. The ID must exist in top-level `protectedPhraseRegistry`; its
  central entry owns the exact text, kind, and source. The registered text must
  be visibly and verbatim present **exactly once** in `page.text`, and the same
  ID may appear only once on a page.
- Only three registry `kind` values exist: `religious-quote` (maximum 25
  words/tokens), `fixed-religious-phrase` (12), and `scientific-term` (4).
  Registry text is unique across the registry, capped at 200 characters, and
  carries a reviewed source of at least 12 trimmed characters. Proper names and
  general formal narration are not protected kinds.
  Protection removes only that registered narrow span from register, tanween,
  and Latin checks; an invented source cannot create an exception.
- Religious, scientific, medical, developmental, and safety claims need an
  appropriate specialist reviewer. A smooth sentence is not proof that a claim
  is true.

### Refrains and visible repetition

Intentional repetition must be declared once at story level in
`refrainPhrases`. Values are normalized-unique, non-empty, and at most 8 Arabic
words. `age-1-2` allows at most two phrases, each visibly used on 2–18 non-cover
pages; every other profile allows one used on 2–4 pages. Only `age-1-2` may
repeat the exact full `page.text`, including on the back cover, and only when it
equals a valid declared refrain. For ages 3–8 the short refrain may recur inside
otherwise advancing text, but duplicate and near-duplicate full pages stay
blocked. A refrain never excuses duplicate `beat` values.

## Lexicon semantics

Every profile contains:

- `preferred`: a starter set of natural, useful words and phrases for that age.
- `teachWithContext`: words allowed only when the picture and nearby action make
  the meaning clear. Each item carries its `contextRule`.
- `avoidOrReplace`: heavy, unnatural, abstract, unsafe, or misleading language.
  Every item provides `term`, `useInstead`, `reason`, and `severity`.

Severity:

- `high`: block by default; use only after a deliberate specialist-approved exception.
- `medium`: replace in normal story prose; a fixed quote or necessary term may justify review.
- `low`: editorial preference; revise when it improves voice without harming accuracy.

The lexicon is a **curated starter**, not a complete Egyptian-Arabic corpus and
not a certified vocabulary-acquisition inventory. A later corpus-backed version
should distinguish words a child understands, says, and can read independently.

## Hard rejection conditions

Reject or rewrite a story when any of these is true:

- An interior page exceeds its profile's `hardMaxWords`.
- A page exceeds `sentenceBudget.maxSentencesPerPage`.
- A sentence exceeds `sentenceBudget.hardMaxWordsPerSentence`.
- A non-cover page is unassigned, belongs to anything except one stage or one
  explicitly declared adjacent pair, or repeats another page's `beat`.
- Visible full-page text repeats at ages 3–8, or repeats at age 1–2 without
  exactly matching a valid declared `refrainPhrases` entry.
- An event lacks a visible cause, or the next event ignores its result.
- A location change or full cast replacement lacks a visible time/cause/movement
  bridge, or `transitionFromPrevious` points to wording absent from `page.text`.
- A helper, prop, clue, power, or solution appears without setup.
- An adult, guest, narrator, coincidence, or magic object solves the climax for the child.
- An educational moral is stated instead of demonstrated by the hero's choice
  and later proof.
- An entertainment story fails to deliver its fantasy promise, lets a guest
  own the climax, or adds a corrective lesson as the real ending.
- The story mixes Egyptian with unexplained MSA or another Arabic dialect.
- Pronouns, time, location, outfit, object ownership, or emotional state drift.
- Text contradicts the intended picture.
- A scientific, medical, religious, or safety claim is unverified or misleading.
- Content includes graphic blood, humiliating punishment, frightening violence,
  unsafe imitation, or adult themes for the selected age.

## Ready-made template state

Template provenance and revision gates are mirrored across `story.json`,
`brief.json`, and `book.json`; all three copies must agree on exact age, source
and target profile IDs, adaptation/revision flags, and completion timestamps.
The target profile also equals `story.languageProfileId`,
`brief.languageProfileId`, and `book.settings.languageProfileId`. Use template
commands instead of hand-editing these fields. A pending cross-profile change
keeps both `requiresAgeAdaptation` and `requiresRevision` true; successful strict
review clears them, records `ageAdaptedAt`, and records `customizedAt`.

## Copyright boundary

The reference system was derived from pattern analysis, not copied story prose.
Do not reuse a source story's plot sequence, characters, distinctive scenes,
page text, illustration, or catchphrase in Hekayati templates. Build original
stories and original guest characters.

Public availability is not permission to copy. Check the license on the exact
source page or file before any reuse. A source marked with an open license still
requires compliance with its attribution and share-alike terms. Analysis in
`research-notes.md` does not transfer or broaden any source rights.
