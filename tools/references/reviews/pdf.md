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
- Crops that cut a face, a hand, or the page's Arabic at a page edge.
- Contrast/exposure: a page too dark or blown-out to read the art or the text.
- Adjacent pages that read as the same picture (same shot scale, viewpoint,
  and staging back-to-back) — this is also a story-rubric concern, but flag it
  here as a visual defect regardless of cause.

### The page's Arabic

The model draws the Arabic inside the artwork, on the surface the prompt named.
This rubric judges it as *printed matter*, not as wording — whether the reader
can read it on paper. Whether it says the right thing belongs to the Arabic
rubric.

- It sits fully inside the trim, clear of the page edge and of the art's main
  action, and its surface is not cropped in half.
- Letterforms are correct at print size: joined, right-to-left, no missing or
  invented glyphs, no mirrored line.
- It has enough contrast against the surface it is printed on to survive
  ink-limited coated stock — pale copy on a pale banner fails here even when it
  looks fine on screen.
- The PDF's invisible text layer for the page matches the visible Arabic, so
  copy, search and `verify` keep working.
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
| `critical` | Wrong/missing/duplicate page, badly malformed anatomy, a cropped face, or Arabic cut off by the trim |
| `high` | Off-orientation or stretched page, unreadable contrast, Arabic too low-contrast to read at print size |
| `medium` | Two adjacent pages read as the same picture, minor crop at a non-focal edge |
| `low` | Small exposure or margin nitpick that doesn't affect readability |

## Output schema

Every blocking issue needs `fixTarget`: `pdf` for build, order, or text-layer
defects, `image` for anything wrong inside the artwork — including Arabic the
model drew badly, since fixing that means regenerating the page — or `story`
only when the approved wording itself must change.

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
      "fixTarget": "image",
      "category": "cropped-text-surface",
      "detail": "the wooden sign carrying the page's Arabic runs off the bottom trim; the last word is cut",
      "fix": "move the sign fully inside the frame in the prompt, bump the prompt version, and regenerate page-14"
    }
  ],
  "notes": []
}
```

Save as `output/reviews/pass-NN-pdf.json`.
