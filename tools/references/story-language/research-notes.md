# Story-language research notes

Research snapshot: 2026-07-19.

Purpose: derive reusable Egyptian-Arabic voice, age-fit density, and causal-story
rules for Hekayati. This document records observations and design decisions. It
is not a source-text archive.

## Inputs and method

### Local PDF review set

- `/Users/abdullah/Downloads/قصة من خير الناس.pdf`
- `/Users/abdullah/Downloads/02-أين-رحلت-الشمس؟.pdf`
- `/Users/abdullah/Downloads/نور وخروف العيد - حكايات بالعربي.pdf`
- `/Users/abdullah/Downloads/قصة يوم العيد.pdf`

Method:

1. Inspect metadata and page counts with `pdfinfo`.
2. Extract text with `pdftotext` when a usable text layer exists.
3. Render every page and read the page image when the PDF is image-only.
4. Estimate words per story page from the visible story text.
5. Trace each page's cause, action, result, location, characters, props, and
   bridge to the next page.
6. Separate useful patterns from defects; no story prose was copied into the
   reference JSON.

The two Eid PDFs are image-only. The Sun PDF has front/back matter text but its
story pages are images. Their word counts are therefore careful manual estimates,
not publisher metadata.

### Web and language-development sources

Egyptian-story source requested by the user:

- [Salam Digital: Egyptian colloquial stories](https://stories.salamdigital.com/%D9%84%D9%87%D8%AC%D8%A9/%D8%A7%D9%84%D8%B9%D8%A7%D9%85%D9%8A%D8%A9-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A%D8%A9/)

Direct Salam samples used for pattern comparison:

- [Hassan and the seed of patience](https://stories.salamdigital.com/%D8%AD%D9%83%D8%A7%D9%8A%D8%A9-%D8%AD%D8%B3%D9%86-%D9%88%D8%B2%D8%B1%D8%B9%D8%A9-%D8%A7%D9%84%D8%B5%D8%A8%D8%B1/%D8%A7%D9%84%D8%B9%D8%A7%D9%85%D9%8A%D8%A9-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A%D8%A9/)
- [Felfel and the elephant Zaezaa](https://stories.salamdigital.com/%D9%82%D8%B5%D8%A9-%D9%81%D9%84%D9%81%D9%84-%D9%88%D8%A7%D9%84%D9%81%D9%8A%D9%84-%D8%B2%D8%B9%D8%B2%D8%B9/%D8%A7%D9%84%D8%B9%D8%A7%D9%85%D9%8A%D8%A9-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A%D8%A9/)
- [Mishmish and the flying paper](https://stories.salamdigital.com/%D9%85%D8%B4%D9%85%D8%B4-%D9%88%D8%A7%D9%84%D9%88%D8%B1%D9%82%D8%A9-%D8%A7%D9%84%D8%B7%D8%A7%D9%8A%D8%B1%D8%A9/)
- [The secret of Mr Shawky's lab](https://stories.salamdigital.com/%D8%B3%D8%B1%D9%91-%D9%85%D8%B9%D9%85%D9%84-%D8%A7%D9%84%D8%A3%D8%B3%D8%AA%D8%A7%D8%B0-%D8%B4%D9%88%D9%82%D9%8A/%D8%A7%D9%84%D8%B9%D8%A7%D9%85%D9%8A%D8%A9-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A%D8%A9/)
- [The carrier-pigeon rescue](https://stories.salamdigital.com/%D8%B1%D8%AD%D9%84%D8%A9-%D8%A7%D9%84%D8%AD%D9%85%D8%A7%D9%85%D8%A9-%D8%A7%D9%84%D8%B2%D8%A7%D8%AC%D9%84%D8%A9-%D9%84%D8%A5%D9%86%D9%82%D8%A7%D8%B0-%D8%A7%D9%84%D9%82%D8%B1%D9%8A%D8%A9-%D9%85%D9%86/%D8%A7%D9%84%D8%B9%D8%A7%D9%85%D9%8A%D8%A9-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A%D8%A9/)

Developmental and language cross-checks:

- [Head Start: choosing books for infants and toddlers](https://headstart.gov/parenting/article/tips-parents-choosing-books-infants-toddlers)
- [HSE: reading with a baby and young child](https://www2.hse.ie/babies-children/checks-milestones/communication-development/reading-with-your-baby/)
- [Chapter One: story-writing guidance for ages 5-8](https://www.chapterone.org/uk/chapter-one-story-writing-guidance)
- [Arabic Communication Development Inventories](https://research.ncl.ac.uk/bulbul/forpractitioners/communicationdevelopmentinventoriescdis/)
- [AraBabyTalk-Egy corpus](https://slkh.github.io/arababytalkegy/)
- [Egyptian-Arabic expressive vocabulary study, 12-30 months](https://link.springer.com/article/10.4103/ejo.ejo_96_18)
- [ASHA communication milestones: 19-24 months](https://www.asha.org/public/developmental-milestones/communication-milestones-19-to-24-months/)
- [ASHA communication milestones: 3-4 years](https://www.asha.org/public/developmental-milestones/communication-milestones-3-to-4-years/)
- [ASHA communication milestones: 4-5 years](https://www.asha.org/public/developmental-milestones/communication-milestones-4-to-5-years/)
- [CODA conventions for Egyptian-Arabic orthography](https://www2.seas.gwu.edu/~mtdiab/files/publications/refereed/24.pdf)

The PDF branding also points to [Twinkl](https://www.twinkl.com/) and the
[Dadd Initiative](https://www.dadd-initiative.org/). Those links identify source
publishers; they do not grant reuse rights.

## PDF findings

### `قصة من خير الناس.pdf`

Structure:

- 10 PDF pages; the narrative occupies PDF pages 3-9.
- About 199 words across 7 story pages.
- About 17-45 words per page; average about 28.
- Domestic realist moral story: clothes no longer fit, the family prepares them,
  and several helping scenes follow.

Useful patterns:

- Familiar home problem.
- Direct family dialogue creates the first decision.
- Clear time/place transitions.
- Repeated core phrase supports recall.
- Text and picture usually describe the same visible action.

Defects to avoid:

- The original clothes-donation goal is never shown reaching its recipient.
- Later good deeds are thematically related but not causally necessary; removing
  one does not change the ending.
- Repeating the moral after each vignette becomes instructional rather than dramatic.
- The prose is accessible MSA, not natural Egyptian Arabic.

Derived rule: close the primary task on-page before adding a second example of
the value. Prefer a causal help chain over independent moral vignettes.

### `02-أين-رحلت-الشمس؟.pdf`

Structure:

- 27 PDF pages; the story is printed as 22 pages inside PDF pages 2-23.
- Cover label: ages 6-8.
- About 725 words across 21 text-bearing pages, plus one picture-only ending.
- About 6-72 words per text page; average about 35.
- Fantasy/science fable: discomfort leads to a wish, the wish creates escalating
  consequences, and the child regrets the decision.

Useful patterns:

- Strong central cause-and-effect spine.
- The child creates the problem through a choice.
- Consequences escalate around one goal.
- Personified nature makes concepts drawable.
- Very short visual-pause pages provide pacing relief.

Defects to avoid:

- Several pages exceed 50 words; two approach 70. This is too dense for the
  current in-image text system and uneven for the stated age.
- Talking characters often deliver textbook explanations rather than distinct dialogue.
- Ecological changes, water loss, oxygen loss, and body pain happen instantly.
- Some scientific explanations are inaccurate or overstate the sun's direct role.
- Temperature behavior across two flights is inconsistent without route context.
- The child decides to confess twice, then a dream reset removes the consequence.

Derived rule: borrow the causal spine, not the information dumps or dream reset.
Show one scientifically accurate consequence at a time and make the child repair
the real result of the choice.

### `نور وخروف العيد - حكايات بالعربي.pdf`

Structure:

- 9 PDF pages; 8 content pages.
- About 8-15 words per page; average about 12.
- Chronological opening: waking, clothes, Eid prayer, return, then a religious
  question-and-answer lesson.

Useful patterns:

- Large type, strong contrast, and one visible event per page.
- A child's concrete question opens the subject naturally.
- Repeated key terms can support recall.

Defects to avoid:

- The sheep appears without prior textual setup.
- Place and group state jump after the return journey.
- The child mainly listens; no goal, attempt, choice, or decisive action.
- A graphic slaughter image creates an abrupt emotional jump for young children.
- Abstract religious wording is much older than the visual reading level.
- The register mixes a colloquial fragment into otherwise formal prose.

Derived rule: keep fixed religious terms accurate, but build a child-led story
around them. For young profiles, avoid graphic blood and require religious and
developmental review.

### `قصة يوم العيد.pdf`

Structure:

- 9 PDF pages; 8 content pages.
- About 8-21 words per page; average about 15.
- Chronological routine: waking, dressing, waiting, visiting relatives,
  greetings, sweets, return, and gifts.

Useful patterns:

- Familiar routine and clear temporal order.
- Most pages contain one drawable activity.
- The trip returns home, providing spatial closure.
- Greeting and thanks can become imitable dialogue.

Defects to avoid:

- It is a schedule, not a causal plot; there is no problem or consequential choice.
- Good behavior is asserted by the narrator instead of shown in a difficult moment.
- The final gifts feel externally attached rather than earned by a story payoff.
- Several sentences have faulty agreement, repeated wording, or crowded dual pronouns.
- Character outfits change during the same morning, breaking visual continuity.

Derived rule: give the child one Eid goal and one small social obstacle. Show the
behavior through a choice, then let the payoff emerge from that action.

## Salam Digital Egyptian-Arabic findings

The reviewed Egyptian index contained 11 stories and about 4,391 words. Story
length ranged from about 227 to 632 words, with a median near 398. Dialogue was
about 38% of the corpus. The site does not consistently assign a target age or
picture-page layout.

Therefore Salam is useful for **voice and connectors**, not for Hekayati page
budgets.

Strong voice signals:

- Egyptian openings built around a familiar village, alley, garden, or school.
- Common forms such as `كان فيه`, `بيحب`, `دايمًا`, `عشان`, `بس`, `ليه`,
  `إزاي`, `بقى`, `استنى`, and `ما تخافيش`.
- Concrete sensory details before the problem.
- Direct dialogue, a stated want, and verbs that move the character.
- Useful causal bridges: `في يوم`, `لكن`, `فكر`, `قرر`, and `من يومها`.

Story observations:

- The Felfel story has a readable goal-plan-attempt-success line.
- The Hassan story has stronger causality than the moral PDFs, but is long and
  sometimes explains the lesson directly.
- The flying-paper story has energetic Egyptian chase language, but several
  turns depend on coincidence.
- The lab story clearly targets an older child and should not seed the youngest lexicon.
- The carrier-pigeon story has setup and payoff, but the ability required by the
  climax needs earlier training and safer adult involvement.

Recurring cautions in the sample:

- `فجأة` appeared about 15 times, `بسرعة` about 17, and `بدأ` about 22. These
  shortcuts can flatten distinct beats when overused.
- Some solutions arrive through coincidence, a sudden ability, or an unseeded helper.
- Some props and promises appear but are not closed.
- Some endings paste a lesson after the plot instead of proving it through action.
- Register sometimes drifts between Egyptian, MSA, and another Arabic dialect.

Derived rule: keep Salam's spoken rhythm, familiar settings, and direct verbs;
apply a stricter Hekayati causal and continuity gate.

## How developmental sources affected the profiles

The infant/toddler guidance supports familiar pictures, shared attention, short
language, repetition, and interactive reading. Arabic CDI and Egyptian child
language resources show that comprehension, spoken production, and age of use
must be distinguished. The ASHA pages provide a broad developmental cross-check,
not an Egyptian lexicon. CODA informs consistent spelling, but picture-book
readability can justify a small declared house style.

Chapter One's ages 5-8 guidance uses a short, simple story and roughly 300-400
words. That range fits inside the `age-6-8` recommended total of 252-432 words
for 18 interior pages. It does **not** establish Hekayati's exact per-page caps.

### Product-heuristic derivation

| Profile | Working target | Why it is set here |
|---|---:|---|
| `age-1-2` | 2-6 words/page; hard 10 | One action, repetition, caregiver read-aloud, and very large in-image type |
| `age-3-5` | 7-16 words/page; hard 22 | One or two short sentences, a simple causal beat, and one contextual new word |
| `age-6-8` | 14-24 words/page; hard 32 | Two or three short sentences, full causal arc, and legible text inside art |

The 18-page recommended totals are arithmetic products of those target ranges.
They are deliberately tighter than many continuous web stories because Hekayati
renders Arabic inside the illustration. Age five spans very different reading
abilities; use the stricter end of `age-3-5` for independent reading and the
upper end for adult read-aloud.

## Limitations

- No comprehension testing was conducted with children.
- The four PDFs use different publishers, licenses, dialects, visual styles,
  and implied age levels.
- Salam stories are continuous web prose, not fixed picture-book pages, and are
  not consistently age-labeled.
- The current age bands combine language understood, language spoken, and text
  independently read. A later evidence-backed schema should separate them.
- `age-profiles.json` is a curated starter dictionary, not corpus-certified and
  not a claim about all Egyptian children's vocabulary.
- Scientific, medical, developmental, and religious content still needs a
  qualified human reviewer for each finished story.

## Copyright and reuse note

The four PDFs and Salam pages were reviewed to identify general patterns:
sentence density, dialogue ratio, causal structure, register, page clarity, and
common failure modes. No source story should be copied, lightly paraphrased, or
used as a reusable Hekayati template.

Do not reuse source characters, distinctive plot sequences, illustrations,
page text, or memorable phrasing without verifying the exact license and
meeting all conditions. An open license on one file does not apply to another
file or to the whole website. Hekayati shared templates must remain original
and copyright-safe.
