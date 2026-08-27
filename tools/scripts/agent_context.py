"""One call that tells an agent where a book is and what to load next.

Before this existed the only way for a session to orient itself was to read the
whole instruction stack — a 31 KB operating contract plus a 23 KB rulebook —
and then guess the state from `status`. That cost roughly fifteen thousand
tokens per session and produced the same answer every time: the state is
already written down in `book.json`.

`build_context` walks the gate ladder in the order the book actually moves
through it and stops at the first gate that is not satisfied. That gate is the
whole answer: it names the blocking condition, the exact command to run, and
the short list of reference files worth loading *for that step*. Everything
below the open gate is unreachable, so nothing about it needs reading yet.

The ladder is data, not prose, so a new gate cannot be added to the workflow
without also appearing here — which is the failure mode the old prose had.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

# Reference bundles, named so a gate declares intent rather than a file list.
# Keep these small: a bundle that grows past a few files stops being cheaper
# than the document it replaced.
ROUTING = ("tools/references/workflow/routing.md",)
STORY = ("tools/references/workflow/story.md",)
PROMPTS = ("tools/references/workflow/prompts.md",)


@dataclass(frozen=True)
class Gate:
    """One blocking condition on the way to a finished book."""

    key: str
    label_en: str
    label_ar: str
    satisfied: Callable[[Mapping[str, Any], Mapping[str, Any]], bool]
    next_command: Callable[[Mapping[str, Any], Mapping[str, Any]], str]
    read: Sequence[str]
    # Whether this rung needs a person. Usually fixed, but a gate can hold a
    # mechanical step and a human one — the character sheet has to be *drawn*
    # before anyone can accept it — so it may also be a predicate on the book.
    human: bool | Callable[[Mapping[str, Any]], bool] = False

    def needs_human(self, book: Mapping[str, Any]) -> bool:
        return bool(self.human(book)) if callable(self.human) else bool(self.human)


def _assets(book: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [a for a in (book.get("assets") or []) if isinstance(a, Mapping)]


def _asset(book: Mapping[str, Any], asset_id: str) -> Mapping[str, Any] | None:
    for asset in _assets(book):
        if asset.get("id") == asset_id:
            return asset
    return None


def _ids_with_prefix(book: Mapping[str, Any], prefix: str) -> list[Mapping[str, Any]]:
    return [a for a in _assets(book) if str(a.get("id", "")).startswith(prefix)]


def _interior_pages(book: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [a for a in _assets(book) if a.get("includeInPdf") and str(a.get("id", "")).startswith("page-")]


def _covers(book: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [a for a in _assets(book) if a.get("id") in {"cover", "back-cover"}]


def _has_image(asset: Mapping[str, Any]) -> bool:
    return bool(asset.get("imagePath")) and asset.get("status") in {
        "generated",
        "awaiting_review",
        "accepted",
    }


def _all_have_images(assets: Sequence[Mapping[str, Any]]) -> bool:
    return bool(assets) and all(_has_image(a) for a in assets)


def _story_locked(book: Mapping[str, Any]) -> bool:
    """True once `lock-story` has run.

    Locking is what registers a `location-sheet-NN` asset per declared location
    and copies each page's approved Arabic onto its asset as `storyText`. Both
    are preconditions for writing prompts at all, so the ladder has to see it.

    Detected three ways so a book locked before the marker existed still reads
    as locked: the explicit marker, the location map, or any asset that already
    carries story text. `reopen-story-review` clears all three.
    """
    if book.get("storyLock"):
        return True
    if book.get("locationAssets"):
        return True
    return any(str(a.get("storyText") or "").strip() for a in _assets(book))


def _pdf_verified(book: Mapping[str, Any], edition: str) -> bool:
    entry = (book.get("pdf") or {}).get(edition) or {}
    return entry.get("status") == "verified" and bool(entry.get("path"))


GATES: tuple[Gate, ...] = (
    Gate(
        key="consent",
        label_en="Image consent",
        label_ar="موافقة استخدام الصور",
        satisfied=lambda book, ctx: bool((book.get("consent") or {}).get("confirmed")),
        next_command=lambda book, ctx: "confirm-consent --project <ABS> --statement \"…\"",
        read=STORY,
        human=True,
    ),
    Gate(
        key="story_goal",
        label_en="Educational or entertainment goal",
        label_ar="هدف القصة",
        satisfied=lambda book, ctx: (book.get("storyGoal") or {}).get("mode")
        in {"educational", "entertainment"},
        next_command=lambda book, ctx: (
            "set-story-goal --project <ABS> --mode educational|entertainment --goal \"…\""
        ),
        read=STORY,
        human=True,
    ),
    Gate(
        key="story_type",
        label_en="Story type A/B/C",
        label_ar="نوع القصة",
        satisfied=lambda book, ctx: book.get("storyType") in {"A", "B", "C"},
        next_command=lambda book, ctx: "set-story-type --project <ABS> --type A|B|C",
        read=STORY,
    ),
    Gate(
        key="story_quality",
        label_en="Deterministic story review",
        label_ar="مراجعة القصة الآلية",
        satisfied=lambda book, ctx: (book.get("storyQuality") or {}).get("decision") == "pass",
        next_command=lambda book, ctx: "review-story --project <ABS>",
        read=STORY + ("tools/references/story-schema.md",),
    ),
    Gate(
        key="story_review",
        label_en="Human story-review gate",
        label_ar="مراجعة الأهل للقصة",
        satisfied=lambda book, ctx: ctx.get("storyReview", {}).get("status") == "approved",
        next_command=lambda book, ctx: _story_review_command(ctx),
        read=STORY + ("tools/references/reviews/story.md",),
        human=True,
    ),
    Gate(
        key="story_locked",
        label_en="Story locked",
        label_ar="قفل القصة",
        satisfied=lambda book, ctx: _story_locked(book),
        next_command=lambda book, ctx: "lock-story --project <ABS>",
        read=STORY,
    ),
    Gate(
        key="prompts_written",
        label_en="Prompt JSON for every asset",
        label_ar="برومبتات كل الأصول",
        satisfied=lambda book, ctx: bool(_assets(book))
        and all(a.get("promptPath") for a in _assets(book)),
        next_command=lambda book, ctx: (
            "write every input/prompts/*.json in one pass — character-sheet, every "
            "location-sheet-NN, and every PDF page — then: preflight --project <ABS>"
        ),
        read=PROMPTS + ("tools/references/prompt-fill-guide.md", "tools/references/prompt-rules.md"),
    ),
    Gate(
        key="prompt_review",
        label_en="Whole-pack prompt approval",
        label_ar="موافقة على حزمة البرومبتات",
        satisfied=lambda book, ctx: ctx.get("promptReview", {}).get("status") == "approved",
        next_command=lambda book, ctx: _prompt_review_command(ctx),
        read=PROMPTS,
        human=True,
    ),
    Gate(
        key="image_lane",
        label_en="Image lane (agent or manual)",
        label_ar="مسار توليد الصور",
        satisfied=lambda book, ctx: bool((book.get("imageLane") or {}).get("selected")),
        next_command=lambda book, ctx: (
            "set-image-lane --project <ABS> --lane agent|manual --statement \"…\"  "
            "(there is no default — ask)"
        ),
        read=("tools/references/prompt-targets.md",),
        human=True,
    ),
    Gate(
        key="character_sheet",
        label_en="Character sheet accepted",
        label_ar="قبول ورقة الشخصيات",
        satisfied=lambda book, ctx: (_asset(book, "character-sheet") or {}).get("status")
        == "accepted",
        next_command=lambda book, ctx: _sheet_command(book),
        read=ROUTING,
        # Drawing the sheet is mechanical; only accepting it is the human call.
        # "اعمل الشخصيات" is a request to render, so the plan must not stop
        # before there is anything to look at.
        human=lambda book: _has_image(_asset(book, "character-sheet") or {}),
    ),
    Gate(
        key="location_sheets",
        label_en="Location sheets rendered",
        label_ar="أوراق الأماكن",
        satisfied=lambda book, ctx: not _ids_with_prefix(book, "location-sheet-")
        or _all_have_images(_ids_with_prefix(book, "location-sheet-")),
        next_command=lambda book, ctx: "generate-book-images --project <ABS>",
        read=ROUTING,
    ),
    Gate(
        key="interior_images",
        label_en="Interior page illustrations",
        label_ar="رسم صفحات القصة",
        satisfied=lambda book, ctx: _all_have_images(_interior_pages(book)),
        next_command=lambda book, ctx: "generate-book-images --project <ABS>",
        read=ROUTING,
    ),
    Gate(
        key="covers",
        label_en="Front and back covers",
        label_ar="الغلاف والغلاف الخلفي",
        satisfied=lambda book, ctx: _all_have_images(_covers(book)),
        next_command=lambda book, ctx: "generate-book-images --project <ABS>",
        read=ROUTING,
    ),
    Gate(
        key="image_approval",
        label_en="Operator sign-off on the images",
        label_ar="موافقة على الصور",
        satisfied=lambda book, ctx: (book.get("imageApproval") or {}).get("status") == "approved",
        next_command=lambda book, ctx: (
            "image-notes --project <ABS>  →  redo flagged assets  →  "
            "approve-images --project <ABS> --statement \"…\""
        ),
        read=ROUTING,
        human=True,
    ),
    Gate(
        key="draft_pdf",
        label_en="Verified draft PDF",
        label_ar="نسخة PDF أولية متحقق منها",
        satisfied=lambda book, ctx: _pdf_verified(book, "draft"),
        next_command=lambda book, ctx: (
            "build --project <ABS> --edition draft  →  verify --project <ABS> --edition draft"
        ),
        read=(),
    ),
    Gate(
        key="review_pass",
        label_en="Four review rubrics merged and passing",
        label_ar="مراجعات الجودة",
        satisfied=lambda book, ctx: (book.get("review") or {}).get("status") == "passed",
        next_command=lambda book, ctx: (
            "story + continuity + pdf in parallel, then arabic last, then: "
            "merge-reviews --project <ABS> --review <story> --review <continuity> "
            "--review <arabic> --review <pdf>"
        ),
        # Only the loop file here. It names the four rubrics and the order they
        # run in; loading all five at once is 584 lines on a turn that has not
        # decided which rubric it is writing yet.
        read=("tools/references/reviews/README.md",),
    ),
    Gate(
        key="final_approval",
        label_en="Explicit final approval",
        label_ar="الموافقة النهائية",
        satisfied=lambda book, ctx: (book.get("finalApproval") or {}).get("status") == "approved",
        next_command=lambda book, ctx: "approve-final --project <ABS> --statement \"…\"",
        read=(),
        human=True,
    ),
    Gate(
        key="final_pdf",
        label_en="Verified final PDF",
        label_ar="النسخة النهائية",
        satisfied=lambda book, ctx: _pdf_verified(book, "final"),
        next_command=lambda book, ctx: (
            "build --project <ABS> --edition final  →  verify --project <ABS> --edition final"
        ),
        read=(),
    ),
)

GATE_KEYS = tuple(gate.key for gate in GATES)


def _story_review_command(ctx: Mapping[str, Any]) -> str:
    status = (ctx.get("storyReview") or {}).get("status")
    return {
        "not_prepared": "prepare-story-review --project <ABS>",
        "awaiting_user": "STOP — the user is reading input/story-review.md. Do not proceed.",
        "changes_detected": "approve-story-review --project <ABS> --statement \"…\"",
        "review_file_missing": "prepare-story-review --project <ABS> --force",
        "stale": "prepare-story-review --project <ABS> --force",
        "story_missing": "write input/story.json first",
    }.get(str(status), "story-review-status --project <ABS>")


def _prompt_review_command(ctx: Mapping[str, Any]) -> str:
    status = (ctx.get("promptReview") or {}).get("status")
    return {
        "not_prepared": "preflight --project <ABS>  →  prepare-prompt-review --project <ABS>",
        "awaiting_user": "STOP — the user is reading Prompts/Index.md. Do not proceed.",
        "feedback_pending": "apply every note to new prompt versions, then prepare-prompt-review",
        "changes_detected": "prepare-prompt-review --project <ABS>",
        "stale": "prepare-prompt-review --project <ABS>",
    }.get(str(status), "prompt-review-status --project <ABS>")


def _sheet_command(book: Mapping[str, Any]) -> str:
    sheet = _asset(book, "character-sheet") or {}
    if _has_image(sheet) and sheet.get("status") != "accepted":
        return "show the sheet, then: character-review --project <ABS> --asset character-sheet --accept"
    return "generate-book-images --project <ABS>   # wave A: sheet + every location sheet together"


class UnknownGate(ValueError):
    """A run-to target that is not a gate on the ladder."""


def build_plan(
    book: Mapping[str, Any],
    ctx: Mapping[str, Any],
    ladder: Sequence[Mapping[str, Any]],
    target: str,
) -> dict[str, Any]:
    """How far the agent may run when the user has pre-authorized a destination.

    "اكمل لحد ما تعمل الشخصيات" is permission for everything between here and
    there. Asking again before each mechanical command in between is not
    caution, it is a round trip the user already paid for. So this returns the
    stretch that runs unattended and the exact rung where it has to stop.

    What it will **not** do is skip a gate that needs a human to say something.
    Consent, the story approval, the prompt-pack approval, the sheet
    acceptance, the image sign-off and the final approval all record a
    statement from a person; an agent that runs through them is not saving a
    round trip, it is inventing the person. So the plan stops at the first one
    that is still open, even when the target is past it, and says why.
    """
    if target not in GATE_KEYS:
        raise UnknownGate(
            f"Unknown gate {target!r}. Valid: {', '.join(GATE_KEYS)}"
        )
    by_key = {gate.key: gate for gate in GATES}
    target_index = GATE_KEYS.index(target)
    states = {row["key"]: row["state"] for row in ladder}

    if states.get(target) == "done":
        return {
            "target": target,
            "targetLabelAr": by_key[target].label_ar,
            "reached": True,
            "steps": [],
            "runWithoutAsking": [],
            "stopsAt": None,
            "stopReasonAr": None,
        }

    steps: list[dict[str, Any]] = []
    run_without_asking: list[str] = []
    stops_at: str | None = None
    for key in GATE_KEYS[: target_index + 1]:
        if states.get(key) == "done":
            continue
        gate = by_key[key]
        command = gate.next_command(book, ctx)
        needs_human = gate.needs_human(book)
        steps.append(
            {
                "key": key,
                "labelAr": gate.label_ar,
                "labelEn": gate.label_en,
                "waitingOnHuman": needs_human,
                "command": command,
            }
        )
        if needs_human:
            if stops_at is None:
                stops_at = key
            continue
        if stops_at is None:
            run_without_asking.append(command)

    reason = None
    if stops_at is not None:
        label = by_key[stops_at].label_ar
        reason = (
            f"«{label}» محتاجة كلام من المستخدم نفسه — مش قرار الوكيل. "
            "شغّل كل اللي قبلها من غير ما تسأل، وبعدين اطلب الرد ده تحديدًا."
        )

    return {
        "target": target,
        "targetLabelAr": by_key[target].label_ar,
        "reached": False,
        "steps": steps,
        "runWithoutAsking": run_without_asking,
        "stopsAt": stops_at,
        "stopReasonAr": reason,
    }


def build_context(
    book: Mapping[str, Any],
    *,
    project: str,
    story_review: Mapping[str, Any] | None = None,
    prompt_review: Mapping[str, Any] | None = None,
    progress: Mapping[str, Any] | None = None,
    until: str | None = None,
) -> dict[str, Any]:
    """The whole agent-facing state of one book, in one payload.

    Returns the ordered gate ladder with a `state` on every rung, the first
    unsatisfied gate as `openGate`, and the files worth reading for that gate
    and nothing else. `alwaysRead` is deliberately a single small router file:
    a session that loads more than that on a routine turn is spending tokens
    re-deriving what this payload already answered.
    """
    ctx = {
        "storyReview": dict(story_review or {}),
        "promptReview": dict(prompt_review or {}),
    }

    ladder: list[dict[str, Any]] = []
    open_gate: Gate | None = None
    for gate in GATES:
        done = bool(gate.satisfied(book, ctx))
        if done:
            state = "done"
        elif open_gate is None:
            state = "open"
            open_gate = gate
        else:
            state = "blocked"
        ladder.append(
            {
                "key": gate.key,
                "state": state,
                "labelEn": gate.label_en,
                "labelAr": gate.label_ar,
                "waitingOnHuman": gate.needs_human(book) and state == "open",
            }
        )

    plan = build_plan(book, ctx, ladder, until) if until else None

    if open_gate is None:
        return {
            "mode": "context",
            "project": project,
            "status": book.get("status"),
            "openGate": None,
            "waitingOnHuman": False,
            "nextCommand": None,
            "nextAction": "Book is complete. Nothing is open.",
            "gates": ladder,
            "alwaysRead": list(ROUTING),
            "read": [],
            "plan": plan,
            "progress": dict(progress or {}),
        }

    return {
        "mode": "context",
        "project": project,
        "status": book.get("status"),
        "openGate": open_gate.key,
        "waitingOnHuman": open_gate.needs_human(book),
        "nextCommand": open_gate.next_command(book, ctx),
        "nextAction": book.get("nextAction"),
        "gates": ladder,
        "alwaysRead": list(ROUTING),
        "read": list(open_gate.read),
        "plan": plan,
        "progress": dict(progress or {}),
    }
