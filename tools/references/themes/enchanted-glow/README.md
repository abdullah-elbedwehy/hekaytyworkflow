# Enchanted Glow — style refs

Whimsical stylized **3D fairy-tale night** illustration (drawing style only: glow, bloom, night palette).

## Refs

| File | Role |
|------|------|
| `ref-scene.png` | Night fairy-tale look: moon, sparkles, glowing flora, soft bloom |

## Apply

```bash
python3 $TOOLS/scripts/story_pipeline.py apply-theme \
  --project <ABS_CLIENT> --theme enchanted-glow
```

Copies these PNGs into the client `input/style/` and sets `brief.themeId` / `visualStyle` from `themes/catalog.json`.

## Prompt rules

- Paste catalog `style.medium` / `style.finish` into every prompt JSON.
- Use `compiledPromptStyleBlock` in the style section of `compiledPrompt`.
- Match style reference images; no studio brand names in `$imagegen` prompts.
