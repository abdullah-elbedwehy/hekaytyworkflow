# Story review rubric

Run in two phases:

1. **Semantic preflight before `lock-story` and before image generation.** Read
   the text-only draft, return issues, and revise `story.json` until it passes.
   Do not spend image calls on a broken plot.
2. **Post-PDF alignment review.** Do not edit client files. Write JSON only
   under client `output/reviews/`.

## Inputs

- Preflight: unlocked `input/story.json` + `input/brief.json`
- Post-PDF: locked `input/story.json`, draft PDF/renders, and page images
- Target age from brief/requirements

## Check

### Handoff rules the machine cannot judge

`check-doctrine` already caught the mechanical ones. These are yours — every one
is blocking:

- **L3 — the emotional crisis resolves through a concrete event.** A gift that
  arrives, a hug, playing together. An abstract inner shift ("وبقى فاهم") is a
  fail even when no banned phrase appears.
- **L4 — reassurance sounds like a parent, not a proverb.** Warm, plain,
  addressed to this child.
- **N2 — fear or jealousy is spoken *to the person it is about*.** «مش عايزكو
  تحبوا حد أكتر مني», not a vague generalisation.
- **N3 — every page serves *this* book's behaviour problem.** A scene that could
  be lifted from another story unchanged is filler; cut it or give it a job.
- **N5 — a magical companion reacts emotionally to the hero's growth.** Not
  scenery.
- **N6 — a promise made by the parents is actually paid off** near the end. Find
  the setup, then find the payoff. If the payoff is missing, that is the issue.
- **N7 — the game page sits where the movement actually is.** A "reach the
  classroom" maze belongs during the walk, not after arriving.
- **N8 — friends notice a visible outward sign** («شكلك زعلانة»), never the
  feeling by magic.
- **C2 — close mixed-gender play is not shown as ordinary and repeated.**
- **Type A only:** there is a real relapse before the fix, and the reward is
  earned by something the hero actually did (N4), not by their role in the family.

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

### Goal branch (never grade both at once)

Read `storyGoal.mode`.

For `educational`:

- The requested value/habit appears as behaviour, not a label.
- The old pattern or temptation has a visible, proportionate cost.
- The child chooses a specific replacement action without shame, punishment,
  magic, or an adult taking control.
- A later scene proves the change holds. If `habitFocus` exists, exact
  `targetBehaviorAr` is visible on a `turn` page and a `reinforce` page.
- The ending does not explain the moral after the proof already showed it.

For `entertainment`:

- The fantasy promise appears early and matches `storyGoal.goalAr`.
- The guest needs the child's help; the guest does not merely escort a passive
  child through spectacle.
- Obstacles escalate and force new action.
- The child's hero moment is the decisive climax.
- The ending pays off the promised wish and does not replace it with a hidden
  corrective lesson.

### Agency

- The child is the one who notices, decides, and acts.
- Guests may guide, encourage, or open a door — they must never solve the climax.
- Nothing is fixed by magic, coincidence, or an adult stepping in at the end.

### Per page

- One concrete drawable action, and a visible change from the previous page.
- The page text and the page image are telling the same moment.
- Adjacent pages differ in location, staging, or shot — no two consecutive pages that read as the same picture.
- Text follows the selected age profile's page/sentence budget. Never use one
  generic word cap for ages 1–8.

### Tone

- Age-appropriate stakes: no combat, weapons, real peril, humiliation, or punishment framing.
- Educational: the moral emerges from choice and proof. Entertainment: the
  fantasy promise gets a satisfying payoff. No lecture in either closing.
- Every character keeps their dignity, including the one who is wrong.

## Do not judge

Arabic glyph rendering, face likeness, or PDF mechanics — other rubrics own
those. During preflight, there is no image/PDF alignment to judge.

## Severity

| Level | Use for |
|---|---|
| `critical` | Broken causal chain, intent mismatch, unsafe teaching, or an adult/guest/coincidence solves the climax |
| `high` | Missing setback or observation beat, a page with no visible change |
| `medium` | Two adjacent pages that read the same, text too long for the age |
| `low` | Wording that could be warmer or more specific |

## Output schema

Every blocking issue needs `fixTarget`: `story` for text/plot edits, `image`
for illustration-only defects, or `pdf` for layout/build defects. This example
requires a fresh Markdown story-review revision; never spend an image retry on it.

```json
{
  "reviewerRole": "story",
  "draftSha256": "<exact draftSha256 returned by verify>",
  "storySha256": "<exact storySha256 returned by verify>",
  "pass": 1,
  "decision": "accept|revise",
  "arcChain": "page-01 → … one line per link, stating the because",
  "issues": [
    {
      "assetId": "page-11",
      "severity": "high",
      "fixTarget": "story",
      "category": "missing-setback",
      "detail": "the drying plan works immediately, so the idea on page-15 is unmotivated",
      "fix": "show some books beyond saving before the observation beat"
    }
  ],
  "notes": []
}
```

Save as `output/reviews/pass-NN-story.json`.
