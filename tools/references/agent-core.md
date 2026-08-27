# Agent core — index

This file is an **index**, not a briefing. It used to be a 31 KB document that
every session read in full before doing anything, which spent roughly fifteen
thousand tokens restating rules the current step did not need. The content
still exists; it is now split by stage so a turn loads only its own stage.

> **Law:** [`handoff.md`](handoff.md) — Arabic, Omar's rulebook, wins every
> conflict. Machine-readable: [`handoff/doctrine.json`](handoff/doctrine.json)
> (read it with `show-doctrine`, never by opening the JSON).
> Where each rule is enforced: [`handoff-enforcement.md`](handoff-enforcement.md).

## Start every session with the machine state, not with a document

```bash
python3 tools/scripts/story_pipeline.py context --project /ABS/CLIENT
```

`context` returns the open gate, the exact next command, and the short list of
files worth loading for **this** step. Load those and nothing else. Re-run it
after each saved action instead of re-reading the workflow files.

## Stage files

| Load when | File | Covers |
|---|---|---|
| Most turns — deciding the next command | [`workflow/routing.md`](workflow/routing.md) | mission, state→command table, parallel law, the three image waves, progress reporting, hard bans |
| Choosing a goal, writing or reviewing the story | [`workflow/story.md`](workflow/story.md) | book start, ready-made templates, the human story-review gate, 22+2 structure, story types, language rules, the seven locks, age profile, causal spine, locations bible, personalization |
| Writing prompt JSON, running renders | [`workflow/prompts.md`](workflow/prompts.md) | multi-persona contract, scene depth, staging, print-safe colour, in-image Arabic, game pages, copyright-safe guests, `compiledPrompt`, art themes |
| After the draft PDF | [`reviews/README.md`](reviews/README.md) | the four-rubric loop and `merge-reviews` |

## Schemas and skeletons — open only the one you are filling

- Pages: [`prompt-template.json`](prompt-template.json)
- Character sheet: [`character-sheet-template.json`](character-sheet-template.json)
- Location sheet: [`location-sheet-template.json`](location-sheet-template.json)
- Fill rules: [`prompt-fill-guide.md`](prompt-fill-guide.md)
- Depth contract: [`prompt-rules.md`](prompt-rules.md)
- Two image tools, one page: [`prompt-targets.md`](prompt-targets.md)
- Personalization contract: [`personalization.md`](personalization.md)
- Story / brief contracts: [`story-schema.md`](story-schema.md), [`brief-schema.md`](brief-schema.md)
- Interview script: [`interview.md`](interview.md)
- Style lock: [`style-lock.md`](style-lock.md)
- Safe guests: [`guests/catalog.json`](guests/catalog.json) — reach it with `list-guests` / `show-guest`
- Art themes: [`themes/catalog.json`](themes/catalog.json) — reach it with `list-themes`
- Ready-made stories: `story-templates/catalog.json` — reach it with `list-templates` / `show-template`
- Age dictionaries: `story-language/age-profiles.json` — reach it with `show-age-profile --age N`

Prefer the command over the file for anything in that last group: the catalogs
change, and a pasted list goes stale the moment it is written down.
