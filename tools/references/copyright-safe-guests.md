# Copyright-safe guests (famous characters)

Famous / franchise characters (Spider-Man, Elsa, Batman, …) **block** `$imagegen` if named. Verified: the same rooftop scene generated cleanly with a described guest, and was refused when the character was named — the page came back empty.

## Start here: the guest library

```bash
python3 $TOOLS/scripts/story_pipeline.py list-guests
python3 $TOOLS/scripts/story_pipeline.py show-guest --guest web-swinger
```

`$TOOLS/references/guests/catalog.json` holds 15 vetted original archetypes, each keyed by the wish it satisfies (masked rope-swinging rescuer, ice princess, caped night protector, mermaid, princess host, friendly pirate, gentle dragon, living toy, animal detective, hero team, …).

Paste `appearanceNotes` **verbatim** rather than improvising. Improvised descriptions are what drift back toward the protected design and get refused.

## What gets scanned

`validate-prompts` rejects franchise names — Latin **and Arabic**, with spelling variants folded (`إلسا` = `الســا`, `ميكى` = `ميكي`) — in every image-bound field:

`compiledPrompt`, `narrativeBeat`, `primaryRequest`, `spatialStaging`, `palette`, all `scene.*`, `scene.propsInFrame[]`, participant and guest `displayName`, `identityLocks.*`, `actionAndEmotion.*`.

A guest whose `appearanceNotes` is under 120 characters is also rejected: vagueness is precisely what makes the model fall back on the franchise it recognizes.

## If a job is refused anyway

`codex-imagegen` detects refusals and automatically retries once with a softened brief that restates the character as an original design. If that still fails, the description is too close to a protected look — swap in a library archetype.

## Ready-made catalog rule

Reusable entries under `story-templates/catalog.json` use original characters
only. Convert the requested function or fantasy (web rescue, ice palace,
masked city helper, royal visit) into a distinct name, silhouette, palette,
costume, powers, and world. Do not ship franchise names, logos, or near-copies
as product templates.

If legacy/custom metadata needs `canonicalHint`, keep it private in catalog,
brief, or story metadata only. Never copy it into page `compiledPrompt`,
`guests.appearanceNotes`, `setting`, `action`, or other image-bound fields.

## Rule

In **every** image prompt (`compiledPrompt`, `guests.*.appearanceNotes`, scene text):

- **Describe** the look in rich visual detail  
- **Never** write the character’s real name, nickname, or franchise title  
- **Never** write logos, trademarks, or “official costume of …”

Story Arabic in `story.json` / in-image text may still use a kid-friendly name if the family wants it in the book — but the **English `$imagegen` prompt must stay nameless**. Prefer inventing a local alias in story text when possible.

## How to write guests

Store in `guests[]` / `guestCharacters[]`:

```json
{
  "id": "guest-hero-01",
  "displayName": "بطل العنكبوت",
  "canonicalHint": "spider-man",
  "appearanceNotes": "athletic youth hero in a full red-and-blue skintight suit with a black web-pattern overlay, large white eye lenses on a full-face mask, muscular but friendly silhouette, no logos, no brand marks"
}
```

- `canonicalHint` = private note for the agent only (optional). **Never** copy `canonicalHint` into `compiledPrompt`.
- `appearanceNotes` + `compiledPrompt` = description only.

## Examples

| Don’t say | Do say |
|---|---|
| Spider-Man | red-and-blue masked hero, web-pattern suit, white eye lenses |
| Batman | dark armored vigilante cape, pointed cowl, bat-silhouette chest emblem avoided — use simple dark oval instead |
| Elsa | young woman in sparkling ice-blue gown, platinum braid, frost magic aura |
| Mickey Mouse | round-eared cartoon mouse in red shorts and yellow shoes — **avoid**; prefer original mouse friend design |
| Superman | tall hero in blue suit, red cape, simple chest shield shape without letter |

## compiledPrompt snippet pattern

> Guest hero (not a named franchise character): [full costume + body + pose]. No logos. No trademarks. No character names.

## Avoid list extras (every page)

Add to `avoid` when guests are famous-coded:

- franchise character names
- brand logos / trademark emblems
- “official licensed costume”
