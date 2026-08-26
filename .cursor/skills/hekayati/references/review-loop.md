# Auto review loop (after draft PDF)

Runs **automatically** when draft PDF is verified — same time user is shown the PDF.

Story meaning already passed the story rubric once on the text-only draft
before `lock-story`. This loop rechecks text-to-image alignment and catches
problems introduced by illustration/layout; it is not the first time anyone
looks at the plot.

## Steps

1. Show absolute `output/pdf/draft.pdf` to user.
2. Apply four rubrics in parallel (Cursor agent):
   - [reviews/story.md](reviews/story.md)
   - [reviews/arabic.md](reviews/arabic.md)
   - [reviews/continuity.md](reviews/continuity.md)
   - [reviews/pdf.md](reviews/pdf.md)
3. Copy the exact `draftSha256` and `storySha256` returned by `verify` into all
   four JSON files. Save under client `output/reviews/pass-NN-*.json` only.
4. Merge:

```bash
python3 tools/scripts/story_pipeline.py merge-reviews \
  --project <ABS_CLIENT> \
  --review <story.json> --review <arabic.json> \
  --review <continuity.json> --review <pdf.json>
```

5. Regenerate only fix-queue pages (`generate-batch --assets ...`).
   Attempt-limit items use `resolve-manual-review` with
   `--asset ID --accept --statement "…"` or
   `--image <ABS_CORRECTED_IMAGE>`; never hand-edit `book.json`.
6. Rebuild + verify draft; show user again.
7. Accept user notes (append to `input/interview.md` or `input/requirements.md`).
8. Repeat until user says `تمام` / `خلص` / satisfied.
9. When user explicitly approves this verified draft, run
   `approve-final --statement "…"`, then build + verify `final`.

Agent edits and user edits happen in the same loop — do not wait for user before starting the first auto review pass.
