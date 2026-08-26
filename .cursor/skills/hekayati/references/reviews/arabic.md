# Arabic review rubric

Run after draft PDF exists. Do not edit client files. Write JSON only under client `output/reviews/`.

## Inputs

- `input/story.json` (exact Arabic source, `languageProfileId`, `personalization`)
- `$TOOLS/references/story-language/age-profiles.json` (dictionary + register rules for that profile)
- Verified draft PDF + `output/renders/draft/`
- Page images under `output/images/` only to confirm they stay text-free

## Check

### Handoff §2 and §6 (highest priority)

`review-story` blocks the patterns it can match. Read for the ones it cannot:

- **Any literary metaphor standing in for an inner feeling** — even a fresh one
  the pattern list has never seen. Feelings are said the way a child thinks
  them.
- **Pronoun agreement with who is being addressed.** Fear aimed at both parents
  gets a plural reply — «قلبنا», not «قلبي».
- **Filler adverbs** («بهدوء», an unearned «شوية») that add nothing.
- **«طب»** as a natural conversational connector, **«بكده»** rather than
  «وهكذا», **«صحيت»** rather than «استيقظت», **«احكي»** rather than «قول» for
  emotional disclosure.
- **«اوي اوي»** doubling belongs in praise and warmth lines specifically.
- A short confirming question before a reply is fine and makes dialogue real
  («قصدك ملك صح؟»).

Report anything you find here as blocking — handoff §2 outranks every other
rule in this repository.

### PDF caption rendering (compare the PDF text layer to `story.json` verbatim)

Flag missing / added / disconnected / mirrored / reversed / substituted /
clipped / illegible Arabic characters in the PDF caption vs the exact source
string for that page. The source illustration itself should contain no caption.

### Register (must match the story's `languageProfileId`)

- No formal/classical (فصحى) leakage into Egyptian narration — `ذهب/وجد/ماذا/سوف` and
  similar are not Egyptian just because the rest of the page is.
- No grammatical tanween ending unless the word is a fixed spoken form listed in
  `sharedEgyptian.lexicalizedTanweenWords` (e.g. `شكرًا`) or sits inside a
  registered `protectedPhraseRegistry` quotation.
- Vocabulary and sentence complexity match the age profile's dictionary — flag a
  word or construction clearly above the target age band.

### Protected phrases

If the page declares `protectedPhrases: [{"registryId": "…"}]`, confirm the
registry's exact text is rendered verbatim in the PDF caption and that the
surrounding page text explains it immediately in simple Egyptian, per the
registry entry.

### Refrains

If the page text matches a declared `refrainPhrases` entry, confirm it is
reproduced exactly — a refrain is only valid verbatim; a near-miss is a
rendering error, not a stylistic variation.

### No stray writing

`compile-prompts` tells the image model to draw **no text anywhere**. Flag any
writing baked into the illustration — signs, posters, book covers, banners,
labels, duplicate captions, or fake letterforms.

## Do not judge

Face likeness, continuity, or PDF mechanics — other rubrics own those. Do not
flag plot or word-choice preferences the age profile doesn't require.

## Severity

| Level | Use for |
|---|---|
| `critical` | Missing, added, mirrored, or reversed Arabic that changes meaning; protected phrase absent or altered |
| `high` | Register mixing (formal leaking into Egyptian), disallowed tanween, refrain reproduced inexactly |
| `medium` | Stray text baked into the illustration, vocabulary above the target age band |
| `low` | Minor legibility (small/cramped) that a reader can still parse |

## Output schema

Every blocking issue needs `fixTarget`: `story` for wording changes, `pdf` for
font/RTL/layout defects, or `image` only when the illustration itself is wrong.

```json
{
  "reviewerRole": "arabic",
  "draftSha256": "<exact draftSha256 returned by verify>",
  "storySha256": "<exact storySha256 returned by verify>",
  "pass": 1,
  "decision": "accept|revise",
  "issues": [
    {
      "assetId": "page-09",
      "severity": "high",
      "fixTarget": "story",
      "category": "register-mixing",
      "detail": "caption reads \"ذهب أحمد إلى البيت\" — formal فصحى inside an Egyptian-narration book",
      "fix": "rewrite story text in Egyptian: \"أحمد راح البيت\", then rebuild the PDF"
    }
  ],
  "notes": []
}
```

Save as `output/reviews/pass-NN-arabic.json`.
