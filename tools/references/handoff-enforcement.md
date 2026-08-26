# Handoff → enforcement map

Every rule in [`handoff.md`](handoff.md) and where it is actually enforced.
A rule with **no machine gate** is a human-judgement rule — it lives in the
review rubrics and the vault checklists, and the reviewers are expected to catch
it. Do not pretend it is automated.

Machine-readable rulebook: [`handoff/doctrine.json`](handoff/doctrine.json).
Loader and checks: `tools/scripts/doctrine.py`.

```bash
python3 tools/scripts/story_pipeline.py show-doctrine
python3 tools/scripts/story_pipeline.py check-doctrine --project /ABS/CLIENT
```

`review-story`, `prepare-story-review`, `complete-template-customization`,
`lock-story`, and `preflight` all include the doctrine verdict, so there is no
way to reach images with a doctrine error open.

## §1 Response style

| Rule | Enforced by |
|---|---|
| نص القصة عربي مصري فقط | `review-story` → `wrong-language-register` + age dictionaries |
| مفيش برومبت قبل الموافقة الصريحة | the permanent Markdown review gate: `prepare-story-review` → `approve-story-review` → `lock-story` |
| مفيش أكتر من صفحة في رسالة توليد | `manual-dispatch` — one instruction per message, `maxPagesPerFile = 2` |
| مفيش تقسيم لقطات من غير اتفاق | `manual-dispatch` prints «مشهد واحد = صورة واحدة» in every block |

## §2 Literal language (highest priority)

| ID | Enforced by |
|---|---|
| L1 مجاز للمشاعر | `doctrine.text_errors` → `doctrine-literal-metaphor` (patterns `MP-*`) |
| L2 المشاعر مباشرة | same patterns; «أخد مكانه» is explicitly allowed |
| L3 حل بفعل ملموس | **human** — story rubric |
| L4 مفيش حكمة | `doctrine-wisdom-quote` (`WP-*`), partial; the rest is human |

The scanner folds diacritics, hamza, and ta-marbuta first, so `قلبُه بقي` is
caught exactly like `قلبه بقى`.

## §3 Narrative structure

| ID | Enforced by |
|---|---|
| N1 جملة الجسر | `review-story` → `unbridged-scene-cut` (needs a real causal/movement bridge visible in the page text) |
| N2 خطاب مباشر | **human** — story rubric |
| N3 مفيش مشهد حشو | `review-story` → duplicate beat/text checks; expansion gaps stay empty rather than auto-filled |
| N4 مكافأة مستحقة | `doctrine-unearned-reward` (`UR-role-based`) + human |
| N5 الرفيق يتفاعل | **human** — story rubric |
| N6 وعد الأهل يتحقق | **human** — story rubric (Setup → Payoff) |
| N7 مكان صفحة اللعبة | **human** — story rubric |
| N8 علامة خارجية | **human** — story rubric |

## §4 Cultural constraints

| ID | Enforced by |
|---|---|
| C1 نفس نوع البطل | `doctrine.cultural_errors` → `mixed-gender-friend-group` (needs `persona.gender` on hero + friends) |
| C2 لعب مختلط | **human** — story rubric |
| C3 مشاركة أكل شخصية | `doctrine-personal-food-sharing` (`FS-*`) |

## §5 Story types

| Rule | Enforced by |
|---|---|
| `storyType` مطلوب | `missing-story-type` |
| النوع يطابق `storyGoal.mode` | `story-type-goal-mismatch` |
| Type A رفيق سحري | `missing-magical-companion` |
| Type A انتكاسة | `missing-relapse-beat` (needs a `setback` stage) |
| Type B بدون رفيق سحري | `forbidden-magical-companion` |
| Type C شخصيات أصلية | `validate-prompts` franchise-name scan + `guests/catalog.json` |

Set it with `set-story-type --type A|B|C`.

## §6 Dialect

| Rule | Enforced by |
|---|---|
| ماما/بابا مش أمه/والده | `doctrine.register_replacements` → `age-language-term` (high = blocking) |
| ضحكة مش ضحك | same, medium = warning |
| بكده مش وهكذا | same, high |
| صحيت مش استيقظت | age-profiles `registerReplacements` |
| ظروف حشو | same, low = warning |
| اتساق الضمائر · «طب» · «اوي اوي» | **human** — arabic rubric |

## §7 Book structure

| Rule | Enforced by |
|---|---|
| 24 صفحة PDF | `wrong-book-length`; `DEFAULT_PDF_PAGES` reads the doctrine |
| 20 صفحة قصة بالظبط | `story-page-count` |
| صفحات البنية موجودة | `missing-structural-page` |
| نص الإهداء ثابت | `dedication-text-drift` — write it with `apply-fixed-pages` |
| نص الغلاف الخلفي ثابت | `back-cover-text-drift` |
| 5 أيقونات | doctrine load-time check (exactly five) |
| قاعدة الدمج | `story-page-count` + `unwritten-story-page` for expansion gaps |

Fixed pages are excluded from the age word budget and the register check — their
copy is Omar's, not the author's — and from the causal spine, because they carry
no story beat.

## §8 Image tool

| ID | Enforced by |
|---|---|
| I1 self-contained | `manual-dispatch` renders one complete message per page |
| I2 نص عربي غير موثوق | art is text-free; `validate-prompts` rejects a prompt missing the clause or leaking the story text |
| I3 Reference Sheet في كل رسالة | `manual-dispatch` always prints the clause and an attachment row (⚠️ if the sheet path is unknown) |
| I4 مفيش multi-shot | printed in every block |
| I5 Landscape 16:9 | `settings.orientation` + `validate-prompts` + `verify` reject off-ratio |
| I6 مطابقة الشيت تكسب | printed verbatim in every block |
| I7 صفحة واحدة لكل رد | `manual-dispatch` refuses a file with more than two pages |
| I8 شيتات الشخصيات | `render_character_sheet_instruction` lists the four angles |
| ألعاب: متاهة / دور على حاجات | **human** — the agent writes every element; no generator yet |

## §9 Print-safe colour

| Rule | Enforced by |
|---|---|
| كل برومبت فيه جملة الألوان | `build_compiled_prompt` adds it at a priority the length-shedding pass never drops; `validate-prompts` rejects a prompt without it |
| Ink limit / GCR / TAC | **human** — pre-print checklist in the vault |
| K-only text | the PDF text layer is drawn K-only by the builder; verify in Acrobat |

## What is deliberately not automated

- Whether an emotional resolution is a real event (L3)
- Whether reassurance sounds like a person or a proverb (L4, partly)
- Whether a scene is filler borrowed from another book (N3, partly)
- Whether mixed play reads as normal and repeated (C2)
- Whether a game page sits where the action actually is (N7)
- Ink limit, GCR, and TAC verification in Acrobat

These belong to the reviewers and to
`vault/01-Checklists/`. Adding a weak regex for them would be worse than
admitting they are human calls.
