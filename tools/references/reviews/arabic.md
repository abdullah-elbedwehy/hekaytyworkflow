# Arabic review rubric

The language pass. It runs on the verified draft, and it runs **last** — after
story, continuity and PDF have had their say — because it is the only rubric
that reads the book the way the family will: as Egyptian sentences a parent says
out loud to a child.

Two things are being judged, and they fail differently:

1. **What the page says.** Wrong wording is a `story` fix and a rebuild.
2. **What the model drew.** The image model writes the page's Arabic inside the
   artwork, and it breaks in known ways. A broken render is an `image` fix and a
   regeneration.

**Pages already queued for regeneration by story, continuity, or pdf:** judge
their *wording* only. Their artwork is about to be redrawn, and the Arabic
inside it with it, so anything you say about the letterforms is thrown away
before it is read. On every other page, judge both.

Do not edit client files. Write JSON only under the client's `output/reviews/`.

## Inputs

- `input/story.json` — the exact approved Arabic, plus `languageProfileId` and
  `personalization`
- `$TOOLS/references/story-language/age-profiles.json` — the dictionary and
  register rules for that profile
- The verified draft PDF and `output/renders/draft/`
- `output/images/` — the page art itself, because that is where the Arabic is

## 1) Handoff §2 and §6 — outranks everything else here

`review-story` already blocked the patterns it can match by regex. Your job is
the ones it cannot see.

- **Any literary metaphor standing in for an inner feeling** — including a fresh
  one no pattern list has ever seen. A feeling is said the way a child thinks
  it, not the way a poet would.
- **Pronoun agreement with whoever is being addressed.** Fear aimed at both
  parents gets a plural answer — «قلبنا», never «قلبي».
- **Filler adverbs** that carry nothing: «بهدوء», an unearned «شوية».
- **The dialect markers themselves:** «طب» as a real conversational connector,
  «بكده» rather than «وهكذا», «صحيت» rather than «استيقظت», «احكي» rather than
  «قول» when a feeling is being disclosed.
- **«اوي اوي»** doubling belongs in praise and warmth lines specifically, not
  scattered for texture.
- A short confirming question before a reply is good writing, not an error
  («قصدك ملك صح؟») — it is how people actually talk.

Everything found here is blocking. Handoff §2 outranks every other rule in this
repository.

## 2) The Arabic the model drew

Compare the writing visible in each page image against that page's exact string
in `story.json`, character for character. The model produces convincing-looking
Arabic that is wrong, so read it, do not glance at it.

The failure modes, in the order they actually occur:

| What you see | Call it |
|---|---|
| Letters standing apart that should be joined | `disconnected-letters` |
| The line reading left-to-right, or the word order flipped | `mirrored-text` |
| A word that is not in the approved string at all | `invented-text` |
| A word from the approved string missing | `dropped-text` |
| Copy running off the edge of its surface, or clipped by it | `text-overflows-surface` |
| Letterforms that look like Arabic but spell nothing | `pseudo-arabic` |

Any of these is `critical` with `fixTarget: image`. There is no partial credit:
a page whose Arabic is not exactly the approved string prints a book nobody
signed off on.

Also confirm the PDF's invisible text layer for that page carries the same
string — that is what keeps copy, search and `verify` honest.

## 3) Writing the page did not ask for

The page's copy belongs on the one surface its prompt named. Anything else that
carries writing is a defect: a poster on the wall, a book cover in the child's
hands, a shopfront sign, a label on a box, a second copy of the caption
somewhere else in the frame.

`medium`, `fixTarget: image`.

## 4) Register — must match the story's `languageProfileId`

- **No فصحى leaking into Egyptian narration.** `ذهب`, `وجد`, `ماذا`, `سوف` do
  not become Egyptian by sitting in an Egyptian paragraph.
- **No grammatical tanween**, unless the word is a fixed spoken form listed in
  `sharedEgyptian.lexicalizedTanweenWords` (`شكرًا` and its like), or it sits
  inside a registered `protectedPhraseRegistry` quotation.
- **Vocabulary and sentence length match the age profile's dictionary.** Flag a
  word or a construction clearly above the target band — not one you personally
  would have written differently.

## 5) Protected phrases and refrains

- A page declaring `protectedPhrases: [{"registryId": "…"}]` must render the
  registry's text verbatim, and the sentences around it must explain it
  immediately in plain Egyptian, exactly as the registry entry says.
- A refrain is only a refrain word for word. A near-miss is a rendering error,
  not a stylistic variation.

## Do not judge

Face likeness, prop continuity, page order, or PDF build mechanics — other
rubrics own those, and duplicate findings make the merged fix queue lie about
how much is broken. Do not flag wording preferences the age profile does not
require.

## Severity

| Level | Use for |
|---|---|
| `critical` | Arabic in the art that is missing, added, mirrored, disconnected, or invented; a protected phrase absent or altered |
| `high` | Register mixing (فصحى inside Egyptian), disallowed tanween, a refrain reproduced inexactly |
| `medium` | Writing the page did not ask for; vocabulary above the target age band |
| `low` | Copy a reader can still parse but that sits cramped or small on its surface |

## Output schema

Every blocking issue needs a `fixTarget`: `story` when the approved wording has
to change, `image` when the model drew it wrong, `pdf` when only the invisible
text layer is at fault.

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
      "severity": "critical",
      "fixTarget": "image",
      "category": "disconnected-letters",
      "detail": "the banner reads «ا ح م د ر ا ح ا ل م د ر س ة» — every letter stands alone",
      "fix": "regenerate page-09 from the same prompt; if it breaks twice, move the copy to a flatter, more front-facing surface and bump the prompt version"
    }
  ],
  "notes": []
}
```

Save as `output/reviews/pass-NN-arabic.json`.
