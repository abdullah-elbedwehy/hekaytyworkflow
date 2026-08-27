# Style lock (quality target)

> **Handoff §9 binds the palette.** Whatever theme is selected, the colours must
> stay print-safe on coated stock: 15–20% below default saturation, no pure
> black fills, no full-bleed deep navy, night around `#2C3E50`, no neon. The
> print-safe clause is compiled into every prompt automatically — the theme
> chooses the *look*, not permission to ignore it. And the palette is picked per
> story from that story's world, never reused as a house template (§9 P11).

Art look comes from **`brief.themeId`** → [`themes/catalog.json`](themes/catalog.json).

## Orientation lock (before anything else)

One shape for the whole book, from `book.json` → `settings.orientation`
(default `landscape`). It drives three things that used to disagree:

| Consumer | Effect |
|---|---|
| `codex-imagegen` job | requested image size (`landscape` → 1536×1024) |
| every prompt JSON | `composition.orientation`, checked by `validate-prompts` |
| `build` | PDF page size, and aspect-correct full-bleed placement |

`verify` rejects any page whose aspect drifts more than 8% from the book
orientation. Mixed aspect ratios were previously stretched onto one page size,
which is what made pages look subtly wrong next to each other.

Run `list-themes` for the full catalog — it is the source of truth and grows
over time. Every entry defines `style.medium` / `style.finish` (paste verbatim
into each prompt), a `fingerprint` that must appear in `style.medium`, and a
`textCarrierHint` describing, in that medium's material language, the in-scene
surface the page's Arabic is printed on and how the lettering should sit on it.
The model draws the words there itself, so the copy belongs to the room: it takes
that surface's angle, its light, and the theme's own hand.

Apply with:

```bash
python3 $TOOLS/scripts/story_pipeline.py apply-theme --project <ABS> --theme <themeId>
```

Theme ids come from `list-themes`. Do not hardcode them.

## Style refs (`input/style/`)

Put 1+ reference images in client `input/style/` (e.g. from theme packs under `themes/<id>/`).

Pipeline **always** attaches them on every Codex `$imagegen` call, after persona photos.

- **storybook / fairytale-glow:** optional user refs (text style from catalog)
- **cartoony / feature-cgi / enchanted-glow / wonder-trail:** `apply-theme --theme <id>` copies `themes/<id>/ref-*.png` into `input/style/`

## Target look by theme

### storybook

Premium whimsical children's **storybook digital illustration** / magical realism:

- Soft painterly textures, rich saturated color
- Cinematic multi-source lighting (cool moonlight + warm lantern/gold)
- Highly detailed joyful faces with realistic skin
- Immersive composition, print-ready
- **Not** flat cartoon, clipart, or washed flat gouache

### cartoony

Stylized **3D CGI children’s animation**, feature-film polish:

- Smooth clean surfaces, stylized hair clumps
- Large expressive glassy eyes with catchlights
- Vibrant saturated primaries, soft cinematic sunlight, shallow depth of field
- Joyful dynamic poses, print-ready
- Match style reference images in `input/style/`
- **Not** photoreal skin pores, flat 2D clipart, washed gouache
- **No** studio brand names in `$imagegen` prompts

### fairytale-glow

Classic soft **fairy-tale children’s animation illustration**:

- Rounded faces, sparkling eyes, warm golden light
- Soft painterly shading, wholesome magical mood
- **Not** photoreal, flat clipart, harsh neon
- **No** studio brand names in `$imagegen` prompts

### feature-cgi

Polished stylized **3D CGI children’s feature animation**:

- Smooth surfaces, glassy eyes, soft cinematic sunlight, shallow DOF
- Match `themes/feature-cgi/ref-*.png`
- **No** studio brand names in `$imagegen` prompts

### enchanted-glow

Whimsical stylized **3D fairy-tale night**:

- Midnight blues, glowing flora, golden sparkle dust, soft bloom
- Match `themes/enchanted-glow/ref-*.png`
- **No** studio brand names in `$imagegen` prompts

### wonder-trail

Vibrant **painterly storybook adventure**:

- Soft brush texture, golden hour, magical sparkles, wonder mood
- Match `themes/wonder-trail/ref-*.png`
- **No** studio brand names in `$imagegen` prompts

## Face refs (required)

Every generate call must include **all** persona photos from `book.json` personas (smart subset per page — see pipeline).
Missing persona file → hard error.

## Prompt lock

After theme chosen: paste catalog `style.medium` / `style.finish` into every prompt.  
`style.immutable: true` means **lock after theme chosen** — do not drift page-to-page. It does **not** mean “always storybook.”
