---
name: hekayati
description: >-
  Repository-owned Hekayati production skill for Arabic personalized children's
  books operated through the Rawy Obsidian vault. Use for new clients, stories,
  prompts, images, reviews, PDFs, approvals, or progress.
---

# Hekayati inside Rawy

The canonical portable skill; it ships with the repository. Operator policy
(privacy, client data, how to talk to the user) is in `AGENTS.md` and is not
repeated here.

## Do this first, every session

```bash
python3 tools/scripts/story_pipeline.py context --project <ABS_CLIENT>
```

It returns the **open gate**, the exact next command, and a `read` list of the
two or three reference files that matter for that step. Load those. Do not
pre-load the workflow documents — the whole point of `context` is that
`book.json` already knows where the book is.

Re-run it after every saved action instead of re-deriving state.

## What to load, and only when

| Situation | Load |
|---|---|
| Deciding the next command | `tools/references/workflow/routing.md` |
| Goal, plot, story text, story review | `tools/references/workflow/story.md` |
| Prompt JSON, lanes, renders | `tools/references/workflow/prompts.md` |
| After the draft PDF | `tools/references/reviews/` |
| A rule is disputed or ambiguous | `tools/references/handoff.md` — the law, Arabic, wins every conflict |
| "Is this actually enforced?" | `tools/references/handoff-enforcement.md` |
| Machine-readable rulebook | `show-doctrine` (never open `handoff/doctrine.json` by hand) |

An index of every schema and skeleton: `tools/references/agent-core.md`.

## Production gates

`context` reports these as a ladder and stops at the first open one. The
ordering is the contract; the detail behind each is in the stage file above.

1. Client identity, role, fixed outfit, target age, image consent.
2. Educational or entertainment — asked before any plot menu, then the matching
   ready templates and all current art themes from the live catalogs.
3. Story type A/B/C fixed before plot production.
4. Deterministic and semantic story review pass.
5. `input/story-review.md` exported, then **stop** for explicit user review.
   Re-read the file before recording approval.
6. `lock-story`. It is the step everyone skips: it registers a
   `location-sheet-NN` asset per declared location and copies each page's
   approved Arabic onto its asset. Writing prompts before it means no location
   sheets and nothing to check `inImageText` against.
7. All schema-v2 prompt JSON written together, compiled, validated, preflighted,
   exported under `Prompts/`, then **stop** for one whole-pack approval. Any
   prompt, review, story, theme, or text-plan change makes it stale.
8. An explicit `agent` or `manual` image lane. There is no default — see
   **Two lanes** below.
9. Character and location sheets first; **stop** for human character approval.
   Manual images enter through `Images Inbox/` and use the same later gates.
10. Pages, then covers, with each page's approved Arabic **drawn inside the
    artwork** on its named `textSurface`. Reject and regenerate any render whose
    copy is mirrored, disconnected, reworded, or running off the surface. Never a
    bottom caption strip, a scrim, or a text layer over the art.
11. `image-notes` → fix what is flagged → **stop** for `approve-images`. The
    approval binds to the image bytes, so regenerating one page afterwards
    invalidates it.
12. Draft built and verified; story + continuity + pdf rubrics in parallel, then
    the arabic rubric last, then `merge-reviews`; failures fixed; a final Arabic
    pass on the verified draft; then **stop** for explicit final approval before
    the final PDF.

Book shape is fixed: front cover, 22 interior pages, back cover. Fixed pages
come from `apply-fixed-pages`.

## When the user names a destination

"Keep going until you make the characters" is permission for everything on the
way there. Asking per step in between is a round trip they already paid for.

```bash
python3 tools/scripts/story_pipeline.py context --project <ABS> --until character_sheet
```

`plan.runWithoutAsking` is the stretch to run unattended. `plan.stopsAt` is the
first rung that still needs a person — stop there even when the target is past
it, and name it. Those gates record a statement from a human; running one is not
saving a round trip, it is inventing the human. `--until` lists the gate keys.

## Two lanes

Both lanes read the same approved prompt JSON. They differ only in who presses
generate.

| | `agent` | `manual` |
|---|---|---|
| Who renders | Codex, in this repo, via `generate-book-images` | a person, in whatever image tool they have |
| Cost | tokens per page | none to us |
| Command | `generate-book-images` / `generate-batch` | `manual-dispatch --asset ID [--target …]` |
| Output | images land in `output/images/` | images come back through `Images Inbox/` → `import-image-inbox` |

On the manual lane ask which image tool **before** exporting: `--target chatgpt`
(default) or `--target nanobanana`. One prompt JSON, one render per target —
see `tools/references/prompt-targets.md`.

Every `manual-dispatch` block is self-contained: the slot it fills, the files to
attach in order, the prompt to paste verbatim, the Arabic that must appear, and
the acceptance check. Nothing in it refers to this repo or this conversation, so
it works in ChatGPT, in Nano Banana, or in somebody else's agent. The same blocks
are mirrored into the client's `Prompts/` notes in Rawy for human review.

## Hard constraints

- Use `tools/scripts/codex_imagegen_dispatch.py`. Never a home-directory path.
- Report the pipeline's `progress` value exactly; never estimate.
- Never replace a human approval with agent judgement.
