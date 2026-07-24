# Story review rubric

Run after draft PDF exists. Do not edit client files. Write JSON only under client `output/reviews/`.

## Inputs

- Locked `input/story.json`
- Page images under `output/images/`
- Target age from brief/requirements

## Check

### Causal chain (the main test)

Read the pages in order and write the arc as a chain: *because of page N, page N+1 happens.*
Flag any page where the link is "and then" instead of "because".

A complete arc reaches all of these, in order:

1. **Setup** — who they are and what they love, shown not stated
2. **Disruption** — the thing that breaks
3. **Goal** — what they now want
4. **Attempt** — a concrete plan they act on
5. **Setback** — the attempt is not enough, honestly shown
6. **Observation** — the child notices something real that reframes the problem
7. **Choice** — the child decides, and it costs something
8. **Decisive action** — the child solves it, not an adult and not luck
9. **Payoff** — the visible result
10. **Resolution** — the promise from the opening restored or repaid

Flag a missing setback especially: a story where the first attempt just works has no arc.

### Agency

- The child is the one who notices, decides, and acts.
- Guests may guide, encourage, or open a door — they must never solve the climax.
- Nothing is fixed by magic, coincidence, or an adult stepping in at the end.

### Per page

- One concrete drawable action, and a visible change from the previous page.
- The page text and the page image are telling the same moment.
- Adjacent pages differ in location, staging, or shot — no two consecutive pages that read as the same picture.
- Text is short enough for a picture book (prefer ≤ 24 words) and matches the target age.

### Tone

- Age-appropriate stakes: no combat, weapons, real peril, humiliation, or punishment framing.
- The moral emerges from the child's choice. No lecture in the closing lines.
- Every character keeps their dignity, including the one who is wrong.

## Do not judge

Arabic glyph rendering, face likeness, or PDF mechanics — other rubrics own those.

## Severity

| Level | Use for |
|---|---|
| `critical` | Broken causal chain, an adult or coincidence solves the climax |
| `high` | Missing setback or observation beat, a page with no visible change |
| `medium` | Two adjacent pages that read the same, text too long for the age |
| `low` | Wording that could be warmer or more specific |

## Output schema

```json
{
  "reviewerRole": "story",
  "pass": 1,
  "decision": "accept|revise",
  "arcChain": "page-01 → … one line per link, stating the because",
  "issues": [
    {
      "assetId": "page-11",
      "severity": "high",
      "category": "missing-setback",
      "detail": "the drying plan works immediately, so the idea on page-15 is unmotivated",
      "fix": "show some books beyond saving before the observation beat"
    }
  ],
  "notes": []
}
```

Save as `output/reviews/pass-NN-story.json`.
