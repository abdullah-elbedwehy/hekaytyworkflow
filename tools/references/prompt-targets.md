# Prompt targets — one page, two image tools

The structured prompt JSON is the truth about a page. What changes between
image tools is only *how that truth is phrased*, and the two tools this repo
supports want opposite phrasings. So `compile-prompts` writes one render per
target into `compiledPrompts`, and every render carries the same binding
clauses.

Read with: [prompt-rules.md](prompt-rules.md) (what a field must contain) and
[handoff.md](handoff.md) §8 and §9, which bind every target without exception.

```bash
python3 $TOOLS/scripts/story_pipeline.py compile-prompts  --project /ABS/client
python3 $TOOLS/scripts/story_pipeline.py manual-dispatch  --project /ABS/client --asset page-05
python3 $TOOLS/scripts/story_pipeline.py manual-dispatch  --project /ABS/client --asset page-05 --target nanobanana
```

---

## The two targets

| | `chatgpt` (default) | `nanobanana` |
|---|---|---|
| Model | ChatGPT / GPT Image | Nano Banana Pro (Gemini 3 Pro Image) |
| Sentence shape | short labelled clauses (`Setting: …`, `Composition: …`) | narrative paragraphs |
| Cap | 3600 chars | 5200 chars |
| Aspect ratio | set by the tool | **stated in the prompt** — `landscape 16:9 aspect ratio` |
| Constraints | positives, then a short ban list; sheds first when long | positives, then a short ban list |
| Reference clause | concise | full |

`chatgpt` stays the default, so `compiledPrompt` keeps meaning exactly what it
meant before targets existed and no project has to be recompiled to keep
working.

## What never differs

`validate-prompts` checks these on **every** render, not just the default one.
A page that is print-safe in one tool and not the other is a reprint waiting
for whichever tool gets opened that day.

- The page's approved Arabic, character for character, on its named
  `textSurface`, with the overlay ban attached — or, on a reference sheet,
  `No visible writing anywhere in this image`.
- The handoff §9 print-safe palette clause.
- `never swap identity` whenever two or more people are on the page.
- The handoff §8 I3/I6 reference-sheet rule, ending `the reference sheet wins`.
- Each render is under its own cap.

## Why the phrasing differs

**Nano Banana Pro plans a scene before it draws it.** Google's own guidance is
to write a narrative, put the non-negotiables first, and describe the result
positively. A field dump (`Foreground: …  Midground: …`) reads to it as a list
of tags; the same content as prose reads as a situation, and it composes the
situation.

**GPT Image weights the head of the prompt and drops the tail.** Short labelled
clauses in priority order survive that; prose does not, because prose has no
seam to cut on. So the labelled render is ordered by priority and sheds whole
sections — never half a sentence — until it fits.

**Negations get read as nouns.** `Avoid: malformed hands, brand logos` mostly
tells an image model that hands and logos belong in the picture. Both renders
now state the same constraints as facts about the finished image — *hands are
anatomically correct, five fingers each* — and keep the negative form only for
the handful of bans with no useful positive version (speech bubbles, drawn
panels, sticker labels).

The rewrite table lives in `prompt_targets.POSITIVE_REWRITES`. An `avoid` entry
with no rewrite is **kept**, not dropped — it just stays a ban.

## The truncation canary

Both tools silently ignore the tail of an over-long instruction, and a dropped
tail is invisible: the art still looks finished. So every `manual-dispatch`
message ends by naming one element to look for:

> - [ ] «a half-eaten date on a paper napkin» ظاهر في الصورة. لو مش موجود،
>   الأداة قصّت آخر التعليمة — ابعت الرسالة تاني كاملة من غير أي حذف.

It is deliberately the **last prop the page already requires**, never a detail
invented for the check. A hit costs nothing. A miss means the instruction was
cut, not that the picture is wrong — resend it whole rather than re-describing
the page.

## Adding a third target

1. Add a `TargetProfile` to `prompt_targets.PROFILES`.
2. If it wants a shape neither renderer produces, write the renderer and
   dispatch on `profile.shape` in `build_compiled_prompt`.
3. Nothing else. `compile-prompts` iterates `TARGETS`, `validate-prompts`
   checks every variant, and `manual-dispatch --target` accepts every id.

The one rule: a new target may change sentence shape, never content. If a
target needs a field the others do not have, that field belongs in the prompt
JSON and in [prompt-rules.md](prompt-rules.md), where every target can read it.
