"""The instruction layer is a token budget, so it gets a test.

Three failures kept coming back by hand and each one costs real tokens on every
single session:

* **Duplication.** The same gate list written in `CLAUDE.md`, `AGENTS.md`, the
  Cursor rule and the skill. Four copies drift, and the agent reads all four.
* **Eager loading.** An entry-point file ordering a 30 KB document to be read
  before any work, whether or not the step needed it.
* **Dead and machine-specific pointers.** Links to files that were deleted, and
  absolute `/Users/...` paths that only work on one Mac.

These tests fail on all three.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The always-loaded entry points. Every byte here is spent on every session, so
# they stay pointers, not policy.
ENTRY_POINTS = (
    ROOT / "CLAUDE.md",
    ROOT / ".cursor/rules/hekayati.mdc",
)
CONTRACT = ROOT / "AGENTS.md"
SKILL = ROOT / ".agents/skills/hekayati/SKILL.md"
ADAPTERS = (
    ROOT / ".claude/skills/hekayati/SKILL.md",
    ROOT / ".cursor/skills/hekayati/SKILL.md",
)
REFERENCES = ROOT / "tools/references"

# Anything larger than this is a document, not an instruction, and must be
# reachable on demand rather than named as a prerequisite.
ENTRY_POINT_MAX_BYTES = 600
CONTRACT_MAX_BYTES = 4000
SKILL_MAX_BYTES = 6000
STAGE_FILE_MAX_BYTES = 20_000


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class EntryPointTests(unittest.TestCase):
    def test_entry_points_stay_pointers(self) -> None:
        for path in ENTRY_POINTS:
            self.assertTrue(path.is_file(), path)
            self.assertLessEqual(
                len(path.read_bytes()),
                ENTRY_POINT_MAX_BYTES,
                f"{path.name} is growing policy again — move it into AGENTS.md",
            )

    def test_entry_points_point_at_the_one_contract(self) -> None:
        for path in ENTRY_POINTS:
            self.assertIn("AGENTS.md", read(path), path)

    def test_only_one_file_owns_the_operator_rules(self) -> None:
        """A distinctive contract rule must appear in exactly one place."""
        owned = "Never invent progress, approvals, deadlines"
        holders = [
            p
            for p in (CONTRACT, SKILL, *ENTRY_POINTS, *ADAPTERS)
            if owned in read(p)
        ]
        self.assertEqual([CONTRACT], holders, "operator rules got duplicated")

    def test_contract_and_skill_stay_small(self) -> None:
        self.assertLessEqual(len(CONTRACT.read_bytes()), CONTRACT_MAX_BYTES)
        self.assertLessEqual(len(SKILL.read_bytes()), SKILL_MAX_BYTES)


class ProgressiveDisclosureTests(unittest.TestCase):
    def test_nothing_orders_the_big_documents_read_up_front(self) -> None:
        """No entry point may make a large reference a prerequisite."""
        big = {"agent-core.md", "handoff.md"}
        for path in (*ENTRY_POINTS, CONTRACT, SKILL):
            text = read(path)
            for line in text.splitlines():
                lowered = line.lower()
                if not any(name in line for name in big):
                    continue
                self.assertNotRegex(
                    lowered,
                    r"\b(read|load)\b.*\bfirst\b|\bbefore\b.*\b(any|every)\b.*\bwork\b",
                    f"{path.name} makes a large document a prerequisite: {line!r}",
                )

    def test_the_orientation_command_is_the_documented_first_step(self) -> None:
        for path in (CONTRACT, SKILL):
            self.assertIn("context --project", read(path), path)

    def test_agent_core_is_an_index_not_a_briefing(self) -> None:
        text = read(REFERENCES / "agent-core.md")
        self.assertLessEqual(
            len((REFERENCES / "agent-core.md").read_bytes()),
            4000,
            "agent-core.md is a briefing again; split it into workflow/",
        )
        for stage in ("workflow/routing.md", "workflow/story.md", "workflow/prompts.md"):
            self.assertIn(stage, text)

    def test_stage_files_exist_and_stay_loadable(self) -> None:
        for name in ("routing.md", "story.md", "prompts.md"):
            path = REFERENCES / "workflow" / name
            self.assertTrue(path.is_file(), path)
            self.assertLessEqual(len(path.read_bytes()), STAGE_FILE_MAX_BYTES, path)


class ReviewRubricTests(unittest.TestCase):
    def test_every_rubric_merge_reviews_demands_actually_exists(self) -> None:
        """`merge-reviews` requires four roles; each needs a written rubric."""
        for role in ("story", "arabic", "continuity", "pdf"):
            path = REFERENCES / "reviews" / f"{role}.md"
            self.assertTrue(
                path.is_file(),
                f"{role} rubric is missing but merge-reviews requires that role",
            )

    def test_the_review_loop_links_all_four(self) -> None:
        text = read(REFERENCES / "reviews" / "README.md")
        for role in ("story", "arabic", "continuity", "pdf"):
            self.assertIn(f"{role}.md", text)


class DeadPointerTests(unittest.TestCase):
    """Relative Markdown links inside the instruction layer must resolve."""

    LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

    def instruction_files(self) -> list[Path]:
        files = [CONTRACT, SKILL, ROOT / "README.md", ROOT / "tools/README.md"]
        files += sorted(REFERENCES.rglob("*.md"))
        return files

    def test_relative_links_resolve(self) -> None:
        broken: list[str] = []
        for path in self.instruction_files():
            for target in self.LINK.findall(read(path)):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                target = target.split("#", 1)[0]
                if not target:
                    continue
                resolved = (path.parent / target).resolve()
                if not resolved.exists():
                    broken.append(f"{path.relative_to(ROOT)} → {target}")
        self.assertEqual([], broken)

    def test_no_machine_specific_absolute_paths(self) -> None:
        """`/Users/<someone>/…` in a rule only works on one laptop."""
        offenders: list[str] = []
        pattern = re.compile(r"/Users/[A-Za-z0-9._-]+/")
        for path in self.instruction_files():
            for number, line in enumerate(read(path).splitlines(), 1):
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
        self.assertEqual([], offenders)

    def test_adapters_point_at_the_canonical_skill(self) -> None:
        for path in ADAPTERS:
            self.assertIn(".agents/skills/hekayati/SKILL.md", read(path), path)


if __name__ == "__main__":
    unittest.main()
