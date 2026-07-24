# Cartoony theme — style refs

Polished stylized **3D CGI children’s animation** (not flat 2D clipart).

## Refs

| File | Role |
|------|------|
| `ref-scene-3d.png` | Full-scene look: lighting, color, depth of field, character finish |
| `ref-portrait-pair.png` | Face/likeness target for photo → illustrated cartoony conversion |

## Apply to a client project

```bash
python3 $TOOLS/scripts/story_pipeline.py apply-theme \
  --project <ABS_CLIENT> --theme cartoony
```

Copies these PNGs into the client `input/style/` and sets `brief.themeId` / `visualStyle` (and `story.json` if present) from `themes/catalog.json`.

Pipeline attaches every file under `input/style/` on Codex `$imagegen` calls after persona photos.

## Prompt rules

- Paste catalog `style.medium` / `style.finish` into every prompt JSON.
- Use `compiledPromptStyleBlock` in the style section of `compiledPrompt`.
- No studio brand names in `$imagegen` prompts.
