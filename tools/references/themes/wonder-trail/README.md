# Wonder Trail — style refs

Vibrant **painterly children’s storybook adventure** illustration (drawing style only).

## Refs

| File | Role |
|------|------|
| `ref-scene.png` | Painterly look: brush texture, golden hour, sparkles, adventure mood |

## Apply

```bash
python3 $TOOLS/scripts/story_pipeline.py apply-theme \
  --project <ABS_CLIENT> --theme wonder-trail
```

Copies these PNGs into the client `input/style/` and sets `brief.themeId` / `visualStyle` from `themes/catalog.json`.

## Prompt rules

- Paste catalog `style.medium` / `style.finish` into every prompt JSON.
- Use `compiledPromptStyleBlock` in the style section of `compiledPrompt`.
- Match style reference images; no studio brand names in `$imagegen` prompts.
