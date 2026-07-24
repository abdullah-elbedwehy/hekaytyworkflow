# Hekayati tools

Python helpers called by the Cursor skill `.cursor/skills/hekayati`.

Not a standalone agent skill. Entry point:

```bash
python3 tools/scripts/story_pipeline.py <command> --project /ABS/client
```

## First-time Mac setup

One command installs Homebrew (if needed), Python 3.9+, Node, Codex CLI, and
pip deps (`pillow` / `reportlab` / `pypdf`). Does **not** run `codex login`
(browser auth — you do that once).

```bash
python3 tools/scripts/story_pipeline.py setup
# or:
bash tools/scripts/setup-mac.sh
```

Check readiness anytime:

```bash
python3 tools/scripts/story_pipeline.py doctor
```

Then only:

```bash
codex login
```

Schemas and image-prompt skeletons live in `tools/references/`.

Ready-made stories live in `references/story-templates/catalog.json`. `list` and
`show` need no client project; `apply` needs an initialized client project. They are
complete 20-page plans: choose one, personalize it into the client project, add
an optional note, then continue through the normal story lock and image flow.
Applying writes an unlocked `input/story.json`; it does not generate images.

Age-specific Egyptian dictionaries and narration contracts live in
`references/story-language/age-profiles.json`. Select the exact profile before
writing; then run the story review before lock:

```bash
python3 tools/scripts/story_pipeline.py list-age-profiles
python3 tools/scripts/story_pipeline.py show-age-profile --age 5
python3 tools/scripts/story_pipeline.py review-story --project /ABS/client
python3 tools/scripts/story_pipeline.py lock-story --project /ABS/client
```

`review-story` checks word/sentence limits, Egyptian register, protected exact
quotations, ordered `narrativeArc`, hero-owned choice/action, and unbridged hard
scene cuts. `lock-story` runs the same review and blocks on errors.

```bash
python3 tools/scripts/story_pipeline.py list-templates
python3 tools/scripts/story_pipeline.py list-templates --category fantasy
python3 tools/scripts/story_pipeline.py show-template --template <ID>
python3 tools/scripts/story_pipeline.py apply-template \
  --project /ABS/client --template <ID>
python3 tools/scripts/story_pipeline.py lock-story --project /ABS/client
```

Add or replace the note before story lock:

```bash
python3 tools/scripts/story_pipeline.py set-template-note \
  --project /ABS/client --note "خلي المغامرة يوم عيد ميلاده"
# Tailor the affected story pages, then:
python3 tools/scripts/story_pipeline.py complete-template-customization \
  --project /ABS/client
python3 tools/scripts/story_pipeline.py lock-story --project /ABS/client
```

The note is a requirement, not decoration. Tailor affected page beats, run
`complete-template-customization`, then lock. Pass `--note ''` to clear it.
`--force` may replace only a draft created before prompts or images exist.

Personalization — habits, traits, and must-appear places/things the family gives
about the child. One habit per book owns the story arc; `lock-story` refuses to
lock until the pages prove it:

```bash
python3 tools/scripts/story_pipeline.py set-personalization \
  --project /ABS/client --json '{"habitFocus": {...}, "requests": [...]}'
python3 tools/scripts/story_pipeline.py show-personalization --project /ABS/client
```

Contract: `references/personalization.md`.

Validate catalog + workflow:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tools/tests -p 'test_*.py' -v
```

**Start here:** `references/agent-core.md` — baked multi-persona + parallel + function routing.

Key refs:

| File | Role |
|---|---|
| `agent-core.md` | Operating contract for the agent |
| `prompt-template.json` | Page prompt skeleton (multi-persona) |
| `character-sheet-template.json` | All-personas sheet |
| `location-sheet-template.json` | One empty place, multi-angle |
| `guests/catalog.json` | Vetted original guests (safe franchise stand-ins) |
| `prompt-fill-guide.md` | How to fill prompts |
| `interview.md` / `story-schema.md` / `brief-schema.md` | Contracts |
| `personalization.md` | Child habits, traits, must-appear requests |
| `story-language/age-profiles.json` | Age dictionaries, word budgets, required arc stages |
| `story-language/age-dictionaries-ar.md` | Human-readable Arabic word lists and narration style by age |
| `story-language/README.md` | Writing method, coherence gate, evidence notes |
| `story-templates/catalog.json` | Ready-made personalized adventures |

Prompt flow — the agent fills structured fields, the pipeline writes the prompt:

```bash
python3 tools/scripts/story_pipeline.py compile-prompts  --project /ABS/client
python3 tools/scripts/story_pipeline.py validate-prompts --project /ABS/client
python3 tools/scripts/story_pipeline.py generate-book-images --project /ABS/client
```

Safe guest lookup when a family asks for a famous character:

```bash
python3 tools/scripts/story_pipeline.py list-guests
python3 tools/scripts/story_pipeline.py show-guest --guest web-swinger
```
