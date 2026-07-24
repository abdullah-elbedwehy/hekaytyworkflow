# Fairytale Glow — style only

Classic soft **fairy-tale children’s animation illustration** (drawing style only — no scene content lock).

No `ref-*.png` pack (text style from `catalog.json` like `storybook`).

## Apply

```bash
python3 $TOOLS/scripts/story_pipeline.py apply-theme \
  --project <ABS_CLIENT> --theme fairytale-glow
```

## Prompt rules

- Paste catalog `style.medium` / `style.finish` into every prompt JSON.
- Use `compiledPromptStyleBlock` in the style section of `compiledPrompt`.
- No studio brand names in `$imagegen` prompts.
