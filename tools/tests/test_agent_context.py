"""The orientation call has to be right about which gate is open.

`context` exists so a session does not read the instruction stack to work out
where a book is. That only holds if the gate ladder agrees with the gates the
pipeline actually enforces — so these tests walk a book forward one gate at a
time and assert that the reported open gate moves with it.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "tools" / "scripts" / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


agent_context = _load("agent_context")


def empty_book() -> dict:
    """A freshly initialized book: every gate shut."""
    return {
        "status": "created",
        "consent": {"confirmed": False},
        "assets": [],
        "pdf": {"draft": {"status": "planned"}, "final": {"status": "planned"}},
        "review": {"status": "not_started"},
        "finalApproval": {"status": "not_approved"},
    }


def full_assets() -> list[dict]:
    """Character sheet, one location sheet, 22 interior pages, two covers."""
    assets = [
        {
            "id": "character-sheet",
            "includeInPdf": False,
            "status": "accepted",
            "promptPath": "input/prompts/character-sheet.v01.json",
            "imagePath": "output/images/character-sheet.png",
        },
        {
            "id": "location-sheet-01",
            "includeInPdf": False,
            "status": "accepted",
            "promptPath": "input/prompts/location-sheet-01.v01.json",
            "imagePath": "output/images/location-sheet-01.png",
        },
    ]
    for n in range(1, 23):
        assets.append(
            {
                "id": f"page-{n:02d}",
                "includeInPdf": True,
                "pdfOrder": n + 1,
                "status": "accepted",
                "promptPath": f"input/prompts/page-{n:02d}.v01.json",
                "imagePath": f"output/images/page-{n:02d}.png",
            }
        )
    for cover in ("cover", "back-cover"):
        assets.append(
            {
                "id": cover,
                "includeInPdf": True,
                "pdfOrder": 0,
                "status": "accepted",
                "promptPath": f"input/prompts/{cover}.v01.json",
                "imagePath": f"output/images/{cover}.png",
            }
        )
    return assets


def satisfied_book() -> dict:
    """Everything done — used as the base for knocking one gate back out."""
    return {
        "status": "complete",
        "consent": {"confirmed": True},
        "storyGoal": {"mode": "educational", "goalAr": "…"},
        "storyType": "A",
        "storyQuality": {"decision": "pass"},
        "storyLock": {"lockedAt": "2026-08-27T00:00:00+00:00"},
        "locationAssets": {"classroom": "location-sheet-01"},
        "assets": full_assets(),
        "imageLane": {"selected": "agent"},
        "imageApproval": {"status": "approved"},
        "pdf": {
            "draft": {"status": "verified", "path": "output/pdf/draft.pdf"},
            "final": {"status": "verified", "path": "output/pdf/final.pdf"},
        },
        "review": {"status": "passed"},
        "finalApproval": {"status": "approved"},
    }


APPROVED = {"status": "approved"}


def ctx(book: dict, **kw) -> dict:
    kw.setdefault("story_review", APPROVED)
    kw.setdefault("prompt_review", APPROVED)
    return agent_context.build_context(book, project="/ABS/CLIENT", **kw)


class LadderShapeTests(unittest.TestCase):
    def test_every_gate_reports_exactly_one_state(self) -> None:
        payload = ctx(empty_book())
        self.assertEqual(
            list(agent_context.GATE_KEYS), [g["key"] for g in payload["gates"]]
        )
        for gate in payload["gates"]:
            self.assertIn(gate["state"], {"done", "open", "blocked"})

    def test_only_one_gate_is_open_at_a_time(self) -> None:
        for book in (empty_book(), satisfied_book()):
            payload = ctx(book)
            open_gates = [g for g in payload["gates"] if g["state"] == "open"]
            self.assertLessEqual(len(open_gates), 1)

    def test_gate_keys_are_unique(self) -> None:
        self.assertEqual(
            len(agent_context.GATE_KEYS), len(set(agent_context.GATE_KEYS))
        )

    def test_every_gate_names_real_reference_files(self) -> None:
        """A reading list that points at a missing file is worse than none."""
        for gate in agent_context.GATES:
            for rel in gate.read:
                self.assertTrue(
                    (ROOT / rel).is_file(), f"{gate.key} points at missing {rel}"
                )
        for rel in agent_context.ROUTING:
            self.assertTrue((ROOT / rel).is_file(), rel)


class OpenGateTests(unittest.TestCase):
    def test_a_new_book_opens_on_consent(self) -> None:
        payload = ctx(empty_book())
        self.assertEqual("consent", payload["openGate"])
        self.assertTrue(payload["waitingOnHuman"])

    def test_a_finished_book_has_no_open_gate(self) -> None:
        payload = ctx(satisfied_book())
        self.assertIsNone(payload["openGate"])
        self.assertIsNone(payload["nextCommand"])
        self.assertFalse(payload["waitingOnHuman"])
        self.assertEqual([], payload["read"])

    def test_each_gate_becomes_the_open_gate_when_knocked_out(self) -> None:
        """The ladder order is the contract — walk it rung by rung."""
        breakers = {
            "consent": lambda b: b.__setitem__("consent", {"confirmed": False}),
            "story_goal": lambda b: b.pop("storyGoal"),
            "story_type": lambda b: b.pop("storyType"),
            "story_quality": lambda b: b.__setitem__(
                "storyQuality", {"decision": "fail"}
            ),
            "story_locked": lambda b: (
                b.__setitem__("storyLock", None),
                b.__setitem__("locationAssets", {}),
                [a.pop("storyText", None) for a in b["assets"]],
            ),
            "prompts_written": lambda b: b["assets"][3].pop("promptPath"),
            "image_lane": lambda b: b.__setitem__("imageLane", {"selected": None}),
            "character_sheet": lambda b: b["assets"][0].__setitem__(
                "status", "prompted"
            ),
            "location_sheets": lambda b: b["assets"][1].__setitem__("imagePath", None),
            "interior_images": lambda b: b["assets"][5].__setitem__("imagePath", None),
            "covers": lambda b: b["assets"][-1].__setitem__("imagePath", None),
            "image_approval": lambda b: b.__setitem__(
                "imageApproval", {"status": "not_approved"}
            ),
            "draft_pdf": lambda b: b["pdf"]["draft"].__setitem__("status", "built"),
            "review_pass": lambda b: b["review"].__setitem__(
                "status", "fixes_pending"
            ),
            "final_approval": lambda b: b["finalApproval"].__setitem__(
                "status", "not_approved"
            ),
            "final_pdf": lambda b: b["pdf"]["final"].__setitem__("status", "built"),
        }
        # story_review and prompt_review live outside book.json, tested below.
        self.assertEqual(
            set(agent_context.GATE_KEYS) - {"story_review", "prompt_review"},
            set(breakers),
            "a gate was added or renamed without a case here",
        )
        for key, break_it in breakers.items():
            book = satisfied_book()
            break_it(book)
            payload = ctx(book)
            self.assertEqual(key, payload["openGate"], f"expected {key} to open")

    def test_story_review_gate_opens_on_every_unapproved_status(self) -> None:
        for status in (
            "not_prepared",
            "awaiting_user",
            "changes_detected",
            "stale",
            "review_file_missing",
        ):
            payload = ctx(satisfied_book(), story_review={"status": status})
            self.assertEqual("story_review", payload["openGate"], status)
            self.assertTrue(payload["nextCommand"])

    def test_a_gate_waiting_on_the_user_says_stop(self) -> None:
        payload = ctx(satisfied_book(), story_review={"status": "awaiting_user"})
        self.assertIn("STOP", payload["nextCommand"])
        self.assertTrue(payload["waitingOnHuman"])

    def test_prompt_review_gate_opens_on_pending_feedback(self) -> None:
        payload = ctx(satisfied_book(), prompt_review={"status": "feedback_pending"})
        self.assertEqual("prompt_review", payload["openGate"])
        self.assertIn("prepare-prompt-review", payload["nextCommand"])


class ReadingListTests(unittest.TestCase):
    def test_the_reading_list_stays_small(self) -> None:
        """The whole point is not re-reading the stack. Cap it."""
        for gate in agent_context.GATES:
            self.assertLessEqual(
                len(gate.read), 5, f"{gate.key} asks for too many files"
            )

    def test_always_read_is_one_router_file(self) -> None:
        self.assertEqual(1, len(agent_context.ROUTING))

    def test_story_gates_do_not_pull_in_the_prompt_stage(self) -> None:
        story_gate = next(g for g in agent_context.GATES if g.key == "story_review")
        self.assertNotIn("tools/references/workflow/prompts.md", story_gate.read)

    def test_prompt_gates_do_not_pull_in_the_story_stage(self) -> None:
        gate = next(g for g in agent_context.GATES if g.key == "prompts_written")
        self.assertNotIn("tools/references/workflow/story.md", gate.read)


class PayloadTests(unittest.TestCase):
    def test_progress_block_is_passed_through_untouched(self) -> None:
        progress = {"percent": 41, "messageAr": "٤١٪"}
        payload = ctx(satisfied_book(), progress=progress)
        self.assertEqual(progress, payload["progress"])

    def test_build_context_does_not_mutate_the_book(self) -> None:
        book = satisfied_book()
        before = copy.deepcopy(book)
        ctx(book)
        self.assertEqual(before, book)



class StoryLockGateTests(unittest.TestCase):
    """Writing prompts before lock-story wastes a whole pack and a human gate."""

    def _approved_but_unlocked(self) -> dict:
        book = empty_book()
        book.update(
            {
                "consent": {"confirmed": True},
                "storyGoal": {"mode": "educational", "goalAr": "…"},
                "storyType": "A",
                "storyQuality": {"decision": "pass"},
                # `init` registers the sheet and the PDF assets; lock-story is
                # what adds the location sheets and every page's storyText.
                "assets": [{"id": "character-sheet", "includeInPdf": False}]
                + [
                    {"id": f"page-{n:02d}", "includeInPdf": True}
                    for n in range(1, 23)
                ]
                + [
                    {"id": "cover", "includeInPdf": True},
                    {"id": "back-cover", "includeInPdf": True},
                ],
            }
        )
        return book

    def test_an_approved_but_unlocked_story_opens_the_lock_gate(self) -> None:
        payload = ctx(self._approved_but_unlocked(), prompt_review={"status": "not_prepared"})
        self.assertEqual("story_locked", payload["openGate"])
        self.assertIn("lock-story", payload["nextCommand"])

    def test_a_book_locked_before_the_marker_existed_still_reads_as_locked(self) -> None:
        """Detection has to work on books already in production."""

        def by_location_map(book: dict) -> None:
            book["locationAssets"] = {"classroom": "location-sheet-01"}

        def by_copied_story_text(book: dict) -> None:
            book["assets"][1]["storyText"] = "أحمد صحي بدري."

        for name, apply_legacy in (
            ("locationAssets", by_location_map),
            ("storyText", by_copied_story_text),
        ):
            with self.subTest(signal=name):
                book = self._approved_but_unlocked()
                apply_legacy(book)
                payload = ctx(book, prompt_review={"status": "not_prepared"})
                self.assertNotEqual("story_locked", payload["openGate"])

    def test_the_prompts_gate_names_the_location_sheets(self) -> None:
        book = self._approved_but_unlocked()
        book["storyLock"] = {"lockedAt": "…"}
        payload = ctx(book, prompt_review={"status": "not_prepared"})
        self.assertEqual("prompts_written", payload["openGate"])
        self.assertIn("location-sheet", payload["nextCommand"])


class RunToTargetTests(unittest.TestCase):
    """`--until` is the user saying "I already told you to get there"."""

    def _mid_book(self) -> dict:
        book = satisfied_book()
        book["imageLane"] = {"selected": None}
        book["assets"][0]["status"] = "prompted"
        book["imageApproval"] = {"status": "not_approved"}
        return book

    def test_no_target_means_no_plan(self) -> None:
        self.assertIsNone(ctx(empty_book())["plan"])

    def test_an_unknown_target_is_refused_by_name(self) -> None:
        with self.assertRaises(agent_context.UnknownGate) as caught:
            ctx(empty_book(), until="make_the_characters")
        self.assertIn("consent", str(caught.exception))

    def test_a_target_already_passed_reports_reached(self) -> None:
        plan = ctx(satisfied_book(), until="story_type")["plan"]
        self.assertTrue(plan["reached"])
        self.assertEqual([], plan["runWithoutAsking"])

    def test_the_plan_stops_at_the_first_gate_that_needs_a_person(self) -> None:
        plan = ctx(self._mid_book(), until="character_sheet")["plan"]
        self.assertEqual("image_lane", plan["stopsAt"])
        self.assertTrue(plan["stopReasonAr"])
        # Everything before that rung runs unattended; nothing after it does.
        self.assertNotIn(
            "character-review",
            " ".join(plan["runWithoutAsking"]),
        )

    def test_a_stretch_with_no_human_gate_runs_end_to_end(self) -> None:
        book = self._mid_book()
        book["imageLane"] = {"selected": "agent"}
        book["assets"][0]["status"] = "accepted"
        book["assets"][1]["imagePath"] = None
        plan = ctx(book, until="covers")["plan"]
        self.assertIsNone(plan["stopsAt"])
        self.assertEqual(
            [step["command"] for step in plan["steps"]], plan["runWithoutAsking"]
        )

    def test_drawing_the_sheet_runs_but_accepting_it_stops(self) -> None:
        """«اعمل الشخصيات» asks for a render, not for a decision."""
        book = satisfied_book()
        book["assets"][0].update({"status": "prompted", "imagePath": None})
        plan = ctx(book, until="character_sheet")["plan"]
        self.assertIsNone(plan["stopsAt"])
        self.assertIn(
            "generate-book-images", " ".join(plan["runWithoutAsking"])
        )

        book["assets"][0].update(
            {"status": "awaiting_review", "imagePath": "output/images/sheet.png"}
        )
        plan = ctx(book, until="character_sheet")["plan"]
        self.assertEqual("character_sheet", plan["stopsAt"])
        self.assertEqual([], plan["runWithoutAsking"])

    def test_every_step_says_whether_it_needs_a_person(self) -> None:
        plan = ctx(empty_book(), until="final_pdf")["plan"]
        self.assertTrue(plan["steps"])
        for step in plan["steps"]:
            self.assertIn(step["waitingOnHuman"], (True, False))
            self.assertTrue(step["command"])


if __name__ == "__main__":
    unittest.main()
