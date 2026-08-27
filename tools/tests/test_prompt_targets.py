"""Both image tools must get the same picture, phrased their own way.

The value of a second target is only real if the two renders stay bound to the
same fields and carry the same non-negotiable clauses. These tests pin that:
what differs is sentence shape, never content.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "tools" / "scripts"
sys.path.insert(0, str(SCRIPTS))

SPEC = importlib.util.spec_from_file_location(
    "story_pipeline", SCRIPTS / "story_pipeline.py"
)
assert SPEC and SPEC.loader
pipeline = importlib.util.module_from_spec(SPEC)
sys.modules["story_pipeline"] = pipeline
SPEC.loader.exec_module(pipeline)

import manual_dispatch  # noqa: E402
import prompt_targets as pt  # noqa: E402


PAGE: dict = {
    "assetId": "page-05",
    "narrativeBeat": "Sama refuses to let go of her mother's hand at the school gate",
    "primaryRequest": "Sama grips her mother's hand while the teacher crouches to greet her",
    "inputImages": [
        {"role": "persona-identity", "personaId": "persona-01", "path": "/abs/sama.png"},
        {"role": "character-sheet", "path": "/abs/sheet.png"},
    ],
    "participants": [
        {"id": "persona-01", "displayName": "سما", "role": "hero", "onPage": True},
        {"id": "persona-02", "displayName": "ماما", "role": "companion", "onPage": True},
    ],
    "identityLocks": {
        "persona-01": {
            "face": "round face, wide dark brown eyes, small upturned nose",
            "hair": "black hair in two short braids with red bands",
        },
        "persona-02": {
            "face": "oval face, high cheekbones, calm dark eyes",
            "hair": "black hair under a soft grey scarf",
        },
    },
    "fixedOutfits": {
        "persona-01": "navy pinafore over a white shirt, white socks, red shoes",
        "persona-02": "long dusty-rose tunic over grey trousers",
    },
    "spatialStaging": "Sama front-left, mother behind her right shoulder",
    "actionAndEmotion": {
        "persona-01": {
            "action": "grips her mother's hand with both hands",
            "emotion": "eyes wide, mouth pressed shut",
        },
        "persona-02": {
            "action": "crouches slightly, free hand on Sama's shoulder",
            "emotion": "steady warm half-smile",
        },
    },
    "scene": {
        "place": "a school gate of painted green iron bars in a sand-coloured wall",
        "timeOfDay": "just after seven, thin early sun",
        "atmosphere": "cool still morning air, dust hanging low",
        "lighting": "low sun from the left, warm gold key, long soft shadows",
        "foreground": "grey paving stones, a scuffed red schoolbag with a brass buckle",
        "midground": "the open green gate, a wooden bench with peeling blue paint",
        "background": "a two-storey sand-coloured school building, dusty palm crowns",
        "propsInFrame": [
            "a scuffed red schoolbag with a brass buckle",
            "a chipped white enamel water bottle",
            "a half-eaten date on a paper napkin",
        ],
        "backdropDetails": "chalk hopscotch squares faded on the pavement, a sparrow on the wall",
    },
    "style": {
        "medium": "premium whimsical children's storybook digital illustration",
        "finish": "rich saturated color, print-ready, NOT flat cartoon",
    },
    "composition": {
        "orientation": "landscape",
        "shotScale": "medium",
        "viewpoint": "low",
        "focalHierarchy": "Sama's hands, then her face",
        "lens": "35mm-equivalent, slight wide",
        "depthOfField": "Sama sharp, the building softly out of focus",
    },
    "palette": "sand, green iron, dusty rose, warm gold",
    "colorScript": "the dusty rose leans warmer where the two hands meet",
    "continuity": {"fromPreviousPage": "still carries the scuffed red schoolbag"},
    "avoid": [
        "extra people",
        "identity drift",
        "malformed hands",
        "brand logos",
        "speech bubbles unless requested",
    ],
}


def render(target: str) -> str:
    return pipeline.build_compiled_prompt(
        dict(PAGE), orientation="landscape", target=target
    )


class TargetProfileTests(unittest.TestCase):
    def test_chatgpt_is_the_default_so_existing_projects_are_unchanged(self) -> None:
        self.assertEqual("chatgpt", pt.DEFAULT_TARGET)
        self.assertEqual(
            render("chatgpt"),
            pipeline.build_compiled_prompt(dict(PAGE), orientation="landscape"),
        )

    def test_an_unknown_target_names_the_ones_that_exist(self) -> None:
        with self.assertRaises(pt.TargetError) as ctx:
            pt.profile("midjourney")
        self.assertIn("nanobanana", str(ctx.exception))


class SharedClauseTests(unittest.TestCase):
    """Whatever the phrasing, these clauses ride on every target."""

    def test_a_page_without_copy_comes_back_wordless(self) -> None:
        for target in pt.TARGETS:
            with self.subTest(target=target):
                self.assertIn("no visible writing", render(target).lower())

    def test_in_image_copy_travels_verbatim_with_an_overlay_ban(self) -> None:
        """The Arabic is drawn into the art, so the render must carry it exactly."""
        copy = "عبد الله رتب لعبه قبل ما ينام"
        page = dict(PAGE, inImageText=copy)
        for target in pt.TARGETS:
            with self.subTest(target=target):
                compiled = pipeline.build_compiled_prompt(
                    dict(page), orientation="landscape", target=target
                )
                self.assertIn(copy, compiled)
                self.assertIn(pt.OVERLAY_BAN_MARKER, compiled.lower())

    def test_no_target_reserves_a_caption_overlay(self) -> None:
        """Story text is drawn inside the art, never over it."""
        for target in pt.TARGETS:
            with self.subTest(target=target):
                lowered = render(target).lower()
                for banned in ("caption can be placed", "bottom 32%", "safe zone"):
                    self.assertNotIn(banned, lowered)

    def test_every_target_carries_the_print_safe_palette(self) -> None:
        """Compact wording, but every §9 rule still rides on both renders."""
        for target in pt.TARGETS:
            with self.subTest(target=target):
                lowered = render(target).lower()
                self.assertIn("print-safe palette", lowered)
                for rule in ("saturation", "pure black", "deep navy", "natural skin"):
                    self.assertIn(rule, lowered)

    def test_every_target_forbids_swapping_two_identities(self) -> None:
        for target in pt.TARGETS:
            with self.subTest(target=target):
                self.assertIn("never swap identity", render(target))

    def test_every_target_carries_the_reference_sheet_rule(self) -> None:
        # handoff §8 I3/I6 — the accepted sheet wins, and nothing generated
        # earlier in the conversation counts as a reference.
        for target in pt.TARGETS:
            with self.subTest(target=target):
                self.assertIn("reference sheet wins", render(target))

    def test_every_target_stays_under_its_own_cap(self) -> None:
        for target in pt.TARGETS:
            with self.subTest(target=target):
                self.assertLessEqual(len(render(target)), pt.profile(target).max_chars)

    def test_every_target_names_the_same_specific_things(self) -> None:
        for target in pt.TARGETS:
            with self.subTest(target=target):
                compiled = render(target)
                self.assertIn("navy pinafore", compiled)
                self.assertIn("warm gold key", compiled)
                self.assertIn("سما", compiled)


class NanoBananaShapeTests(unittest.TestCase):
    def test_it_states_the_aspect_ratio_in_words(self) -> None:
        # The phone lane has no ratio switch, so the ratio has to be said.
        self.assertIn("16:9 aspect ratio", render("nanobanana"))

    def test_it_states_constraints_positively(self) -> None:
        compiled = render("nanobanana")
        self.assertIn("Also true of the finished image", compiled)
        self.assertIn("only the people named above are in the frame", compiled)
        # "malformed hands" is a shape to avoid; the model is told the shape to draw.
        self.assertNotIn("malformed hands", compiled)
        self.assertIn("five fingers each", compiled)

    def test_a_ban_with_no_positive_form_stays_a_ban(self) -> None:
        self.assertIn("Do not include: speech bubbles", render("nanobanana"))

    def test_it_reads_as_prose_not_as_labelled_fragments(self) -> None:
        compiled = render("nanobanana")
        self.assertIn("Closest to the camera,", compiled)
        self.assertNotIn("Foreground:", compiled)
        self.assertNotIn("Composition:", compiled)


class PositiveRewriteTests(unittest.TestCase):
    def test_a_known_negation_becomes_a_statement_of_fact(self) -> None:
        positives, bans = pt.positive_constraints(["extra people"])
        self.assertEqual(
            ["only the people named above are in the frame, and nobody else"], positives
        )
        self.assertEqual([], bans)

    def test_an_unknown_negation_is_kept_rather_than_dropped(self) -> None:
        positives, bans = pt.positive_constraints(["a cat wearing sunglasses"])
        self.assertEqual([], positives)
        self.assertEqual(["a cat wearing sunglasses"], bans)

    def test_two_negations_with_the_same_fix_collapse_to_one_line(self) -> None:
        positives, _ = pt.positive_constraints(["Latin text", "mirrored Arabic"])
        self.assertEqual([pt.TEXT_REWRITE_WORDLESS], positives)

    def test_a_page_with_copy_is_never_told_every_surface_is_blank(self) -> None:
        """The contradiction that used to come back as art with no story text."""
        positives, _ = pt.positive_constraints(
            ["Latin text", "mirrored Arabic"], has_copy=True
        )
        self.assertEqual([pt.TEXT_REWRITE_WITH_COPY], positives)
        self.assertNotIn(pt.TEXT_REWRITE_WORDLESS, positives)

    def test_a_compiled_page_with_copy_never_claims_the_surfaces_are_blank(self) -> None:
        page = dict(PAGE, inImageText="عبد الله رتب لعبه", textSurface="wooden sign")
        for target in pt.TARGETS:
            with self.subTest(target=target):
                compiled = pipeline.build_compiled_prompt(
                    dict(page), orientation="landscape", target=target
                ).lower()
                self.assertNotIn("blank and wordless", compiled)
                self.assertNotIn("no visible writing", compiled)


class TailCheckTests(unittest.TestCase):
    def test_the_canary_is_a_prop_the_page_already_requires(self) -> None:
        canary = pt.tail_check(PAGE)
        self.assertEqual("a half-eaten date on a paper napkin", canary)
        self.assertIn(canary, PAGE["scene"]["propsInFrame"])

    def test_a_page_with_no_props_falls_back_to_the_foreground(self) -> None:
        payload = {"scene": {"foreground": "grey paving stones", "propsInFrame": []}}
        self.assertEqual("grey paving stones", pt.tail_check(payload))


class CompiledVariantTests(unittest.TestCase):
    def test_a_project_compiled_before_targets_existed_still_reads(self) -> None:
        legacy = {"compiledPrompt": "an old single render"}
        self.assertEqual({"chatgpt": "an old single render"}, pt.compiled_variants(legacy))
        self.assertEqual(
            "an old single render", pt.compiled_for(legacy, "nanobanana")
        )

    def test_a_missing_target_falls_back_rather_than_shipping_nothing(self) -> None:
        payload = {"compiledPrompts": {"chatgpt": "labelled render"}}
        self.assertEqual("labelled render", pt.compiled_for(payload, "nanobanana"))

    def test_nothing_compiled_is_an_error_not_an_empty_prompt(self) -> None:
        with self.assertRaises(pt.TargetError):
            pt.compiled_for({}, "chatgpt")


class ManualDispatchTargetTests(unittest.TestCase):
    def _message(self, target: str) -> str:
        payload = dict(PAGE)
        payload["compiledPrompts"] = {t: render(t) for t in pt.TARGETS}
        return manual_dispatch.render_manual_instruction(
            payload,
            asset_id="page-05",
            character_sheet_path="/abs/sheet.png",
            target=target,
        )

    def test_the_message_names_the_tool_it_was_written_for(self) -> None:
        self.assertIn("Nano Banana Pro", self._message("nanobanana"))
        self.assertIn("ChatGPT", self._message("chatgpt"))

    def test_the_nano_banana_message_pastes_the_narrative_render(self) -> None:
        self.assertIn(render("nanobanana"), self._message("nanobanana"))

    def test_the_chatgpt_message_pastes_the_labelled_render(self) -> None:
        self.assertIn(render("chatgpt"), self._message("chatgpt"))

    def test_every_message_carries_the_truncation_canary(self) -> None:
        for target in pt.TARGETS:
            with self.subTest(target=target):
                self.assertIn("a half-eaten date on a paper napkin", self._message(target))

    def test_an_unknown_target_is_refused_before_anything_is_rendered(self) -> None:
        with self.assertRaises(manual_dispatch.ManualDispatchError):
            manual_dispatch.render_manual_instruction(
                dict(PAGE), asset_id="page-05", target="dall-e"
            )


if __name__ == "__main__":
    unittest.main()


class GamePageClauseTests(unittest.TestCase):
    """handoff §8 — an activity page has to be playable, not just look playable."""

    def _render(self, spec: dict, target: str = "chatgpt") -> str:
        page = dict(PAGE, gameSpec=spec)
        return pipeline.build_compiled_prompt(
            page, orientation="landscape", target=target
        )

    MAZE = {
        "kind": "maze",
        "startDescription": "the hero on the lit rooftop, lower left",
        "goalDescription": "the warm-windowed house, upper right",
        "elements": ["grey stone corridor walls one tile thick"],
    }

    def test_an_ordinary_page_gets_no_game_clause(self) -> None:
        self.assertNotIn(pt.GAME_PLAYABILITY_MARKER, render("chatgpt").lower())

    def test_every_target_carries_the_playability_rule(self) -> None:
        for target in pt.TARGETS:
            with self.subTest(target=target):
                self.assertIn(
                    pt.GAME_PLAYABILITY_MARKER, self._render(self.MAZE, target).lower()
                )

    def test_a_maze_states_the_single_route_and_its_two_ends(self) -> None:
        compiled = self._render(self.MAZE).lower()
        self.assertIn("exactly one open route", compiled)
        self.assertIn("lit rooftop", compiled)
        self.assertIn("warm-windowed house", compiled)

    def test_the_solution_is_never_drawn(self) -> None:
        """A maze printed with its route traced is a wasted page."""
        compiled = self._render(self.MAZE).lower()
        self.assertIn("never mark, trace, circle or number the answer", compiled)
        self.assertIn("never the path", compiled)

    def test_declared_elements_travel_verbatim(self) -> None:
        """The agent writes the elements; the model must not invent its own."""
        compiled = self._render(self.MAZE)
        self.assertIn("grey stone corridor walls one tile thick", compiled)
        self.assertIn("inventing nothing", compiled)

    def test_spot_the_difference_carries_its_count_and_its_list(self) -> None:
        compiled = self._render(
            {
                "kind": "spot-the-difference",
                "differenceCount": 2,
                "differences": ["the red truck loses a wheel", "the lamp turns off"],
                "elements": ["two panels side by side on a star rug"],
            }
        ).lower()
        self.assertIn("exactly 2 differences", compiled)
        self.assertIn("the lamp turns off", compiled)

    def test_search_and_find_lists_its_targets(self) -> None:
        compiled = self._render(
            {
                "kind": "search-and-find",
                "targetItems": ["three yellow stars", "one blue robot"],
                "elements": ["a toy-strewn bedroom floor"],
            }
        ).lower()
        self.assertIn("three yellow stars", compiled)
        self.assertIn("fully visible and countable", compiled)

    def test_an_unknown_game_kind_is_ignored_not_guessed(self) -> None:
        """A typo must not silently compile a page with no playability rules."""
        compiled = self._render({"kind": "sudoku", "elements": ["a grid"]}).lower()
        self.assertNotIn(pt.GAME_PLAYABILITY_MARKER, compiled)

    def test_the_game_clause_survives_the_length_shedding_pass(self) -> None:
        """Priority 0 — a bounded prompt drops colour notes before playability."""
        sections = [(0, pt.game_spec_clause(dict(PAGE, gameSpec=self.MAZE)))]
        sections += [(5, "x" * 4000)]
        prompt, shed = pt.assemble(sections, cap=1200)
        self.assertTrue(shed)
        self.assertIn(pt.GAME_PLAYABILITY_MARKER, prompt.lower())
