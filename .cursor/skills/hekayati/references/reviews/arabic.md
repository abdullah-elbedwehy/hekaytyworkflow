# Arabic review rubric

Run after draft PDF exists. Do not edit client files. Write JSON only under client `output/reviews/`.

## Inputs

- `input/story.json` (exact Arabic source)
- Original page images from `output/images/`

## Check

Flag missing / added / disconnected / mirrored / reversed / substituted / clipped / illegible Arabic vs story text.

## Do not

Rewrite locked copy.

## Output schema

```json
{
  "reviewerRole": "arabic",
  "pass": 1,
  "decision": "accept|revise",
  "issues": [],
  "notes": []
}
```

Save as `output/reviews/pass-NN-arabic.json`.
