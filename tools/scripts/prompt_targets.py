"""Compile one image prompt per target model.

The structured prompt JSON is the single source of truth for a page. What
changes between image tools is only *how that truth is phrased*, and the two
tools Omar actually uses want opposite phrasings:

* **ChatGPT / GPT Image** reads short labelled clauses well and drops the tail
  of a long prompt, so the compiled string is ordered by priority and bounded.
* **Nano Banana Pro (Gemini 3 Pro Image)** plans a scene before drawing it. It
  reads a narrative paragraph better than a tag list, it wants the
  non-negotiables stated first, and it follows a *positive* description far
  more reliably than a list of things to avoid — a negation list mostly teaches
  it which nouns belong in the picture.

So both renderers read the same fields and emit the same binding clauses
(the page's exact Arabic on its named surface, print-safe palette, identity
locks, reference-sheet rule); they
differ in sentence shape and in how the `avoid` list is expressed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import doctrine


class TargetError(ValueError):
    pass


@dataclass(frozen=True)
class TargetProfile:
    """How one image model wants to be talked to."""

    id: str
    label: str
    max_chars: int
    shape: str  # "labelled" | "narrative"
    aspect_ratio_in_prompt: bool
    note: str


PROFILES: dict[str, TargetProfile] = {
    "chatgpt": TargetProfile(
        id="chatgpt",
        label="ChatGPT / GPT Image",
        max_chars=3000,
        shape="labelled",
        aspect_ratio_in_prompt=False,
        note=(
            "Short labelled clauses, non-negotiables first. The tail of a long "
            "prompt gets ignored, so the compiler sheds optional sections."
        ),
    ),
    "nanobanana": TargetProfile(
        id="nanobanana",
        label="Nano Banana Pro (Gemini 3 Pro Image)",
        max_chars=3600,
        shape="narrative",
        aspect_ratio_in_prompt=True,
        note=(
            "Narrative paragraphs, positive phrasing, explicit aspect ratio and "
            "an explicit 'use only the attached references' directive."
        ),
    ),
}

# The compiled prompt's overlay ban and its validator have drifted apart twice
# now — once wording changed, `validate-prompts` started failing every page in
# the project. Both sides read these, so a rewording cannot break the gate.
OVERLAY_BAN_MARKER = "no overlay"
GAME_PLAYABILITY_MARKER = "solvable exactly as drawn"

TARGETS: tuple[str, ...] = tuple(PROFILES)
DEFAULT_TARGET = "chatgpt"


def profile(target: str) -> TargetProfile:
    try:
        return PROFILES[str(target)]
    except KeyError:
        raise TargetError(
            f"Unknown image target {target!r}; expected one of {', '.join(TARGETS)}"
        ) from None


# ---------------------------------------------------------------------------
# Field cleaners — shared by both renderers.
# ---------------------------------------------------------------------------


def clean(value: Any) -> str:
    """Collapse a field to a single clean line, or empty if it's a CHANGE stub."""
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split()).strip(" .")
    if not text or text.upper().startswith("CHANGE"):
        return ""
    return text


def clean_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = clean(item)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def join_sentences(parts: Iterable[str]) -> str:
    """Join field fragments as real sentences, not lowercase run-ons."""
    out: list[str] = []
    for part in parts:
        text = part.strip() if isinstance(part, str) else ""
        if not text:
            continue
        out.append(text[0].upper() + text[1:])
    return ". ".join(out) + "." if out else ""


# ---------------------------------------------------------------------------
# Negation → positive constraint.
# ---------------------------------------------------------------------------

# Every `avoid` entry the templates ship, rewritten as the thing that SHOULD be
# true. Matched on a lowercased substring so a hand-edited variant still lands.
# What has no rewrite stays a hard ban: a few bans really are bans, and both
# models honour a short one.
POSITIVE_REWRITES: tuple[tuple[str, str], ...] = (
    ("extra people", "only the people named above are in the frame, and nobody else"),
    ("identity swap", "each person keeps their own face, hair, and outfit throughout"),
    ("identity drift", "every face stays identical to its reference sheet"),
    ("outfit drift", "every outfit stays identical to the fixed outfit named above"),
    ("malformed hands", "hands are anatomically correct, five fingers each, fully drawn"),
    ("empty vague scenes", "every layer of the frame carries a named, specific object"),
    ("franchise character names", "every character design is original"),
    ("brand logos", "every garment, product, and surface is plain and unbranded"),
    ("trademark emblems", "every garment, product, and surface is plain and unbranded"),
    ("watermarks", "the image is clean, with no overlay of any kind"),
    ("living-artist imitation", "the style comes only from the style description above"),
)

# The writing rewrites depend on whether the page carries copy at all, so they
# live apart from the table above. A page with copy must not be told that every
# surface is blank — that pair is what came back with the Arabic missing. A
# reference sheet has no copy and must be told exactly that.
TEXT_REWRITE_NEEDLES: tuple[str, ...] = (
    "mirrored arabic",
    "cropped text",
    "extra letters",
    "latin text",
    "numbers unless required",
)
TEXT_REWRITE_WITH_COPY = (
    "the only writing anywhere in the frame is the Arabic copy named above, "
    "right-to-left with joined letters and no letter clipped by its surface"
)
TEXT_REWRITE_WORDLESS = "every surface in the frame is blank and wordless"

# These stay phrased as bans because there is no useful positive form: the
# model has to be told the panel/box/bubble furniture of comics is absent.
HARD_BAN_HINTS: tuple[str, ...] = (
    "text box",
    "text boxes",
    "sticker",
    "speech bubble",
    "panel",
    "split frame",
)


def positive_constraints(
    avoid: Iterable[Any], *, has_copy: bool = False
) -> tuple[list[str], list[str]]:
    """Split an `avoid` list into positive statements and residual hard bans.

    ``has_copy`` says whether this asset carries `inImageText`. It only changes
    the writing-related rewrites, and it has to: telling a page with copy that
    every surface is blank is the contradiction that used to come back as a
    beautiful illustration with no story text on it.
    """
    text_rewrite = TEXT_REWRITE_WITH_COPY if has_copy else TEXT_REWRITE_WORDLESS
    positives: list[str] = []
    bans: list[str] = []
    for raw in avoid or []:
        text = clean(raw)
        if not text:
            continue
        lowered = text.lower()
        rewrite = next(
            (positive for needle, positive in POSITIVE_REWRITES if needle in lowered),
            "",
        )
        if not rewrite and any(needle in lowered for needle in TEXT_REWRITE_NEEDLES):
            rewrite = text_rewrite
        if rewrite:
            if rewrite not in positives:
                positives.append(rewrite)
            continue
        if text not in bans:
            bans.append(text)
    return positives, bans


# ---------------------------------------------------------------------------
# Reference-image directive (handoff §8 I3 + I6, in English for the prompt).
# ---------------------------------------------------------------------------


def reference_directive(payload: Mapping[str, Any], *, concise: bool = False) -> str:
    """Name the attached references and forbid re-deriving the face.

    handoff §8 I3 says the accepted character sheet rides on every generation
    message, and I6 says the sheet wins over the photo. Both lived only in the
    Arabic manual lane; a compiled prompt that omits them lets the model reach
    for the last image it made, which is exactly how identity drifts.

    ``concise`` trims it for the labelled lane, where a 380-character clause in
    the middle of the prompt pushes the constraint tail past the cap.
    """
    roles: list[str] = []
    raw = payload.get("inputImages")
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, Mapping):
                continue
            if not clean(entry.get("path")):
                continue
            role = clean(entry.get("role")) or "reference"
            if role not in roles:
                roles.append(role)
    attached = ", ".join(roles) if roles else "character sheet and persona photos"
    if concise:
        return (
            f"Attached references only ({attached}). Match the character sheet "
            "exactly; never re-derive faces or reuse earlier generated images. "
            "The reference sheet wins."
        )
    return (
        f"Work only from the attached reference images ({attached}). Copy the "
        "cartoon character exactly as the character sheet draws it: same face "
        "proportions, same eye shape and size, same nose and mouth, same skin "
        "and hair tone. Never re-derive a face from a photograph and never "
        "carry anything over from an image generated earlier in this "
        "conversation. If matching the reference sheet conflicts with looking "
        "realistic, the reference sheet wins."
    )


def game_spec_clause(payload: Mapping[str, Any]) -> str:
    """The playability block for an activity page, or "" for an ordinary page.

    handoff §8 is blunt about why this exists: the agent has to name every game
    element and where it sits, because a model left to invent them produces a
    maze with three exits and a spot-the-difference whose differences are JPEG
    noise. So the declared elements travel verbatim, and the doctrine's rules for
    that game kind travel with them at a priority the shedding pass never drops.
    """
    spec = payload.get("gameSpec")
    if not isinstance(spec, Mapping):
        return ""
    kind = clean(spec.get("kind"))
    if not kind:
        return ""
    # Compact by design: a game page also carries a scene, identity locks and the
    # exact Arabic, so the contract is compressed — but never past the ban on
    # drawing the answer. A maze printed with its route traced is a wasted page.
    try:
        rules = doctrine.game_short_clause(kind)
    except doctrine.DoctrineError:
        # A typo in `kind` must not silently compile a page with no playability
        # rules at all — validate-prompts reports the unknown kind instead.
        return ""
    parts = [f"This playable {kind} page {rules}"]
    if kind == "maze":
        start = clean(spec.get("startDescription"))
        goal = clean(spec.get("goalDescription"))
        if start:
            parts.append(f"The route starts at {start}")
        if goal:
            parts.append(f"and ends at {goal}")
    elif kind == "spot-the-difference":
        count = spec.get("differenceCount")
        differences = clean_list(spec.get("differences"), 8)
        if isinstance(count, int) and count > 0:
            parts.append(
                f"There are exactly {count} differences between the two panels"
            )
        if differences:
            parts.append("Differences: " + "; ".join(differences))
    elif kind == "search-and-find":
        targets = clean_list(spec.get("targetItems"), 10)
        if targets:
            parts.append("Find exactly: " + "; ".join(targets))

    elements = clean_list(spec.get("elements"), 12)
    if elements:
        parts.append(
            "Draw these game elements exactly as described, inventing nothing and "
            "leaving nothing out: " + "; ".join(elements)
        )
    return ". ".join(part.rstrip(". ") for part in parts if part) + "."


def prompt_print_safe_clause(payload: Mapping[str, Any]) -> str:
    """The print guard, plus the brightness a children's page is supposed to have.

    These two belong in one clause because on their own each one misleads. The
    press constraints alone ("medium saturation, no pure black") read as an
    instruction to be drab, and the art came back drab: measured across this
    repo's books, the median page sat at a mean luminance of 115/255 with a
    fifth of its pixels in shadow, which prints heavy and muddy.

    Bright is not the opposite of print-safe. An open, daylit page with coloured
    shadows uses *less* ink than a dark one — grading the existing art to these
    targets dropped peak ink coverage from 326% to 300% while raising printed
    luminance. So the clause asks for both, in the order that matters.
    """
    return (
        "Bright airy lighting with luminous mid-tones and light coloured shadows; "
        "night scenes readable in moonlit blue-grey, never muddy. Print-safe "
        "palette: medium saturation; no pure black fills, deep navy, neon, or "
        "orange cast; natural skin and clothing."
    )


def shot_phrase(shot_scale: str, viewpoint: str) -> str:
    """Turn the two bare composition keywords into readable camera English."""
    shot = clean(shot_scale)
    view = clean(viewpoint)
    if shot and "shot" not in shot.lower():
        shot = f"{shot} shot"
    if view and not any(word in view.lower() for word in ("angle", "view", "level")):
        view = f"{view} angle"
    if shot and view:
        return f"Shot as a {shot} from a {view}"
    if shot:
        return f"Shot as a {shot}"
    if view:
        return f"Shot from a {view}"
    return ""


# ---------------------------------------------------------------------------
# Reading compiled renders back off a payload.
# ---------------------------------------------------------------------------


def compiled_variants(payload: Mapping[str, Any]) -> dict[str, str]:
    """Every compiled render on a prompt payload, keyed by target.

    Falls back to the legacy single ``compiledPrompt`` so a project compiled
    before targets existed still validates and still dispatches.
    """
    raw = payload.get("compiledPrompts")
    variants: dict[str, str] = {}
    if isinstance(raw, Mapping):
        for target, text in raw.items():
            if isinstance(target, str) and isinstance(text, str) and text.strip():
                variants[target] = text
    if not variants:
        legacy = payload.get("compiledPrompt")
        if isinstance(legacy, str) and legacy.strip():
            variants[DEFAULT_TARGET] = legacy
    return variants


def compiled_for(payload: Mapping[str, Any], target: str) -> str:
    """The render for one target, falling back to the default render."""
    variants = compiled_variants(payload)
    if target in variants:
        return variants[target]
    if DEFAULT_TARGET in variants:
        return variants[DEFAULT_TARGET]
    raise TargetError(
        f"No compiled prompt for target {target!r} — run compile-prompts"
    )


# ---------------------------------------------------------------------------
# Tail check — a truncation canary borrowed from drift-detection prompting.
# ---------------------------------------------------------------------------


def tail_check(payload: Mapping[str, Any]) -> str:
    """Name one already-required prop that sits late in the prompt.

    Both models silently ignore the tail of an over-long prompt, and a dropped
    tail is invisible: the art still looks finished. So the operator gets one
    cheap, checkable element to look for. It is deliberately an element the
    page already requires — never an extra detail invented for the check — so a
    hit costs nothing and a miss means the instruction was truncated, not that
    the picture is wrong.
    """
    scene = payload.get("scene") if isinstance(payload.get("scene"), Mapping) else {}
    props = clean_list(scene.get("propsInFrame"), 6)
    if props:
        return props[-1]
    return clean(scene.get("foreground"))


# ---------------------------------------------------------------------------
# Assembly.
# ---------------------------------------------------------------------------


def assemble(sections: list[tuple[int, str]], *, cap: int) -> tuple[str, bool]:
    """Join priority-tagged sections, shedding optional ones until they fit.

    Returns the prompt and whether anything was shed. Priorities 0 and 1 are
    never dropped, so the identity locks, the style, the text ban and the
    print-safe clause survive any length pressure.
    """
    def render(rows: list[tuple[int, str]]) -> str:
        return " ".join(text for _, text in rows)

    prompt = render(sections)
    shed = False
    for priority in (5, 4, 3, 2):
        if len(prompt) <= cap:
            break
        sections = [row for row in sections if row[0] != priority]
        prompt = render(sections)
        shed = True
    return prompt.strip(), shed


# ---------------------------------------------------------------------------
# The narrative renderer (Nano Banana Pro).
# ---------------------------------------------------------------------------


def _on_page(payload: Mapping[str, Any]) -> tuple[list[str], dict[str, str]]:
    names: dict[str, str] = {}
    order: list[str] = []
    for entry in payload.get("participants") or []:
        if not isinstance(entry, Mapping) or entry.get("onPage", True) is False:
            continue
        pid = entry.get("id")
        if not isinstance(pid, str):
            continue
        order.append(pid)
        names[pid] = clean(entry.get("displayName")) or pid
    return order, names


def build_narrative_prompt(payload: Mapping[str, Any], *, orientation: str) -> str:
    """Render the same fields as prose, for Nano Banana Pro.

    Section order follows Google's own guidance: the non-negotiables (what the
    image is, its aspect ratio, the reference rule, the style) come first, the
    scene is described as one continuous situation rather than a field dump,
    and the constraint tail is stated positively.
    """
    asset_id = str(payload.get("assetId") or "asset")
    is_character_sheet = asset_id == "character-sheet"
    is_location_sheet = asset_id.startswith("location-sheet-")

    style = payload.get("style") if isinstance(payload.get("style"), Mapping) else {}
    scene = payload.get("scene") if isinstance(payload.get("scene"), Mapping) else {}
    composition = (
        payload.get("composition")
        if isinstance(payload.get("composition"), Mapping)
        else {}
    )
    locks = (
        payload.get("identityLocks")
        if isinstance(payload.get("identityLocks"), Mapping)
        else {}
    )
    outfits = (
        payload.get("fixedOutfits")
        if isinstance(payload.get("fixedOutfits"), Mapping)
        else {}
    )
    actions = (
        payload.get("actionAndEmotion")
        if isinstance(payload.get("actionAndEmotion"), Mapping)
        else {}
    )

    order, names = _on_page(payload)
    ratio = doctrine.required_aspect_ratio()
    sections: list[tuple[int, str]] = []

    def add(priority: int, text: str) -> None:
        if text and text.strip():
            sections.append((priority, text.strip()))

    # 1. What this image is. Aspect ratio is stated in words because the phone
    #    lane has no ratio switch to set.
    beat = clean(payload.get("narrativeBeat"))
    request = clean(payload.get("primaryRequest"))
    if is_character_sheet:
        add(
            0,
            f"A character reference sheet in {orientation} {ratio} aspect ratio, "
            f"one sheet in one frame. {request}.",
        )
    elif is_location_sheet:
        add(
            0,
            f"A location reference sheet in {orientation} {ratio} aspect ratio, "
            f"with no people in it at all. {request}.",
        )
    else:
        add(
            0,
            f"A single full-bleed children's picture-book illustration in "
            f"{orientation} {ratio} aspect ratio — one continuous scene in one "
            f"frame, never a split or multi-panel layout. "
            f"The page has to show this moment: {beat}. {request}.",
        )

    # 2. The reference rule, before anything it could contradict.
    add(1, reference_directive(payload))

    # 3. Who is in it, as prose.
    for pid in order:
        lock = locks.get(pid) if isinstance(locks.get(pid), Mapping) else {}
        face = clean(lock.get("face"))
        hair = clean(lock.get("hair"))
        outfit = clean(outfits.get(pid))
        bits = [b[0].upper() + b[1:] for b in (face, hair) if b]
        line = f"{names[pid]}: " + ". ".join(bits) if bits else ""
        if outfit:
            line = (line + ". " if line else f"{names[pid]}: ") + (
                f"Dressed, without variation on any page, in {outfit}"
            )
        add(1, line + "." if line else "")

        secondary = [
            clean(lock.get(key))
            for key in ("age", "skin", "build", "accessories")
            if clean(lock.get(key)) and clean(lock.get(key)).lower() not in {"none", "n/a"}
        ]
        if secondary:
            add(3, f"{names[pid]} is also {'; '.join(secondary)}.")

    if len(order) >= 2:
        staging = clean(payload.get("spatialStaging"))
        add(
            1,
            (f"They are placed like this: {staging}. " if staging else "")
            + "Each person matches their own reference photo — never swap "
            "identity, faces, or outfits between them.",
        )

    # 4. The moment.
    for pid in order:
        act = actions.get(pid) if isinstance(actions.get(pid), Mapping) else {}
        action = clean(act.get("action"))
        emotion = clean(act.get("emotion"))
        if action and emotion:
            add(1, f"In this moment {names[pid]} {action}, {emotion}.")
        elif action:
            add(1, f"In this moment {names[pid]} {action}.")
        elif emotion:
            add(1, f"{names[pid]} reads as {emotion}.")

    for guest in payload.get("guests") or []:
        if not isinstance(guest, Mapping):
            continue
        notes = clean(guest.get("appearanceNotes"))
        if notes:
            add(
                1,
                "One original guest character, invented for this book and "
                f"belonging to no existing franchise: {notes}.",
            )

    # 5. Where it happens, as one situation rather than a field dump.
    place = clean(scene.get("place"))
    time_of_day = clean(scene.get("timeOfDay"))
    lighting = clean(scene.get("lighting"))
    atmosphere = clean(scene.get("atmosphere"))
    setting_bits: list[str] = []
    if place and time_of_day:
        setting_bits.append(f"The scene: {place}, {time_of_day}")
    elif place:
        setting_bits.append(f"The scene: {place}")
    elif time_of_day:
        setting_bits.append(f"It is {time_of_day}")
    if lighting:
        setting_bits.append(f"The light: {lighting}")
    if atmosphere:
        setting_bits.append(atmosphere)
    add(1, join_sentences(setting_bits))

    layers: list[str] = []
    if clean(scene.get("foreground")):
        layers.append(f"Closest to the camera, {clean(scene.get('foreground'))}")
    if clean(scene.get("midground")):
        layers.append(f"In the middle distance, {clean(scene.get('midground'))}")
    if clean(scene.get("background")):
        layers.append(f"Behind that, {clean(scene.get('background'))}")
    if clean(scene.get("backdropDetails")):
        layers.append(clean(scene.get("backdropDetails")))
    add(2, join_sentences(layers))

    props = clean_list(scene.get("propsInFrame"), 6)
    if props:
        add(3, "The frame also holds " + ", ".join(props) + ".")

    # 6. Style, verbatim from the theme catalog on every asset in the book.
    style_line = join_sentences([clean(style.get("medium")), clean(style.get("finish"))])
    if style_line:
        add(0, "Render it in this style: " + style_line)

    # 7. Camera, as one photographic sentence.
    shot = clean(composition.get("shotScale"))
    viewpoint = clean(composition.get("viewpoint"))
    lens = clean(composition.get("lens"))
    dof = clean(composition.get("depthOfField"))
    focal = clean(composition.get("focalHierarchy"))
    camera: list[str] = []
    framing = shot_phrase(shot, viewpoint)
    if framing:
        camera.append(framing)
    if lens:
        camera.append(lens)
    if dof:
        camera.append(dof)
    if focal:
        camera.append(f"Reading order in the frame: {focal}")
    add(3, join_sentences(camera))
    learned = payload.get("learnedRulesApplied") or []
    learned_text = [
        clean(item.get("rule"))
        for item in learned
        if isinstance(item, Mapping) and clean(item.get("rule"))
    ]
    if learned_text:
        add(
            2,
            "Apply these approved local prompt rules: "
            + "; ".join(learned_text[:3])
            + ".",
        )

    # 7b. Games. An activity page has to work as a puzzle, not just look like
    #     one, so its rules ride at the same priority as the identity locks.
    game_clause = game_spec_clause(payload)
    if game_clause:
        add(0, game_clause)

    # 8. Text. The story copy is drawn inside the artwork itself, so the render
    #    carries the exact Arabic and an explicit ban on any overlay. A sheet has
    #    no copy of its own and must come back wordless instead.
    raw_in_image_text = payload.get("inImageText")
    in_image_text = str(raw_in_image_text).strip() if isinstance(raw_in_image_text, str) else ""
    if in_image_text:
        # Naming the surface is what stops the copy reading as a pasted caption:
        # printed on a pinned note, a cloth banner or a windowsill, it belongs to
        # the room, takes its light and its perspective, and prints as artwork.
        surface = clean(payload.get("textSurface"))
        where = f"on {surface}" if surface else "on a surface"
        add(
            0,
            f"Inside the artwork, {where}, render this exact Arabic RTL copy with "
            "joined letters, following its angle and light. No overlay, "
            "caption bar, or later text layer; do not alter, shorten, or add writing: "
            f"{in_image_text}",
        )
    else:
        add(0, "No visible writing anywhere in this image: every surface is blank.")

    # 9. Colour. The print-safe clause is doctrine on every asset (handoff §9).
    palette = clean(payload.get("palette"))
    if palette:
        add(4, f"The palette for the whole book is {palette}.")
    add(1, prompt_print_safe_clause(payload))
    color_script = clean(payload.get("colorScript"))
    if color_script:
        add(
            4,
            "For this beat only, lean that same palette — no new colours — like "
            f"this: {color_script}.",
        )

    continuity = (
        payload.get("continuity")
        if isinstance(payload.get("continuity"), Mapping)
        else {}
    )
    carried = clean(continuity.get("fromPreviousPage"))
    if carried and carried.lower() != "n/a":
        add(4, f"Carried over from the previous page: {carried}.")

    # 10. Constraints, stated as what must be true. A bare negation list mostly
    #     tells an image model which nouns belong in the picture.
    positives, bans = positive_constraints(
        payload.get("avoid") or [], has_copy=bool(in_image_text)
    )
    if len(order) >= 2:
        swap = "each person keeps their own face, hair, and outfit throughout"
        if swap not in positives:
            positives.append(swap)
    if positives:
        add(2, "Also true of the finished image: " + "; ".join(positives[:6]) + ".")
    if bans:
        add(2, "Do not include: " + ", ".join(bans[:4]) + ".")

    prompt, _ = assemble(sections, cap=profile("nanobanana").max_chars)
    return prompt
