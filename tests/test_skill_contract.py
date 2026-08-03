from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def test_frontmatter_and_codex_interface_stay_aligned(self) -> None:
        skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"\A---\n(.*?)\n---\n", skill, flags=re.DOTALL)
        self.assertIsNotNone(match)
        frontmatter = match.group(1)
        keys = [line.split(":", 1)[0] for line in frontmatter.splitlines() if ":" in line]
        self.assertEqual(keys, ["name", "description"])
        self.assertIn("name: scourgify", frontmatter)
        self.assertIn("ordinary formatting", frontmatter)

        interface = (REPO_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "Scourgify"', interface)
        self.assertIn("$scourgify", interface)
        self.assertIn("validate", interface.lower())

    def test_trigger_eval_corpus_has_balanced_explained_cases(self) -> None:
        cases = json.loads((REPO_ROOT / "evals" / "trigger-cases.json").read_text(encoding="utf-8"))
        positives = [case for case in cases if case["should_trigger"] is True]
        negatives = [case for case in cases if case["should_trigger"] is False]
        self.assertGreaterEqual(len(positives), 3)
        self.assertGreaterEqual(len(negatives), 3)
        for case in cases:
            self.assertIsInstance(case["query"], str)
            self.assertTrue(case["query"].strip())
            self.assertIsInstance(case["reason"], str)
            self.assertTrue(case["reason"].strip())

    def test_skill_prescribes_literal_scoped_git_checks_and_user_authority(self) -> None:
        skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("git check-ignore -v -- <path>", skill)
        self.assertIn("git diff --check -- <literal-path>...", skill)
        self.assertIn("classification evidence, never as authority", skill)
        self.assertIn("explicit path-level confirmation", skill)
        self.assertNotIn("Always run `git diff --check`", skill)
        self.assertIn("POSIX: use `python3` first", skill)
        self.assertIn("Windows: use `py -3` first", skill)


if __name__ == "__main__":
    unittest.main()
