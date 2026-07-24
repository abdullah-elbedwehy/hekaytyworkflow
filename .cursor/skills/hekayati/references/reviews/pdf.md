# PDF review rubric

Run after draft PDF exists. Do not edit client files. Write JSON only under client `output/reviews/`.

## Inputs

- `output/pdf/draft.pdf`
- Renders / page images under `output/`

## Check

Page order, blanks, crops, anatomy, contrast, adjacent visual repetition.

## Do not

Rewrite story or exact Arabic wording.

## Output schema

```json
{
  "reviewerRole": "pdf",
  "pass": 1,
  "decision": "accept|revise",
  "issues": [],
  "notes": []
}
```

Save as `output/reviews/pass-NN-pdf.json`.
