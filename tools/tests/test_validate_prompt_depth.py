"""The depth gate as the pipeline actually runs it, not just as a scorer.

`promptdepth` is unit-tested on its own in test_promptdepth.py. What this file
covers is the wiring: that `validate-prompts` refuses a thin prompts folder, that
it accepts a rich one, that `--min-depth` reaches the scorer, and that the
adjacent-page shot-variety rule fires — none of which the scorer can check alone.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "tools" / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pipeline = _load("story_pipeline")

THEME_FINGERPRINT = "premium whimsical children's storybook digital illustration"
STYLE_FINISH = (
    "rich saturated color, detailed joyful faces, warm-cool light mix, print-ready"
)

RICH_SCENE = {
    "place": "the school yard doorway with cream plaster walls and a painted iron gate",
    "timeOfDay": "early morning, low warm sun from the left",
    "lighting": "key light from the left window, warm golden, soft shadows with a cool blue fill",
    "atmosphere": "still air before the bell, dust hanging in the light",
    "foreground": "a chipped grey concrete step and a red plastic lunchbox lying open",
    "midground": "the green painted iron gate on worn stone hinges, half swung inward",
    "background": "four tall ficus trees against a pale sky above the arcade",
    "backdropDetails": (
        "chalk marks fading on the wall, a blue bench with peeling paint, a "
        "sparrow on the ledge, scuffed tile grout, a hanging rope"
    ),
    "propsInFrame": [
        "blue sponge ball, compressed in his fist",
        "green painted iron gate, rust blooming at the lower hinge",
        "red plastic lunchbox, open and half-full",
    ],
}


def rich_prompt(asset_id: str, *, shot: str, view: str, participants: bool = True) -> dict:
    payload: dict = {
        "schemaVersion": 1,
        "assetId": asset_id,
        "version": 1,
        "useCase": "illustration-story",
        "narrativeBeat": "Ahmed hesitates at the classroom door because the room went quiet",
        "primaryRequest": "Ahmed grips the blue sponge ball and steps through the green gate",
        "locationId": "school-yard",
        "participants": (
            [{"id": "persona-01", "displayName": "أحمد", "role": "hero", "onPage": True}]
            if participants
            else []
        ),
        "guests": [],
        "identityLocks": {
            "persona-01": {
                "face": "match the persona-01 photo exactly, round jaw and wide brown eyes",
                "hair": "short black hair cropped close above the ears",
            }
        }
        if participants
        else {},
        "fixedOutfits": {
            "persona-01": "green cotton t-shirt and blue denim trousers with white trainers"
        }
        if participants
        else {},
        "actionAndEmotion": {
            "persona-01": {
                "action": "stands square in the doorway, both hands closed around the ball",
                "emotion": "held breath, shoulders lifted, eyes wide",
            }
        }
        if participants
        else {},
        "scene": copy.deepcopy(RICH_SCENE),
        "style": {
            "medium": THEME_FINGERPRINT,
            "finish": STYLE_FINISH,
            "immutable": True,
        },
        "composition": {
            "orientation": "landscape",
            "shotScale": shot,
            "viewpoint": view,
            "focalHierarchy": "Ahmed, the gate, the trees",
            "lens": "35mm-equivalent, slight wide, no edge distortion",
            "depthOfField": "Ahmed sharp, the arcade softly out of focus",
        },
        "palette": "teal, warm sand, muted gold",
        "colorScript": "the gold leans warmer as he decides to step through",
        "continuity": {
            "fromPreviousPage": "Ahmed still carries the blue sponge ball from the yard",
            "recurringProps": ["blue sponge ball"],
            "propStates": {"blue sponge ball": "compressed"},
        },
        "constraints": ["exactly listed participants only — no extra people"],
        "avoid": ["extra people", "identity drift", "malformed hands"],
        "compiledPrompt": "",
    }
    return payload


class DepthGateIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()
        personas = self.project / "personas"
        personas.mkdir()
        (personas / "ahmed.png").write_bytes(b"fixture")
        pipeline.command_init(argparse.Namespace(project=self.project, pages=5))

        # validate-prompts only needs a locked storyPath plus the story file to
        # cross-check participants and locations, so the lock chain is set
        # directly here rather than replayed command by command.
        book = pipeline.load_book(self.project)
        book["storyPath"] = "input/story.json"
        book["consent"] = {"confirmed": True, "statement": "ok", "confirmedAt": "now"}
        pipeline.save_book(self.project, book)
        self.asset_ids = [a["id"] for a in book["assets"]]

        story = {
            "pages": [
                {
                    "id": asset_id,
                    "participants": ["persona-01"],
                    "locationId": "school-yard",
                }
                for asset_id in self.asset_ids
                if asset_id != "character-sheet"
            ]
        }
        pipeline.atomic_json(self.project / "input" / "story.json", story)

        brief_path = self.project / "input" / "brief.json"
        brief = pipeline.read_json(brief_path)
        brief["themeId"] = "storybook"
        pipeline.atomic_json(brief_path, brief)

    def write_prompts(self, mutate=None) -> None:
        """Write one rich prompt per asset, alternating shot scale and viewpoint."""
        shots = [("wide", "eye-level"), ("medium", "low"), ("close", "high")]
        book = pipeline.load_book(self.project)
        for index, asset in enumerate(book["assets"]):
            shot, view = shots[index % len(shots)]
            payload = rich_prompt(
                asset["id"],
                shot=shot,
                view=view,
                participants=not asset["id"].startswith("location-sheet-"),
            )
            if mutate:
                payload = mutate(asset["id"], payload) or payload
            pipeline.atomic_json(
                self.project / asset["promptPath"], payload
            )
        pipeline.command_compile_prompts(argparse.Namespace(project=self.project))

    def validate(self, **kwargs):
        return pipeline.command_validate_prompts(
            argparse.Namespace(project=self.project, **kwargs)
        )

    def test_rich_prompts_pass_and_report_their_score(self) -> None:
        self.write_prompts()
        result = self.validate(min_depth=None)
        self.assertTrue(result["valid"])
        self.assertGreaterEqual(result["depth"]["min"], 70)
        self.assertEqual(len(result["depth"]["weakest"]), 3)

    def test_a_vague_scene_blocks_the_whole_folder(self) -> None:
        def make_thin(asset_id: str, payload: dict):
            if asset_id == "page-01":
                payload["scene"]["lighting"] = "nice beautiful light in the room"
            return payload

        self.write_prompts(make_thin)
        with self.assertRaises(pipeline.WorkflowError) as caught:
            self.validate(min_depth=None)
        message = str(caught.exception)
        self.assertIn("scene.lighting", message)
        self.assertIn("page-01", message)

    def test_change_stubs_are_rejected(self) -> None:
        def make_stub(asset_id: str, payload: dict):
            if asset_id == "page-02":
                payload["scene"]["foreground"] = "CHANGE: near objects with material"
            return payload

        self.write_prompts(make_stub)
        with self.assertRaises(pipeline.WorkflowError) as caught:
            self.validate(min_depth=None)
        self.assertIn("CHANGE stub", str(caught.exception))

    def test_adjacent_pages_may_not_share_scale_and_viewpoint(self) -> None:
        def flatten(asset_id: str, payload: dict):
            payload["composition"]["shotScale"] = "medium"
            payload["composition"]["viewpoint"] = "eye-level"
            return payload

        self.write_prompts(flatten)
        with self.assertRaises(pipeline.WorkflowError) as caught:
            self.validate(min_depth=None)
        self.assertIn("repeats the previous page's shot", str(caught.exception))

    def test_strict_depth_requires_the_recommended_fields(self) -> None:
        """The lever: recommended fields are optional by default, required at 95.

        This is the whole point of scoring them instead of only warning — a
        warning that costs nothing is a warning nobody acts on.
        """

        def drop_recommended(asset_id: str, payload: dict):
            payload["composition"].pop("lens", None)
            payload["composition"].pop("depthOfField", None)
            payload.pop("colorScript", None)
            return payload

        self.write_prompts(drop_recommended)
        relaxed = self.validate(min_depth=None)
        self.assertTrue(relaxed["valid"])
        self.assertLess(relaxed["depth"]["min"], 95)
        self.assertTrue(any("lens" in w for w in relaxed["warnings"]), relaxed["warnings"])

        with self.assertRaises(pipeline.WorkflowError) as caught:
            self.validate(min_depth=95)
        self.assertIn("under the 95 minimum", str(caught.exception))

    def test_fully_filled_prompts_reach_the_strict_bar(self) -> None:
        self.write_prompts()
        self.assertTrue(self.validate(min_depth=95)["valid"])

    def test_compiled_prompt_carries_the_new_precision_fields(self) -> None:
        self.write_prompts()
        payload = json.loads(
            (self.project / "input" / "prompts" / "page-01.v01.json").read_text(
                encoding="utf-8"
            )
        )
        compiled = payload["compiledPrompt"]
        self.assertIn("35mm-equivalent", compiled)
        self.assertIn("softly out of focus", compiled)
        self.assertIn("Colour emphasis for this beat only", compiled)


if __name__ == "__main__":
    unittest.main()
