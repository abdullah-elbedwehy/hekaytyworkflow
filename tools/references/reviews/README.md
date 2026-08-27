# Review loop (after the draft PDF)

Runs **automatically** when the draft PDF is verified — the same moment the user
is shown the PDF.

Story meaning already passed the story rubric once on the text-only draft, before
`lock-story`. This loop rechecks text-to-image alignment and catches what the
illustration and the layout introduced; it is not the first time anyone looks at
the plot.

## Order inside a pass: three in parallel, then the language pass

```text
story  ·  continuity  ·  pdf     ← one dispatch, in parallel
        ↓ (their fix queue is now known)
arabic                           ← reads last, with that queue in hand
        ↓
merge-reviews (all four)  →  regenerate  →  rebuild + verify
```

The Arabic rubric reads last on purpose, and it is the last thing anybody reads
before the book prints.

The reason is mechanical. The model draws each page's Arabic *inside* the
artwork, so any page already queued for regeneration — bad hands, broken
continuity, a cropped face — comes back with its Arabic redrawn from scratch.
Judging that text before the page is redrawn is reading something that is about
to be thrown away. So when the Arabic reviewer sees a page that the other three
have already queued, it judges the **wording** only and leaves the drawn
letterforms for the next pass. On every page not in that queue, it judges both.

`merge-reviews` still takes all four roles in one call — that gate does not
change.

## Steps

1. Show the absolute `output/pdf/draft.pdf` to the user.
2. Apply three rubrics in parallel:
   - [`story.md`](story.md)
   - [`continuity.md`](continuity.md)
   - [`pdf.md`](pdf.md)
3. Then apply [`arabic.md`](arabic.md), with the pages those three queued
   already known.
4. Copy the exact `draftSha256` and `storySha256` returned by `verify` into all
   four JSON files. Save under the client's `output/reviews/pass-NN-*.json` only.
5. Merge:

```bash
python3 tools/scripts/story_pipeline.py merge-reviews \
  --project <ABS_CLIENT> \
  --review <story.json> --review <continuity.json> \
  --review <arabic.json> --review <pdf.json>
```

6. Regenerate only fix-queue pages (`generate-batch --assets ...`).
   Attempt-limit items use `resolve-manual-review` with
   `--asset ID --accept --statement "…"` or `--image <ABS_CORRECTED_IMAGE>`;
   never hand-edit `book.json`.
7. Rebuild, verify, and show the user again. Accept their notes (append to
   `input/interview.md` or `input/requirements.md`).
8. Repeat until the user says `تمام` / `خلص` / is satisfied.
9. When the user explicitly approves this verified draft, read
   [`arabic.md`](arabic.md) over it one final time — every page, wording and
   letterforms both, with nothing queued and nothing about to change. Only then
   `approve-final --statement "…"`, then build and verify `final`.

Agent edits and user edits happen in the same loop — do not wait for the user
before starting the first automatic pass.
