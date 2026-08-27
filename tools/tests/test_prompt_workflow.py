from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "tools" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import prompt_workflow as workflow  # noqa: E402


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class PromptWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.rawy = self.root / "Rawy"
        self.project = self.rawy / "Clients" / "sample"
        self.project.mkdir(parents=True)
        write_json(
            self.project / "input/brief.json",
            {"themeId": "storybook", "visualStyle": "warm"},
        )
        self.prompt = self.project / "input/prompts/page-02.v01.json"
        write_json(
            self.prompt,
            {
                "schemaVersion": 2,
                "assetId": "page-02",
                "compiledPrompt": "Draw a clean blank wall frame. Render no text.",
                "inputImages": [],
                "textIntegration": {
                    "version": 1,
                    "mode": "scene-surface",
                    "carrierKind": "wall-frame",
                    "carrierDescription": "برواز",
                    "rationaleAr": "طبيعي",
                    "plannedRegion": {"x": 0.5, "y": 0.1, "width": 0.4, "height": 0.5},
                },
            },
        )
        self.book = {
            "storyReview": {
                "status": "approved",
                "approvedStorySha256": "a" * 64,
            },
            "briefPath": "input/brief.json",
            "settings": {},
            "assets": [
                {
                    "id": "page-02",
                    "promptPath": "input/prompts/page-02.v01.json",
                    "promptVersion": 1,
                    "storyText": "كان يا مكان",
                }
            ],
        }
        workflow.initialize_book_state(self.book)

    def test_pack_approval_is_hash_bound_and_prompt_change_is_stale(self) -> None:
        prepared = workflow.prepare_prompt_review(self.project, self.book)
        self.assertEqual("awaiting_user", prepared["status"])
        approved = workflow.approve_prompts(self.project, self.book, "موافق على الحزمة")
        self.assertEqual("approved", approved["status"])
        payload = json.loads(self.prompt.read_text(encoding="utf-8"))
        payload["compiledPrompt"] += " changed"
        write_json(self.prompt, payload)
        self.assertEqual(
            "changes_detected",
            workflow.prompt_review_status(self.project, self.book)["status"],
        )

    def test_notes_block_approval_until_new_prompt_version(self) -> None:
        workflow.prepare_prompt_review(self.project, self.book)
        note = workflow.asset_review_path(self.project, "page-02")
        text = note.read_text(encoding="utf-8").replace(
            "<!-- rawy-prompt:notes:start -->\n",
            "<!-- rawy-prompt:notes:start -->\nكبّر البرواز\n",
        )
        note.write_text(text, encoding="utf-8")
        status = workflow.prompt_review_status(self.project, self.book)
        self.assertEqual("feedback_pending", status["status"])
        with self.assertRaises(workflow.PromptWorkflowError):
            workflow.approve_prompts(self.project, self.book, "موافق")

    def test_lane_has_no_default_and_requires_current_approval(self) -> None:
        workflow.prepare_prompt_review(self.project, self.book)
        workflow.approve_prompts(self.project, self.book, "موافق على الحزمة")
        self.assertIsNone(workflow.selected_lane(self.book))
        selected = workflow.set_image_lane(
            self.project,
            self.book,
            lane="manual",
            statement="هعمل الصور يدوي",
        )
        self.assertEqual("manual", selected["lane"])
        self.assertEqual(
            "manual",
            workflow.require_lane(self.project, self.book, expected="manual"),
        )

    def test_learning_redacts_client_path_and_activates_explicit_rule(self) -> None:
        result = workflow.record_learning(
            self.rawy,
            self.project,
            self.book,
            asset_id="page-02",
            statement=f"اتعلم الموضوع ده: كبّر السطح بعيد عن {self.project}",
            category="surface",
            accepted=True,
            before_sha256="b" * 64,
            after_sha256="c" * 64,
        )
        self.assertEqual("active", result["rule"]["status"])
        saved = Path(result["path"]).read_text(encoding="utf-8")
        self.assertNotIn(str(self.project), saved)

    def test_carriers_vary_and_games_use_native_mode(self) -> None:
        first = workflow.text_integration_plan(
            "page-02", {"beat": "home scene"}, story_text="قصير", narrative_index=0
        )
        second = workflow.text_integration_plan(
            "page-03", {"beat": "home scene"}, story_text="قصير", narrative_index=1
        )
        game = workflow.text_integration_plan(
            "page-20", {"beat": "maze game page"}, story_text="ساعده", narrative_index=2
        )
        self.assertNotEqual(first["carrierKind"], second["carrierKind"])
        self.assertEqual("game-native", game["mode"])


class InImageTextDefaultTests(unittest.TestCase):
    """Every new book renders its Arabic inside the artwork — there is no opt-in."""

    def test_a_fresh_book_declares_in_image_text(self) -> None:
        book: dict = {}
        workflow.initialize_book_state(book)
        self.assertEqual("in-image", book["settings"]["textRendering"])

    def test_an_existing_choice_is_not_overwritten(self) -> None:
        book = {"settings": {"textRendering": "legacy-carrier"}}
        workflow.initialize_book_state(book)
        self.assertEqual("legacy-carrier", book["settings"]["textRendering"])



class GamePageDetectionTests(unittest.TestCase):
    """handoff §8 — a game page that is never detected never has to be authored.

    `validate-prompts` only demands a `gameSpec` on pages this classifier calls
    `game-native`. It used to read `role/pageType/beat/setting` and not `text`,
    so the instruction the child actually reads — «ساعد سما توصل للفصل» — was
    invisible and the requirement quietly never fired.
    """

    def _mode(self, **page) -> str:
        return workflow.integration_mode("page-07", page)

    def test_the_instruction_in_the_page_text_is_what_makes_it_a_game(self) -> None:
        for text in (
            "ساعد سما توصل للفصل",
            "دوّر على الحاجات المخبية",
            "لاقي ٥ اختلافات بين الصورتين",
            "وصّل كل حيوان بأكله",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    "game-native", self._mode(beat="sama walks to class", text=text)
                )

    def test_the_named_puzzle_kinds_are_all_recognised(self) -> None:
        for beat in (
            "maze to the classroom",
            "spot the difference between the two yards",
            "search-and-find in the toy room",
            "متاهة الوصول للفصل",
        ):
            with self.subTest(beat=beat):
                self.assertEqual("game-native", self._mode(beat=beat, text="…"))

    def test_ordinary_narration_is_not_a_game(self) -> None:
        """A suffixed verb is a story sentence, not an instruction to the reader."""
        for text in (
            "ماما ساعدت أخوها",
            "سما ساعدتني أرتب اللعب",
            "سما دوّرت على الكورة",
            "سما نامت بدري",
        ):
            with self.subTest(text=text):
                self.assertEqual("scene-surface", self._mode(beat="bedtime", text=text))

    def test_an_explicit_pageType_beats_the_heuristic_both_ways(self) -> None:
        # The escape hatch the validator's error message points at.
        self.assertEqual(
            "scene-surface",
            self._mode(beat="bedtime", text="ماما ساعد أخوك", pageType="story"),
        )
        self.assertEqual(
            "game-native",
            self._mode(beat="quiet room", text="سما نامت بدري", pageType="game"),
        )

    def test_sheets_and_fixed_pages_are_never_game_pages(self) -> None:
        for asset_id in ("character-sheet", "location-sheet-01"):
            self.assertEqual("none", workflow.integration_mode(asset_id, {}))
        for asset_id in ("cover", "page-01", "page-22", "back-cover"):
            self.assertEqual(
                "designed-page",
                workflow.integration_mode(asset_id, {"text": "ساعد سما"}),
            )


if __name__ == "__main__":
    unittest.main()
