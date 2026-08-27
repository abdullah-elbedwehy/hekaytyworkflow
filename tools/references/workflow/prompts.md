# Workflow · prompts and images

Load this file while writing prompt JSON, choosing an image lane, and reviewing
renders. Not needed before the story is locked.

> Law: [`../handoff.md`](../handoff.md). Enforcement:
> [`../handoff-enforcement.md`](../handoff-enforcement.md).
> Next command: `story_pipeline.py context --project <ABS>`.

## Multi-persona contract

1. Discover every image under `personas/` (or project root). Each = `persona-01…N`.
2. Interview: get **real Arabic display names + roles + fixed outfits** for every persona (filenames may be garbage).
3. `story.json` pages list exact `participants` ids for that beat — subset OK; never invent people.
4. **character-sheet** prompt: **all** personas, multi-view each, separate, same outfits forever.
5. **Page** prompts: only people in `participants` (+ guests if any). Per-persona `identityLocks`, `fixedOutfits`, `actionAndEmotion`.
6. Refs passed to `$imagegen`:
   - character-sheet → all persona photos
   - page → only on-page persona photos + accepted character-sheet + style refs
7. Continuity: same face/outfit/props across pages; never swap identities between personas.


## Baked prompt quality (every page JSON)

### Scene (must be drawable)

Fill all layers: `place`, `timeOfDay`, `atmosphere`, `lighting`, `foreground`, `midground`, `background`, `propsInFrame[]`, `backdropDetails`. Concrete materials/colors. No vague one-liners.

### Multi-person staging

When 2+ participants on page:
- State spatial relation (who left/right/front, who touches whom)
- One shared action beat; per-person pose + emotion
- Clear face visibility for every on-page persona
- No identity mix (name A must match photo A)

### Print-safe colour (handoff §9, mandatory in every prompt)

The book prints Rich Coverage on coated stock at RST Prints. `compile-prompts`
adds the print-safe clause to **every** prompt at a priority the length-shedding
pass never drops, and `validate-prompts` rejects a prompt without it. Do not
remove it, and do not write a palette that fights it: desaturate 15–20%, no pure
black fills, no full-bleed deep navy, night scenes around `#2C3E50`, no neon.
The palette itself is chosen per story from that story's world — it is not a
template reused between books.

Before sending to the printer, remind Omar to check Ink Limit 280%, GCR instead
of UCR, and Total Area Coverage per page in Acrobat Pro.

### Story text lives inside the picture

The image model draws the Arabic itself, as part of the artwork. Every page
prompt carries two fields:

- `inImageText` — the page's approved Arabic, character for character, copied
  from `story.json`. Never reworded, shortened, or "tidied". `validate-prompts`
  and `begin-asset` both refuse a prompt whose copy drifted from the approved
  text, because that prints a book nobody signed off on.
- `textSurface` — the thing in the scene the copy is printed on: a paper note
  pinned to a corkboard, a cloth banner on the bedroom wall, a wooden sign over
  the maze, a windowsill, a chalkboard. Naming it is what makes the words read as
  part of the room instead of a caption pasted on top; the copy then takes that
  surface's angle and its light.

Never a caption bar, bottom strip, white panel, scrim, or UI overlay. Reference
sheets carry no copy at all — leave `inImageText` empty and they come back
wordless.

Arabic from an image model breaks in specific ways: mirrored, letters
disconnected, words invented, text running off the surface. Reject and
regenerate; do not accept a page whose Arabic is not exactly the approved
string. The PDF also carries the same text invisibly, so copy, search and
`verify` keep working.

### Game pages (handoff §8 — read this before writing one)

A game page has to *work as a puzzle*, not look like one. A child will put a
crayon on it. Declare a `gameSpec` on the prompt with `kind` set to `maze`,
`spot-the-difference`, or `search-and-find`.

**You write every element and where it sits. The tool invents none.** This is
the rule that gets broken most often, and it is the one that produces a maze
with three exits or a spot-the-difference whose "differences" are compression
noise. `gameSpec.elements` is where they go.

| kind | You must supply | The prompt then enforces |
|---|---|---|
| `maze` | `startDescription`, `goalDescription`, `elements` | Exactly one continuous open route; every other corridor dead-ends; unbroken walls; corridors wide enough for a child's finger |
| `spot-the-difference` | `differenceCount`, `differences`, `elements` | Two panels identical in framing, light and palette except for exactly the listed differences, each a whole object a child can name |
| `search-and-find` | `targetItems`, `elements` | Every target present, fully visible and countable at the stated quantity |

Three rules across all three kinds:

- **Never draw the answer.** Mark the start and the goal on a maze; never trace
  the winning path. Never circle, number, or highlight a difference or a target.
- **The instruction text goes inside the image**, on a `textSurface` that suits a
  game page — a wooden sign hung above the maze, a banner over the panels.
- **Placement follows the story's movement** (handoff N7): a "get to class" maze
  belongs while the hero is walking, not after they arrive. If a friend is on the
  page, they are *playing*, not watching.

`validate-prompts` fails a game page with no `gameSpec`, with a missing required
field, or whose `differenceCount` does not match the differences actually listed.

A page counts as a game when its `beat`, `setting`, or visible `text` reads as an
instruction to the child — that last one is what usually gives it away. Declare
`"pageType": "game"` on a puzzle whose wording hides it, and `"pageType":
"story"` on a narration page the heuristic misreads. Never silence the error with
an invented `gameSpec`.

### Copyright-safe famous characters

Naming a franchise character gets the image **refused** — the job fails and the page comes back empty. Describing the look works fine. This is tested: an identical scene generated cleanly with a described guest and was refused when the character was named.

1. `list-guests` → find the archetype matching what the family asked for.
2. `show-guest --guest <key>` → paste `appearanceNotes` **verbatim** into `story.json` `guestCharacters[]` and each page's `guests[]`.
3. Never write the franchise name in **any** image-bound field. `validate-prompts` scans `compiledPrompt`, `narrativeBeat`, `primaryRequest`, `spatialStaging`, `palette`, every `scene.*` field, `propsInFrame[]`, participant/guest `displayName`, `identityLocks.*` and `actionAndEmotion.*` — in Latin **and Arabic** (`سبايدر مان`, `إلسا`, `ميكي ماوس`, …).
4. A thin guest description (< 120 chars) is rejected: vagueness is what makes the model reach for the franchise it recognizes.

Library: `$TOOLS/references/guests/catalog.json`. Rules: `$TOOLS/references/copyright-safe-guests.md`.

Ready-made/public catalog entries use original guest characters only. If a user
requests a franchise by name, convert it into an original archetype before it
enters reusable catalog or image-prompt text.

### `compiledPrompt` is compiled, not written

Fill the **structured fields** well. Then run `compile-prompts`. The pipeline assembles the string in a fixed priority order and bounds it, because image models weight the head of a prompt and drop the tail — hand-written prompts kept losing the Arabic text rules off the end.

Priority: header → identity locks → actions → guests → setting → layers → style → composition → **Arabic text** → palette → avoid. Sections are shed from the least important end if it runs long. Identity, setting, style and the Arabic text block are never dropped.

If `compile-prompts` errors that a prompt is too long, shorten the verbose field it names — do not raise the cap.

The seven coherence locks this serves are in [`story.md`](story.md).

## Art themes

`$TOOLS/references/themes/catalog.json` is the only theme source of truth.
Always call `list-themes` and offer every returned option; never copy a short
theme list into instructions because the catalog changes.

Interview picks `themeId`; `apply-theme` syncs brief/story + style refs. See `style-lock.md`.

