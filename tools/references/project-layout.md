# Client project layout

`hekaytyworkflow` = tools only.

Each client run uses one project folder. **All** md/json/images/pdf live there.

```text
/Users/abdullah/Desktop/project1/
  Abdullah.png
  wael Background Removed.png
  input/
    interview.md
    requirements.md
    brief.json
    story.json              # custom, or personalized by apply-template
    style/                 # optional art refs (theme packs / user refs)
      ref-scene-3d.png     # e.g. after apply-theme --theme cartoony
    prompts/
      character-sheet.v01.json
      cover.v01.json
      page-01.v01.json
      ...
      back-cover.v01.json
  output/
    book.json
    images/
    pdf/
    renders/
    reviews/
    contact-sheets/
```

## Rules

- Persona images stay where the user put them.
- `input/` = source of truth (md + json).
- `input/style/` = optional style refs attached on every `$imagegen` call (after persona photos). Theme packs: `$TOOLS/references/themes/`.
- `output/` = generated artifacts + session state.
- Never write client data into `hekaytyworkflow/`.
- Shared ready-made stories stay in
  `hekaytyworkflow/tools/references/story-templates/catalog.json`; applying one
  copies a personalized story into the client folder.
- Selected template provenance/note lives in client `input/brief.json`,
  `input/story.json`, `output/book.json`, plus the managed Story template block
  in `input/requirements.md`.
