# Rawy operator contract

The one place these rules live. `CLAUDE.md` and `.cursor/rules/hekayati.mdc`
point here; they do not restate anything. Production gates and the command flow
live in the skill, not here: `.agents/skills/hekayati/SKILL.md`.

## Orientation

1. Open the task from `Rawy/Dashboard.md`.
2. For client work, read `Rawy/Clients/<slug>/Client.md`.
3. Run `python3 tools/scripts/story_pipeline.py context --project <ABS_CLIENT>`.
   It returns the open gate, the exact next command, and the two or three
   reference files worth loading for that step. Load those; skip the rest.

Re-run `context` after each saved action. Do not re-read the workflow files to
work out where a book is — that is what `book.json` is for.

## Operator behavior

- One folder under `Rawy/Clients/` is one client and one book/order.
- For a new client, capture the real name, phone, request, and creation date,
  then create the shell under `Rawy/Clients/`. Never invent missing values.
- Run pipeline actions for the user. Do not turn the conversation into a list
  of terminal commands unless the user explicitly asks for commands.
- Refresh the matching `Client.md` and Rawy statistics after every saved
  production change.
- Preserve user-entered identity, request, deadline, payment, priority,
  blocker, and notes during synchronization.
- Never invent progress, approvals, deadlines, payment state, blockers, or
  customer facts. Read them from the client files and pipeline output. Report
  the pipeline's `progress` value exactly; never estimate your own.
- Never replace a human approval with agent judgement. `context` marks the
  gates that are `waitingOnHuman`; those stop the turn.
- A destination the user already named is permission for everything on the way
  to it. When they say «كمّل لحد ما تعمل الشخصيات», run every mechanical command
  between here and there without asking again — `context --until <gate>` returns
  that stretch as `runWithoutAsking`, and `stopsAt` as the first rung that still
  needs a person. Stop there even when the target is past it, and name the gate
  that stopped you.
- Keep human-facing Arabic natural and Egyptian. Keep paths, IDs, schemas, and
  technical values exact.

## Data boundaries

- All private production data belongs only in the Git-ignored
  `Rawy/Clients/<slug>/` tree. Never place client names, phones, photos,
  stories, prompts, or generated artifacts in tracked files, logs, examples, or
  test fixtures.
- Use repository-owned tools only — `tools/scripts/`. Never call a dispatcher
  or skill from a home-directory or otherwise machine-specific absolute path.

Rawy contains the user-facing GUI only. Doctrine, scripts, schemas, and agent
instructions stay outside the vault navigation.
