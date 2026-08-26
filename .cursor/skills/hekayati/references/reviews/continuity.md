# Continuity review rubric

Run after draft PDF exists. Do not edit client files. Write JSON only under client `output/reviews/`.

## Inputs

- Persona photos
- Accepted character-sheet image
- Every `location-sheet-NN` image
- `input/story.json` (personas, `locations[]`, per-page `locationId`)
- Page images under `output/images/`

## Check

### Handoff §8 identity drift

The single most common failure in this business: the tool reaches for the last
image it produced instead of the approved sheet, and the face walks away from
itself over 20 pages.

- Compare every page against the **accepted character sheet**, never against the
  neighbouring page. Drift is only visible against the original.
- Same face proportions, same eye size and shape, same nose and mouth, same skin
  and hair tone as the sheet — not as the real photo.
- No style drift toward realism, and no changing face proportions between pages.
- The fixed outfit is identical on every page the person appears.
- Landscape 16:9 on every page, no split frames, no portrait.

Where realism and sheet-matching disagree, sheet-matching wins. Report any drift
as blocking with the sheet as the reference.

Compare against the locks, not against your memory of the previous page.

### Identity (per persona, every page they appear on)

- Face reads as the **same child** as their photo and the character sheet — face shape, eye colour and spacing, nose, mouth, hairline.
- Hair: same colour, length, and style (fringe, ponytail, curl pattern).
- Skin tone identical across pages — check pages with very different lighting especially, warm sunset light must not change their complexion.
- Outfit exactly matches `fixedOutfit`: garment type, colour, and details like a chest pocket or a hair elastic.
- Apparent age stable — a child must not read as 4 on one page and 9 on another.
- **No identity swap**: persona A never borrows persona B's face, hair, or clothes.

### Place (per location, every page set there)

- Architecture matches that location's sheet: same layout, same openings, same proportions.
- Fixed landmarks present and in the same relative position (the fountain, the bench, the noticeboard, the shelves).
- Materials and colours match — a turquoise door does not become green.
- Only camera angle, time of day, and weather may differ between visits.
- A page must not silently relocate: if `locationId` says the courtyard, it is the courtyard.

### Props and state

- `continuity.recurringProps` appear where the story implies them.
- Prop state progresses correctly and never reverts (a soaked book does not become dry again, a finished poster does not become blank).

### Cast

- Only `participants` + declared `guests` appear. Flag any invented extra person.
- Guest characters keep the same appearance on every page they appear on.
- Pages with no participants contain **no people at all**.

## Do not judge

Plot quality, Arabic spelling, or art taste. Only whether the locked things stayed locked.

## Severity

| Level | Use for |
|---|---|
| `critical` | Identity swap, wrong child's face, a page in the wrong location |
| `high` | Outfit or hair drift, missing landmark, invented extra person |
| `medium` | Prop state error, skin tone shifted by lighting |
| `low` | Minor prop position or small detail difference |

## Output schema

Every blocking issue needs `fixTarget`: `image`, `story`, or `pdf`. Outfit,
identity, prop, and visual-location drift normally target `image`.

```json
{
  "reviewerRole": "continuity",
  "draftSha256": "<exact draftSha256 returned by verify>",
  "storySha256": "<exact storySha256 returned by verify>",
  "pass": 1,
  "decision": "accept|revise",
  "issues": [
    {
      "assetId": "page-07",
      "severity": "high",
      "fixTarget": "image",
      "category": "outfit-drift",
      "detail": "جنى is wearing a pink top; fixedOutfit is the yellow tank with a chest pocket",
      "fix": "regenerate page-07 with the outfit restated"
    }
  ],
  "notes": []
}
```

Save as `output/reviews/pass-NN-continuity.json`.
