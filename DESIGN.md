---
name: "Rawy / راوي"
description: "A calm, bilingual production ledger for personalized Arabic books."
colors:
  forest: "#173f35"
  forest-deep: "#0f3028"
  forest-soft: "#2f6f5c"
  paper: "#f6f5ef"
  raised-paper: "#fffdf7"
  mint: "#dcebe3"
  sand: "#d8c8a4"
  ink: "#17211d"
  muted-ink: "#596860"
  faint-ink: "#76827c"
  forest-border: "rgba(23, 63, 53, 0.14)"
  on-forest: "#f6faf7"
  night: "#101c18"
  night-raised: "#172b24"
  night-mint: "#24483b"
  night-sand: "#8d7c58"
  night-ink: "#edf4f0"
  night-muted: "#b4c7bd"
  night-accent: "#9acbb5"
typography:
  display:
    fontFamily: "Rawy Cairo, SF Arabic, sans-serif"
    fontSize: "clamp(2.6rem, 6vw, 4.8rem)"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Rawy Cairo, SF Arabic, sans-serif"
    fontSize: "clamp(1.35rem, 2vw, 1.75rem)"
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: "Rawy Cairo, SF Arabic, sans-serif"
    fontSize: "17px"
    fontWeight: 400
  label:
    fontFamily: "Rawy Cairo, SF Arabic, sans-serif"
    fontSize: "0.82rem"
    fontWeight: 600
  stat-value:
    fontFamily: "Rawy Cairo, SF Arabic, sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1
rounded:
  ticket: "12px"
  surface: "14px"
spacing:
  compact: "12px"
  inset-y: "14px"
  inset: "16px"
  phrase: "18px"
  cluster: "24px"
  section: "48px"
  wide: "64px"
  page-end: "80px"
components:
  lead-callout:
    backgroundColor: "{colors.forest}"
    textColor: "{colors.on-forest}"
    typography: "{typography.body}"
    rounded: "{rounded.surface}"
    padding: "16px 18px"
    width: "min(100%, 720px)"
  stat-card:
    backgroundColor: "{colors.raised-paper}"
    textColor: "{colors.forest-soft}"
    rounded: "{rounded.surface}"
    padding: "14px 16px"
    height: "112px"
  client-card:
    backgroundColor: "{colors.mint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.ticket}"
  base-container:
    backgroundColor: "{colors.raised-paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    width: "100%"
  progress-panel:
    backgroundColor: "{colors.forest}"
    textColor: "{colors.on-forest}"
    rounded: "{rounded.surface}"
  action-panel:
    backgroundColor: "{colors.mint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
  blocker-panel:
    backgroundColor: "color-mix(in srgb, {colors.sand} 42%, transparent)"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
---

# Design System: Rawy / راوي

## Overview

**Creative North Star: "The Forest Ledger"**

Rawy is a calm production ledger built from deep forest green, warm paper, mint, and sand. It feels like a working studio record rather than a generic SaaS dashboard or a decorative children's scrapbook: operational information is compact, legible, and visibly ordered, while the materials stay warm enough for a story-production setting.

The interface is RTL-first and bilingual, with Cairo carrying both Arabic and English. The dashboard tells one ordered story: the Rawy wordmark and working sentence establish purpose, studio totals show the pulse, attention comes before the active-client list, and the complete ledger follows. Light and dark themes preserve that hierarchy by remapping surfaces and text rather than changing the visual language.

**Key Characteristics:**

- Forest-led warm neutrals with mint and sand reserved for operational meaning.
- A large, compact Cairo wordmark above dense, work-oriented content.
- Raised ledger surfaces, small production tickets, and restrained ambient depth.
- Bilingual labels that remain readable in an RTL-first workspace.
- One obvious path from studio pulse to attention to a client record.

## Colors

The palette pairs authoritative forest green with warm paper and low-chroma status materials; dark mode translates those same roles into deep green-black surfaces rather than introducing a new hue family.

### Primary

- **Ledger Forest:** The main authority color for the wordmark, lead panel, progress panels, and strong interactive emphasis.
- **Deep Forest:** The darker workspace-chrome companion used where the forest surface needs separation.
- **Working Green:** The link, stat-value, and active accent that carries action without becoming bright or decorative.

### Tertiary

- **Quiet Mint:** The calm action and client-card surface; it signals work that can proceed.
- **Studio Sand:** The blocker material; its warmth marks friction without turning the interface into an alarm display.

### Neutral

- **Warm Paper:** The primary light canvas.
- **Raised Paper:** Cards and ledger containers above the paper canvas.
- **Ledger Ink:** Primary light-theme text.
- **Muted Ink:** Labels, table headings, and supporting metadata.
- **Faint Ink:** Low-emphasis workspace text.
- **Night:** The dark-theme canvas.
- **Night Raised:** Raised cards in dark mode.
- **Night Ink / Night Muted:** High- and supporting-contrast text for dark mode.

### Named Rules

**The Forest Authority Rule.** Forest owns hierarchy and action; mint and sand explain operational state but never compete with it as general accents.

**The Theme Translation Rule.** Dark mode remaps material roles—canvas, raised paper, mint, sand, ink—without changing the information hierarchy or adding a new accent family.

**The Status Has Words Rule.** Color supports statuses, but bilingual status labels and explicit headings carry the meaning.

## Typography

**Display Font:** Rawy Cairo (with SF Arabic and sans-serif fallback)

**Body Font:** Rawy Cairo (with SF Arabic and sans-serif fallback)

**Character:** One Arabic-first family gives the ledger a steady, unified voice across Arabic, English, data, headings, inputs, and controls. Hierarchy comes from scale, weight, and compact spacing rather than a decorative type pairing.

### Hierarchy

- **Display:** A bold, tightly tracked, one-line wordmark used only for the dashboard identity; it scales fluidly and settles at 2.6rem on narrow screens.
- **Headline:** A compact section title for attention, active, and complete-client groupings.
- **Body:** The 17px workspace baseline for bilingual reading and operating text.
- **Label:** A semibold supporting role for stat names and metadata.
- **Stat Value:** A bold 2rem value with unit line-height for quick studio scanning.

### Named Rules

**The One Family Rule.** Cairo carries the interface end to end; hierarchy is made with scale and weight, not with an ornamental second face.

**The Bilingual Pair Rule.** Arabic leads human-facing labels, English follows after a slash or on the paired line, and neither language is reduced to decorative microcopy.

## Layout

The dashboard uses a centered reading surface capped at 1120px, with fluid inline padding from 24px to 64px and 80px of closing space. Its first viewport is linear and deliberate: identity, working sentence, five studio totals, attention, active clients, then the complete ledger. Section headings begin on a 48px vertical interval, keeping operational blocks distinct without turning them into isolated dashboard islands.

Studio totals form a five-column row with 12px gaps. At 820px they become two columns with the final item spanning the row; at 520px they become a single column and the page inset contracts to 18px. Client detail pages use a narrower 860px reading measure. Bases containers may scroll horizontally rather than compressing table content below readability.

**The Pulse-Before-Queue Rule.** Studio totals stay together immediately after the working sentence, and the attention queue stays ahead of all-client browsing.

**The Ledger Width Rule.** Wide overview data uses the 1120px dashboard measure; individual client work uses the quieter 860px measure.

## Elevation & Depth

Rawy is flat by default and uses one restrained ambient shadow only for raised callouts and ledger containers. Light mode uses a green-tinted shadow; dark mode uses a slightly deeper neutral shadow. Lead, empty, client-card, progress, action, and blocker surfaces rely on tonal contrast instead of elevation.

### Shadow Vocabulary

- **Ledger Raise** (`0 10px 28px rgba(23, 63, 53, 0.08)`): Low ambient lift for light-theme stat cards, general callouts, and Bases containers.
- **Night Ledger Raise** (`0 12px 30px rgba(0, 0, 0, 0.2)`): The same structural role on the dark canvas.

### Named Rules

**The One-Level Rule.** Use a single ambient elevation level for structural surfaces; operational state panels remain shadowless.

## Shapes

The form language is softly rectangular and ledger-like. Major surfaces and callouts use a 14px radius; compact client tickets use 12px. Borders are thin and forest-tinted only where a container boundary is needed, while color-filled callouts carry no border. There are no pills, ornamental cutouts, or playful silhouettes.

**The Two-Radius Rule.** Use 14px for structural surfaces and 12px for compact tickets; do not add arbitrary intermediate radii.

## Components

### Lead Callout

- **Character:** A concise working sentence on solid forest, not a promotional hero.
- **Shape:** A 14px rounded rectangle, capped at 720px.
- **Color:** Forest background with near-white text.
- **Treatment:** Shadowless, borderless, and free of callout title chrome or icons.

### Stat Cards

- **Character:** Compact production tickets that scan as one studio pulse.
- **Shape:** A 14px raised surface with a 112px minimum height and compact inset.
- **Color:** Raised paper with muted labels and working-green values; dark mode uses night-raised surfaces and a pale green value.
- **Treatment:** The full card stretches to the row height, while the value sits 14px below its label.

### Client Cards / Bases

- **Character:** Dense records, not marketing cards.
- **Shape:** Client tickets use 12px corners; the enclosing Bases surface uses 14px corners.
- **Color:** Tickets use quiet mint; the enclosing ledger uses raised paper.
- **Treatment:** Tickets are flat and borderless. The enclosing Bases view receives the system's one ambient elevation and a faint forest border.

### Client State Panels

- **Progress:** Solid forest with near-white text.
- **Next Action:** Quiet mint with ledger ink.
- **Blocker:** A 42% sand tint mixed with transparency, always paired with explicit blocker text.
- **Treatment:** All three use the structural 14px radius and remain shadowless.

### Tables and Links

- **Tables:** Body rows remain compact; headers use smaller semibold muted text.
- **Links:** Working green, semibold, with a one-pixel underline offset by 3px.
- **Overflow:** Tables scroll horizontally when the available width cannot preserve readable fields.

## Do's and Don'ts

### Do:

- **Do** preserve the dashboard story: wordmark and working sentence, studio pulse, attention, active clients, then the complete ledger.
- **Do** use forest for authority, mint for actionable calm, and sand for blockers.
- **Do** keep Arabic first and English visibly paired in operational labels.
- **Do** preserve the five-to-two-to-one stat-grid behavior across desktop, tablet, and phone widths.
- **Do** use text as the source of status meaning and color as reinforcement.

### Don't:

- **Don't** turn Rawy into a generic SaaS dashboard with competing accent colors or equal-weight card islands.
- **Don't** add playful illustration, gradients, glow, decorative dashboard clutter, or ornamental type.
- **Don't** use shadow to communicate status; status surfaces are tonal and explicitly labeled.
- **Don't** expose hidden properties, phone numbers, production doctrine, or terminal instructions in overview surfaces.
- **Don't** invent a third corner radius or a second elevation level without an observed reusable need.
