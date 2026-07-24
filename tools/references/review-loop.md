# Auto review loop (after draft PDF)

Cursor skill `hekayati` owns this. Rubrics live in:

`.cursor/skills/hekayati/references/reviews/{story,arabic,continuity,pdf}.md`

## Steps

1. Show absolute `output/pdf/draft.pdf` to user.
2. Apply four rubrics in parallel; save JSON under client `output/reviews/pass-NN-*.json`.
3. Merge:

```bash
python3 tools/scripts/story_pipeline.py merge-reviews \
  --project <ABS_CLIENT> \
  --review <story.json> --review <arabic.json> \
  --review <continuity.json> --review <pdf.json>
```

4. Regenerate fix-queue pages → rebuild draft → loop until تمام → final.
