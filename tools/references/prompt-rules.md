# Prompt rules — the ultra-detail contract

Binding rules for the model that fills `input/prompts/*.json`. `validate-prompts`
enforces most of them mechanically (`tools/scripts/promptdepth.py`); the rest are
enforced by the reviewers. A prompt that clears this bar renders right the first
time, and first-time-right is the entire speed strategy — a regenerated page
costs more than an hour of careful writing.

Read with: [prompt-fill-guide.md](prompt-fill-guide.md) (which field goes where)
and [agent-core.md](agent-core.md) (routing and parallel rules). The rulebook
above all of them is [handoff.md](handoff.md).

---

## Rule 0a — two handoff rules bind every single prompt

**Shape (handoff §8 I5).** Landscape 16:9, always. One orientation for the whole
book. Never portrait unless Omar says so explicitly, and never a split frame:
one scene is one image.

**Colour (handoff §9).** The book prints Rich Coverage on coated stock.
`compile-prompts` inserts the print-safe clause into every prompt at a priority
the length-shedding pass never drops, and `validate-prompts` rejects a compiled
prompt that lost it. What that means for the palette you write:

- desaturate roughly 15–20% below the default you first reach for
- no pure black (`#000000`) fills — use a warm dark grey or brown
- no full-bleed deep navy or heavy saturated dark field; break any large dark
  area with a gradient, a texture, or lighter accents
- night scenes sit around `#2C3E50`, not `#0A1633`
- warm practical lights stay the brightest point without orange/yellow blowout
- natural mid-saturation skin and clothing, no neon

The palette itself is chosen from **this story's** world. It is not a house
template reused between books (handoff §9 P11).

---

## Rule 0 — the stranger test

> A person who has never read the story, holding only this JSON and the
> reference photos, must be able to draw the page and get the same picture the
> story needs.

Every rule below is a special case of that one. When unsure whether a field is
finished, ask what that stranger would have to invent. Whatever they invent, the
image model invents too — differently on every page.

---

## Rule 1 — name the thing, never the category

The failure is not short writing. It is writing that describes a *class* of
object instead of one object.

| ✗ Category | ✓ Thing |
|---|---|
| `a table` | `a low pine table, one leg shorter, ring stains near the edge` |
| `morning light` | `low sun from the left window, warm gold, long soft shadows` |
| `a toy` | `a blue sponge ball, compressed in his fist` |
| `a nice kitchen` | `a narrow kitchen with mint-green tiles to waist height, a chipped enamel sink, a hanging brass pot` |
| `مكان جميل` | `شرفة خشبية بشيش تركوازي فوق شارع بيطل على البحر` |

Mechanical consequence: `scene.place`, `scene.foreground`, `scene.midground`
must each name a **material**; `scene.lighting` must name a **direction** and a
**temperature**; `fixedOutfits` must name a **colour**.

---

## Rule 2 — banned vocabulary

These words feel descriptive and commit to nothing. `validate-prompts` rejects
any field containing them.

**English** — nice, beautiful, pretty, lovely, amazing, wonderful, detailed,
highly detailed, intricate, various, some, several, many, etc, appropriate,
suitable, fitting, typical, normal, generic, standard, classic, stuff, things,
objects, elements, background elements, atmospheric, moody, interesting,
dynamic, epic, stunning, masterpiece, best quality, high quality, 4k, 8k.

**Arabic** — جميل/جميلة، حلو/حلوة، رائع/رائعة، مناسب/مناسبة، عادي/عادية، بعض،
أشياء، حاجات، مميز/مميزة، تفاصيل كثيرة.

`masterpiece`, `4k`, `best quality` are worse than useless here: they are
tag-soup habits from a different generation of models, and they push the image
toward stock-render polish and away from the theme's illustration style.

---

## Rule 3 — word floors per field

Below these counts the field cannot carry a specific thing. `validate-prompts`
reports the actual count when a field is short.

| Field | Min words | Must also name |
|---|---|---|
| `narrativeBeat` | 6 | — |
| `primaryRequest` | 6 | — |
| `scene.place` | 6 | a material |
| `scene.timeOfDay` | 4 | a light quality |
| `scene.lighting` | 8 | direction **and** colour |
| `scene.atmosphere` | 5 | — |
| `scene.foreground` | 8 | material **and** colour |
| `scene.midground` | 8 | a material |
| `scene.background` | 7 | — |
| `scene.backdropDetails` | 12 | — |
| `identityLocks.<persona>.face` | 6 | — |
| `identityLocks.<persona>.hair` | 4 | — |
| `fixedOutfits.<persona>` | 6 | a colour |
| `actionAndEmotion.<persona>.action` | 6 | — |
| `actionAndEmotion.<persona>.emotion` | 4 | — |
| `palette` | 4 | a colour |

`scene.propsInFrame`: **3+ entries** on a story page, and every entry needs a
colour **and** either a material or a state (`half-eaten`, `chipped`, `rusted`).
The state is what makes a prop the *same* prop on the next page.

Sheets are scored on the subset that applies: a character sheet owes identity,
outfits, lighting, and palette — not a background, because inventing scenery on
the sheet is how it ends up contradicting the location sheets. A location sheet
owes the place and nothing about people.

---

## Rule 4 — the score

Every prompt gets a 0-100 depth score. **Pages must reach 80, sheets 70.**
`validate-prompts` prints the three weakest prompts on success so the next pass
knows where to spend effort. Below the floor, it blocks and names each field.

The weights say what matters: identity locks and lighting are the heaviest,
because a drifted face or an inconsistent light source is what a family notices
and what forces a regeneration. Background depth is the lightest.

Override for a deliberate exception:

```bash
python3 $TOOLS/scripts/story_pipeline.py validate-prompts --project <ABS> --min-depth 70
```

Lowering it is a decision to accept more regenerations. It is not a shortcut.

---

## Rule 5 — precision fields (new, strongly recommended)

Warned, not blocked — but they are the cheapest quality left on the table:

- **`composition.lens`** — `35mm-equivalent, slight wide, no edge distortion`.
  Without it every page reads as one camera bolted to a tripod for the whole book.
- **`composition.depthOfField`** — what is sharp, what falls soft. This is what
  separates a photograph of a scene from an illustration with a subject.
- **`colorScript`** — how this beat leans the *existing* palette warmer, cooler,
  or more saturated, and why the beat calls for it. Never a new palette; the
  palette is locked once in story continuity and the colour script only
  emphasises within it.

---

## Rule 6 — variety across pages, not just inside one

`validate-prompts` fails two adjacent interior pages that share both
`composition.shotScale` and `composition.viewpoint`. Same scale plus same
viewpoint reads as one drawing printed twice, no matter how different the
content is.

Plan the shot rhythm across the whole book before writing page one: a wide
establishing beat, a medium two-shot, a close on hands, a low angle for the
moment the child decides. The arc stages in `story.json` already tell you where
the emphasis belongs.

---

## Rule 7 — continuity is a field, not a hope

From `page-02` onward, `continuity.fromPreviousPage` must name what each
returning person still wears, holds, or carries. Five words minimum, and it must
be specific enough to check: `still carries the blue sponge ball from the yard`,
not `same as before`.

`continuity.recurringProps` and `continuity.propStates` carry the objects that
appear across several pages and what condition each is in right now.

---

## Rule 8 — text never enters the art

The Arabic is **not** painted into the illustration. `build` draws it as a real
PDF text layer, so:

- Every page prompt carries the text-free clause (the compiler adds it).
- The bottom band stays calm and low-detail — no faces, hands, or key action.
- No drawn box, band, or panel under the caption area.
- The story text must never appear anywhere in `compiledPrompt`.

All four are enforced. The reason the ban is total rather than "no caption": an
image model given any excuse to draw a sign, a poster, or a book cover will
render malformed Arabic on it.

---

## Rule 9 — copyright-safe guests, described not named

Franchise characters are replaced by an archetype from `list-guests`, pasted
verbatim into `guests[]`. Never the real name, in Latin or Arabic, in any field.
Descriptions under 120 characters are rejected — vagueness is exactly what
triggers a model refusal.

---

## Rule 10 — write all prompts in one pass

After `lock-story`, write **every** prompt file before running anything:
character sheet, one location sheet per declared location, then every PDF page.
Then one `compile-prompts`, one `validate-prompts`. Dripping prompts page by
page turns a single validation round into twenty.

Then run `preflight` once — it collapses the environment check, the story review,
the compile, and the validation into a single verdict listing *everything*
wrong at once, instead of surfacing one failure per round trip.

---

## Self-check before you hand the folder over

- [ ] Every field passes the stranger test.
- [ ] Zero banned words, English and Arabic.
- [ ] Every prop names a colour and a material or state.
- [ ] Lighting names a direction and a temperature on every asset.
- [ ] Each on-page persona has their own face lock, outfit, action, and emotion.
- [ ] No two adjacent pages share scale **and** viewpoint.
- [ ] `continuity.fromPreviousPage` is filled from `page-02` on.
- [ ] `lens`, `depthOfField`, `colorScript` filled on every page.
- [ ] `preflight` returns `ok: true`.
