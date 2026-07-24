# Auto review loop (after draft PDF)

Runs **automatically** when draft PDF is verified — same time user is shown the PDF.

## Steps

1. Show absolute `output/pdf/draft.pdf` to user.
2. Apply four rubrics in parallel (Cursor agent):
   - [reviews/story.md](reviews/story.md)
   - [reviews/arabic.md](reviews/arabic.md)
   - [reviews/continuity.md](reviews/continuity.md)
   - [reviews/pdf.md](reviews/pdf.md)
3. Save JSON under client `output/reviews/pass-NN-*.json` only.
4. Merge:

```bash
python3 tools/scripts/story_pipeline.py merge-reviews \
  --project <ABS_CLIENT> \
  --review <story.json> --review <arabic.json> \
  --review <continuity.json> --review <pdf.json>
```

5. Regenerate only fix-queue pages (`generate-batch --assets ...`).
6. Rebuild + verify draft; show user again.
7. Accept user notes (append to `input/interview.md` or `input/requirements.md`).
8. Repeat until user says `تمام` / `خلص` / satisfied.
9. Build + verify `final`.

Agent edits and user edits happen in the same loop — do not wait for user before starting the first auto review pass.
