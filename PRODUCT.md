# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Abdullah operates personalized Arabic children's-book production from Obsidian and an agent opened at this repository root.
- Friends may clone the repository and use the same workflow without installing project-specific skills globally.

## Product Purpose

Rawy is the Obsidian-first operating interface for the Hekayati production workflow. It keeps every private client/book in one local vault, exposes honest production status and next actions, and lets the agent create and update clients in the correct place.

Success means the operator can open one vault, see what needs attention, open any client, and continue production without navigating doctrine or terminal instructions.

## Positioning

Rawy turns the existing deterministic Hekayati book pipeline into a client-centered Obsidian workspace while keeping consent, story-review, image-review, and final-approval gates enforceable by code.

## Operating Context

- The agent starts at the repository root; every path in the instructions is
  relative to it.
- Obsidian opens the repository-owned `Rawy/` folder as the vault.
- One client folder represents one book/order.
- Human-visible client data is edited in Markdown properties; generated production truth comes from `output/book.json`.
- Client photos, phone numbers, stories, prompts, images, reviews, and PDFs are private local data and must remain Git-ignored.

## Capabilities and Constraints

- Arabic/English interface, RTL-first.
- No community plugins. Rawy runs on core Obsidian only: Bases, search, bookmarks, and note properties.
- Visible UI contains no doctrine, CLI runbooks, or setup instructions.
- Client identity fields stay minimal: name, phone, request description, and creation date.
- Optional operational fields: deadline, payment state, priority, blocker, and notes.
- Aggregate dashboard never exposes phone numbers.
- Existing Hekayati doctrine and production gates remain canonical.
- Existing clients may be migrated into `Rawy/Clients/` only through verified path rewriting with rollback.

## Brand Commitments

- Product name: Rawy / راوي.
- Visual direction: Forest Ledger.
- Primary surfaces: warm off-white and deep forest green `#173F35`.
- Muted mint status fields, sand details, and Cairo Arabic typography.
- Simple, calm, operational. No playful illustration system, gradients, glow, decorative dashboard clutter, or animation.

## Evidence on Hand

- Existing tested Python workflow under `tools/`.
- Existing doctrine and production state under `tools/references/`.
- Existing Rawy vault generator in `tools/scripts/rawy_vault.py`.
- No verified revenue, margin, payment, deadline, or delivery metrics may be invented.

## Product Principles

- Obsidian is the primary operator interface; the CLI stays behind the agent.
- Show source-backed status only.
- Keep private client data local and untracked.
- Preserve production gates and exact artifacts during UI changes.
- Prefer one obvious path over configurable complexity.

## Accessibility & Inclusion

- RTL and mixed Arabic/English text must remain readable.
- Status cannot rely on color alone.
- Light and dark Obsidian themes must maintain legible contrast.
