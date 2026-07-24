# Continuity review rubric

Run after draft PDF exists. Do not edit client files. Write JSON only under client `output/reviews/`.

## Inputs

- Persona photos
- Accepted character-sheet image
- Every `location-sheet-NN` image
- `input/story.json` (personas, `locations[]`, per-page `locationId`)
- Page images under `output/images/`

## Check

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

```json
{
  "reviewerRole": "continuity",
  "pass": 1,
  "decision": "accept|revise",
  "issues": [
    {
      "assetId": "page-07",
      "severity": "high",
      "category": "outfit-drift",
      "detail": "جنى is wearing a pink top; fixedOutfit is the yellow tank with a chest pocket",
      "fix": "regenerate page-07 with the outfit restated"
    }
  ],
  "notes": []
}
```

Save as `output/reviews/pass-NN-continuity.json`.
