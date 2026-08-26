from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "scripts" / "promptdepth.py"
SPEC = importlib.util.spec_from_file_location("promptdepth", MODULE_PATH)
assert SPEC and SPEC.loader
pd = importlib.util.module_from_spec(SPEC)
sys.modules["promptdepth"] = pd
SPEC.loader.exec_module(pd)


# A page prompt filled the way the guide demands: every field names a specific
# thing, with colour, material, and light direction where the field calls for it.
RICH_PAGE: dict = {
    "assetId": "page-02",
    "narrativeBeat": "Ahmed hesitates at the classroom door because the room has gone quiet",
    "primaryRequest": "Ahmed grips the blue sponge ball while Mona holds the green gate open",
    "participants": [
        {"id": "persona-01", "displayName": "أحمد", "onPage": True},
        {"id": "persona-02", "displayName": "منى", "onPage": True},
    ],
    "identityLocks": {
        "persona-01": {
            "face": "match the persona-01 photo exactly, same round jaw and wide brown eyes",
            "hair": "short black hair cropped close above the ears",
        },
        "persona-02": {
            "face": "match the persona-02 photo exactly, narrow chin and high cheekbones",
            "hair": "long dark brown braid tied with a red band",
        },
    },
    "fixedOutfits": {
        "persona-01": "green cotton t-shirt and blue denim trousers with white trainers",
        "persona-02": "yellow linen dress with a teal cardigan and brown leather sandals",
    },
    "actionAndEmotion": {
        "persona-01": {
            "action": "stands square in the doorway, both hands closed around the ball",
            "emotion": "held breath, shoulders lifted, eyes wide",
        },
        "persona-02": {
            "action": "leans her weight on the open gate, arm stretched behind her",
            "emotion": "patient half-smile, chin tipped toward him",
        },
    },
    "scene": {
        "place": "the school yard doorway with cream plaster walls and a painted iron gate",
        "timeOfDay": "early morning, low warm sun from the left",
        "lighting": "key light from the left window, warm golden, soft shadows with a cool blue fill",
        "atmosphere": "still air before the bell, dust hanging in the light",
        "foreground": "a chipped grey concrete step and a red plastic lunchbox lying open",
        "midground": "the green painted iron gate on worn stone hinges, half swung inward",
        "background": "four tall ficus trees against a pale sky above the arcade",
        "backdropDetails": (
            "chalk marks fading on the wall, a blue bench with peeling paint, "
            "a sparrow on the ledge, scuffed tile grout, a hanging rope"
        ),
        "propsInFrame": [
            "blue sponge ball, compressed in his fist",
            "green painted iron gate, rust blooming at the lower hinge",
            "red plastic lunchbox, open and half-full",
        ],
    },
    "palette": "teal, warm sand, muted gold",
    "composition": {"shotScale": "medium", "viewpoint": "eye-level", "focalHierarchy": "Ahmed, gate, trees"},
    "continuity": {"fromPreviousPage": "Ahmed still carries the blue sponge ball from the yard"},
}


def page(**changes) -> dict:
    payload = copy.deepcopy(RICH_PAGE)
    for dotted, value in changes.items():
        path = dotted.split("__")
        node = payload
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = value
    return payload


class RichPromptTests(unittest.TestCase):
    def test_a_fully_specified_page_passes(self) -> None:
        report = pd.gate(RICH_PAGE, asset_id="page-02")
        self.assertTrue(report.ok, report.failures)
        self.assertGreaterEqual(report.score, pd.DEFAULT_MIN_SCORE)


class ThinPromptTests(unittest.TestCase):
    def test_vague_lighting_is_rejected_by_name(self) -> None:
        report = pd.gate(page(scene__lighting="nice beautiful light everywhere in the room"), asset_id="page-02")
        self.assertFalse(report.ok)
        self.assertTrue(any("scene.lighting" in f for f in report.failures), report.failures)

    def test_short_field_is_rejected_with_its_word_count(self) -> None:
        report = pd.gate(page(scene__foreground="a step"), asset_id="page-02")
        self.assertFalse(report.ok)
        self.assertTrue(any("scene.foreground is 2 words" in f for f in report.failures), report.failures)

    def test_change_stub_is_caught(self) -> None:
        report = pd.gate(page(scene__place="CHANGE: specific named location"), asset_id="page-02")
        self.assertFalse(report.ok)
        self.assertTrue(any("CHANGE stub" in f for f in report.failures), report.failures)

    def test_props_without_material_or_colour_are_rejected(self) -> None:
        thin = page()
        thin["scene"]["propsInFrame"] = ["a ball", "a gate", "a box"]
        report = pd.gate(thin, asset_id="page-02")
        self.assertFalse(report.ok)
        self.assertTrue(any("propsInFrame" in f for f in report.failures), report.failures)

    def test_too_few_props_are_rejected(self) -> None:
        thin = page()
        thin["scene"]["propsInFrame"] = ["blue sponge ball, worn cotton cover"]
        report = pd.gate(thin, asset_id="page-02")
        self.assertFalse(report.ok)
        self.assertTrue(any("needs 3" in f for f in report.failures), report.failures)

    def test_outfit_without_a_colour_is_rejected(self) -> None:
        thin = page()
        thin["fixedOutfits"]["persona-01"] = "a shirt and trousers he wears every single day"
        report = pd.gate(thin, asset_id="page-02")
        self.assertFalse(report.ok)
        self.assertTrue(any("colour" in f for f in report.failures), report.failures)

    def test_arabic_filler_is_caught_too(self) -> None:
        thin = page()
        # Long enough to clear the word floor, so the filler check is what fires.
        thin["scene"]["backdropDetails"] = (
            "بعض التفاصيل جميلة حوالين المكان وحاجات تانية كتير في الخلفية "
            "ومناظر حلوة على الجناب وكمان أشياء مناسبة في الركن البعيد"
        )
        report = pd.gate(thin, asset_id="page-02")
        self.assertFalse(report.ok)
        self.assertTrue(any("filler" in f for f in report.failures), report.failures)

    def test_missing_continuity_blocks_pages_after_the_first(self) -> None:
        thin = page()
        thin["continuity"] = {}
        self.assertFalse(pd.gate(thin, asset_id="page-02").ok)
        # page-01 has no previous page, so the same payload is fine there.
        first = copy.deepcopy(thin)
        first["assetId"] = "page-01"
        self.assertTrue(pd.gate(first, asset_id="page-01").ok, pd.gate(first, asset_id="page-01").failures)


class SheetTests(unittest.TestCase):
    def test_character_sheet_is_not_asked_for_a_background(self) -> None:
        sheet = {
            "assetId": "character-sheet",
            "primaryRequest": "five views of each child on a neutral field",
            "participants": RICH_PAGE["participants"],
            "identityLocks": RICH_PAGE["identityLocks"],
            "fixedOutfits": RICH_PAGE["fixedOutfits"],
            "scene": {
                "lighting": "even soft key from the front left, warm white, no hard shadows",
                "propsInFrame": [],
            },
            "palette": "teal, warm sand, muted gold",
        }
        report = pd.gate(sheet, asset_id="character-sheet")
        self.assertTrue(report.ok, report.failures)

    def test_location_sheet_is_not_asked_for_people(self) -> None:
        location = {
            "assetId": "location-sheet-01",
            "primaryRequest": "the empty school yard doorway with no people present",
            "participants": [],
            "scene": copy.deepcopy(RICH_PAGE["scene"]),
            "palette": "teal, warm sand, muted gold",
        }
        report = pd.gate(location, asset_id="location-sheet-01")
        self.assertTrue(report.ok, report.failures)

    def test_sheets_use_the_lower_threshold(self) -> None:
        self.assertEqual(pd.minimum_score("character-sheet"), pd.SHEET_MIN_SCORE)
        self.assertEqual(pd.minimum_score("location-sheet-03"), pd.SHEET_MIN_SCORE)
        self.assertEqual(pd.minimum_score("page-07"), pd.DEFAULT_MIN_SCORE)


class HelperTests(unittest.TestCase):
    def test_vague_hits_are_word_bounded(self) -> None:
        # "some" inside "something" is not the filler word "some".
        self.assertEqual(pd.vague_hits("a handsome carved stool"), [])
        self.assertIn("some", pd.vague_hits("some carved stools"))

    def test_word_count_handles_arabic(self) -> None:
        self.assertEqual(pd.word_count("كورة إسفنج زرقاء"), 3)

    def test_threshold_override_is_honoured(self) -> None:
        thin = {"assetId": "page-03", "participants": []}
        self.assertFalse(pd.gate(thin, asset_id="page-03", threshold=0).ok is None)
        # A zero threshold still cannot rescue a payload with real field failures.
        self.assertFalse(pd.gate(thin, asset_id="page-03", threshold=0).ok)


if __name__ == "__main__":
    unittest.main()
