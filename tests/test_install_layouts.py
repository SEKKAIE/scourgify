from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ITEMS = ("SKILL.md", "agents", "assets", "references", "scripts")


class InstallLayoutTests(unittest.TestCase):
    def test_codex_claude_code_and_cursor_layouts_contain_complete_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            destinations = (
                home / ".codex" / "skills" / "scourgify",
                home / ".claude" / "skills" / "scourgify",
                home / ".cursor" / "skills" / "scourgify",
            )
            for destination in destinations:
                destination.mkdir(parents=True)
                for item in RUNTIME_ITEMS:
                    source = REPO_ROOT / item
                    target = destination / item
                    if source.is_dir():
                        shutil.copytree(source, target)
                    else:
                        shutil.copy2(source, target)

                self.assertTrue((destination / "SKILL.md").is_file())
                self.assertTrue((destination / "scripts" / "scourgify_scan.py").is_file())
                self.assertTrue((destination / "scripts" / "validate_closeout.py").is_file())
                self.assertTrue((destination / "references" / "closeout-ledger.md").is_file())
                self.assertTrue((destination / "assets" / "scourgify-hero-v1.png").is_file())
                result = subprocess.run(
                    [sys.executable, str(destination / "scripts" / "scourgify_scan.py"), "--self-test"],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
