# Feature CGI — style refs

Polished stylized **3D CGI children’s feature animation** (drawing style only).

## Refs

| File | Role |
|------|------|
| `ref-scene.png` | Full-scene look: lighting, color, depth of field, character finish |

## Apply

```bash
python3 $TOOLS/scripts/story_pipeline.py apply-theme \
  --project <ABS_CLIENT> --theme feature-cgi
```

Copies these PNGs into the client `input/style/` and sets `brief.themeId` / `visualStyle` from `themes/catalog.json`.

## Prompt rules

- Paste catalog `style.medium` / `style.finish` into every prompt JSON.
- Use `compiledPromptStyleBlock` in the style section of `compiledPrompt`.
- Match style reference images; no studio brand names in `$imagegen` prompts.
