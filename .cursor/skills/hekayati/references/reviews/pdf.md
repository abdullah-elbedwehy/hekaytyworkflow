# PDF review rubric

Run after draft PDF exists. Do not edit client files. Write JSON only under client `output/reviews/`.

## Inputs

- `output/pdf/draft.pdf`
- `output/book.json` (`settings.orientation`, asset order, per-asset `storyText`)
- Page images under `output/images/`

## Check

### Print safety (handoff §9)

- No full-bleed deep navy, pure black, or heavy saturated dark field on any page
- Night scenes read as desaturated blue-grey (~`#2C3E50`), not deep navy
- Every large dark area is broken by gradient, texture, or lighter accents
- Skin and clothing sit at natural mid saturation — no neon
- All PDF text is K-only (100K / 0C / 0M / 0Y), never Rich Black
- The book is 22 interior pages; the two covers are separate files

Anything failing here is blocking. Also remind Omar to run Ink Limit 280%, GCR
instead of UCR, and Total Area Coverage per page in Acrobat Pro before sending
to RST Prints — that check is his, not the pipeline's.

### Structure

- Page order matches `book.json` asset order (front cover → interior → back cover).
- No blank, corrupt, duplicate, or missing page. Two pages that look
  byte-identical are a generation bug, not a coincidence — flag it even if
  `reconcile-image` should have caught it upstream.
- Page count matches `settings.pdfPageCount`.

### Shape

- Every page shares one orientation (`settings.orientation`); `verify` already
  hard-rejects >8% aspect drift, but flag any page that reads visually
  off-ratio, stretched, or letterboxed anyway.
- Full-bleed: no unintended white margin, border, or edge artifact from the
  scale-to-fill crop.

### Image quality

- Malformed anatomy: hands, feet, faces — extra/missing digits, warped limbs,
  merged bodies.
- Crops that cut a face, hand, or the caption text at a page edge.
- Contrast/exposure: a page too dark or blown-out to read the art or the text.
- Adjacent pages that read as the same picture (same shot scale, viewpoint,
  and staging back-to-back) — this is also a story-rubric concern, but flag it
  here as a visual defect regardless of cause.

### Text layer

Every page carrying story text gets a drawn caption; the art itself must be
completely text-free.

- Caption sits fully inside the safe zone — never cropped by the page edge or
  overlapping the art's main action.
- Font renders correctly (no missing glyphs, no tofu boxes, no reversed RTL
  order) and is legible at print size against its background.
- The illustration carries **no** writing of its own: any letters baked into a
  sign, poster, book cover, or banner are a defect, even decorative ones.
  `build` and the prompt rules both forbid it, so a page that shows text in the
  art was generated from a stale prompt.

## Do not

Rewrite story or exact Arabic wording. Judge plot quality or continuity — other
rubrics own those.

## Severity

| Level | Use for |
|---|---|
| `critical` | Wrong/missing/duplicate page, badly malformed anatomy, cropped caption or face |
| `high` | Off-orientation or stretched page, unreadable contrast, overlay caption escaping the safe zone |
| `medium` | Two adjacent pages read as the same picture, minor crop at a non-focal edge |
| `low` | Small exposure or margin nitpick that doesn't affect readability |

## Output schema

Every blocking issue needs `fixTarget`: `pdf` for caption/layout/build defects,
`image` for faulty source art, or `story` only when the approved wording must
change. Never route a PDF-layout defect into an image retry.

```json
{
  "reviewerRole": "pdf",
  "draftSha256": "<exact draftSha256 returned by verify>",
  "storySha256": "<exact storySha256 returned by verify>",
  "pass": 1,
  "decision": "accept|revise",
  "issues": [
    {
      "assetId": "page-14",
      "severity": "critical",
      "fixTarget": "pdf",
      "category": "cropped-caption",
      "detail": "Arabic caption band is cut off at the bottom page edge",
      "fix": "correct the PDF caption layout, rebuild, and render the draft again"
    }
  ],
  "notes": []
}
```

Save as `output/reviews/pass-NN-pdf.json`.
