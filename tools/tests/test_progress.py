from __future__ import annotations

import argparse
import copy
import importlib.util
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


progress = _load("progress")
pipeline = _load("story_pipeline")


def book(**overrides) -> dict:
    """Minimal manifest shaped like the real one, with nothing done yet."""
    assets = [
        {"id": "character-sheet", "status": "planned", "includeInPdf": False},
        {"id": "location-sheet-01", "status": "planned", "includeInPdf": False},
        {"id": "cover", "status": "planned", "includeInPdf": True},
        {"id": "page-01", "status": "planned", "includeInPdf": True},
        {"id": "page-02", "status": "planned", "includeInPdf": True},
        {"id": "back-cover", "status": "planned", "includeInPdf": True},
    ]
    base = {
        "assets": assets,
        "consent": {"confirmed": False},
        "storyGoal": None,
        "storyPath": None,
        "review": {"status": "not_started", "pass": 0, "fixQueue": []},
        "pdf": {
            "draft": {"status": "planned", "path": None},
            "final": {"status": "planned", "path": None},
        },
    }
    base.update(overrides)
    return base


def render(ids: list[str], manifest: dict) -> dict:
    for asset in manifest["assets"]:
        if asset["id"] in ids:
            asset["imagePath"] = f"output/images/{asset['id']}.png"
            asset["status"] = "generated"
    return manifest


class PhaseWeightTests(unittest.TestCase):
    def test_weights_sum_to_one_hundred(self) -> None:
        self.assertEqual(sum(p.weight for p in progress.PHASES), 100)

    def test_fresh_book_is_low_but_not_zero(self) -> None:
        payload = progress.book_progress(book())
        self.assertGreater(payload["percent"], 0)
        self.assertLess(payload["percent"], 10)
        self.assertEqual(payload["phase"], "setup")

    def test_finished_book_reaches_one_hundred(self) -> None:
        manifest = render(
            ["character-sheet", "location-sheet-01", "cover", "page-01", "page-02", "back-cover"],
            book(
                storyGoal={"mode": "educational"},
                storyPath="input/story.json",
                consent={"confirmed": True},
                review={"status": "passed", "pass": 1, "fixQueue": []},
                pdf={
                    "draft": {"status": "verified", "path": "output/pdf/draft.pdf"},
                    "final": {"status": "verified", "path": "output/pdf/final.pdf"},
                },
            ),
        )
        for asset in manifest["assets"]:
            asset["status"] = "accepted" if asset["id"] == "character-sheet" else "generated"
        payload = progress.book_progress(manifest)
        self.assertEqual(payload["percent"], 100)
        self.assertIn("١٠٠", payload["messageAr"])

    def test_percent_never_decreases_along_the_real_flow(self) -> None:
        """Each step of the pipeline must move the bar forward, never back."""
        steps: list[dict] = []
        manifest = book()

        def snapshot() -> None:
            # Deep copy: the assets list is mutated in place below, and a shallow
            # copy would make every snapshot show the final state.
            steps.append(copy.deepcopy(manifest))

        snapshot()
        manifest["storyGoal"] = {"mode": "educational"}
        snapshot()
        manifest["consent"] = {"confirmed": True}
        snapshot()
        manifest["storyPath"] = "input/story.json"
        snapshot()
        for asset in manifest["assets"]:
            asset["status"] = "prompted"
        snapshot()
        render(["character-sheet"], manifest)
        manifest["assets"][0]["status"] = "accepted"
        snapshot()
        render(["location-sheet-01"], manifest)
        snapshot()
        render(["page-01", "page-02"], manifest)
        snapshot()
        render(["cover", "back-cover"], manifest)
        snapshot()
        manifest["pdf"]["draft"] = {"status": "verified", "path": "d.pdf"}
        snapshot()
        manifest["review"] = {"status": "passed", "pass": 1, "fixQueue": []}
        snapshot()
        manifest["pdf"]["final"] = {"status": "verified", "path": "f.pdf"}
        snapshot()

        percents = [progress.book_progress(s)["percent"] for s in steps]
        # Every step must actually move the number, or the bar is decorative.
        self.assertEqual(len(set(percents)), len(percents), percents)
        for earlier, later in zip(percents, percents[1:]):
            self.assertLessEqual(earlier, later, percents)
        self.assertEqual(percents[-1], 100)

    def test_book_without_location_sheets_still_reaches_one_hundred(self) -> None:
        manifest = book(
            storyGoal={"mode": "entertainment"},
            storyPath="input/story.json",
            consent={"confirmed": True},
            review={"status": "manual_review", "pass": 1, "fixQueue": []},
            pdf={
                "draft": {"status": "verified", "path": "d"},
                "final": {"status": "verified", "path": "f"},
            },
        )
        manifest["assets"] = [a for a in manifest["assets"] if a["id"] != "location-sheet-01"]
        render(["character-sheet", "cover", "page-01", "page-02", "back-cover"], manifest)
        for asset in manifest["assets"]:
            asset["status"] = "accepted" if asset["id"] == "character-sheet" else "generated"
        self.assertEqual(progress.book_progress(manifest)["percent"], 100)


class EtaTests(unittest.TestCase):
    def test_eta_uses_measured_durations_when_present(self) -> None:
        manifest = book(storyPath="input/story.json", consent={"confirmed": True})
        manifest["assets"][0]["durationSec"] = 60
        manifest["assets"][0]["imagePath"] = "x.png"
        manifest["assets"][1]["durationSec"] = 100
        manifest["assets"][1]["imagePath"] = "y.png"
        self.assertEqual(progress.measured_image_seconds(manifest), 80)
        # 4 images left, 2 lanes → 2 rounds × 80s, plus pdf/review tail.
        eta = progress.eta_seconds(manifest, workers=2)
        self.assertGreaterEqual(eta, 160)

    def test_eta_falls_back_to_the_assumed_rate_with_no_history(self) -> None:
        self.assertIsNone(progress.measured_image_seconds(book()))
        self.assertGreater(progress.eta_seconds(book(), workers=6), 0)

    def test_bar_length_is_stable(self) -> None:
        for percent in (0, 33, 50, 99, 100):
            self.assertEqual(len(progress.render_bar(percent)), progress.BAR_WIDTH)


class AttachProgressTests(unittest.TestCase):
    """The CLI must attach progress without ever turning success into failure."""

    def test_missing_project_argument_is_a_no_op(self) -> None:
        args = argparse.Namespace()
        self.assertEqual(pipeline.attach_progress(args, {"ok": True}), {"ok": True})

    def test_unreadable_manifest_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(project=Path(tmp).resolve())
            self.assertEqual(pipeline.attach_progress(args, {"a": 1}), {"a": 1})

    def test_real_project_gets_a_progress_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp).resolve()
            personas = project / "personas"
            personas.mkdir()
            (personas / "hero.png").write_bytes(b"fixture")
            pipeline.command_init(argparse.Namespace(project=project, pages=6))
            result = pipeline.attach_progress(
                argparse.Namespace(project=project), {"ok": True}
            )
            self.assertIn("progress", result)
            self.assertIn("percent", result["progress"])
            self.assertEqual(result["progress"]["phase"], "setup")


if __name__ == "__main__":
    unittest.main()
