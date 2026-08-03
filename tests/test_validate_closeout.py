from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.validate_closeout import validate


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_closeout.py"
SCANNER = REPO_ROOT / "scripts" / "scourgify_scan.py"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def snapshot(root: str, entries: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "repository": {"root": root},
        "scope": {
            "ignored": "not-inventoried",
            "nested_gitlinks": "not-inspected",
            "untracked": "all",
        },
        "entries": entries,
        "ignored_entries": [],
    }


def entry(path_id: str, path: str, category: str = "unknown") -> dict:
    return {"path_id": path_id, "path": path, "category": category}


def ledger_row(path_id: str, path: str) -> dict:
    return {
        "path_id": path_id,
        "path": path,
        "owner": "current task",
        "reason": "created by the requested change",
        "next_action": "keep",
        "evidence": "tests passed",
        "permission": "not-required",
    }


class CloseoutValidatorTests(unittest.TestCase):
    def test_before_and_after_scan_scopes_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before_value = snapshot("/repo", [])
            before_value["scope"]["ignored"] = "inventoried"
            before_value["ignored_entries"] = [entry("scg-secret", ".env", "dangerous")]
            after_value = snapshot("/repo", [])
            before = root / "before.json"
            after = root / "after.json"
            ledger = root / "ledger.json"
            write_json(before, before_value)
            write_json(after, after_value)
            write_json(ledger, [ledger_row("scg-secret", ".env")])

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--ledger",
                    str(ledger),
                    "--format",
                    "json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertFalse(report["complete"])
            self.assertIn("scope", "\n".join(report["errors"]).lower())

    def test_ignored_entries_are_rejected_when_inventory_is_disabled(self) -> None:
        before_value = snapshot("/repo", [])
        before_value["ignored_entries"] = [entry("scg-secret", ".env", "dangerous")]
        report = validate(before_value, snapshot("/repo", []), [])

        self.assertFalse(report["complete"])
        self.assertIn("must be empty", "\n".join(report["errors"]))

    def test_duplicate_ledger_identity_blocks_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.json"
            after = root / "after.json"
            ledger = root / "ledger.json"
            write_json(before, snapshot("/repo", [entry("scg-a", "a.txt")]))
            write_json(after, snapshot("/repo", [entry("scg-a", "a.txt")]))
            write_json(ledger, [ledger_row("scg-a", "a.txt"), ledger_row("scg-a", "a.txt")])

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--ledger",
                    str(ledger),
                    "--format",
                    "json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertEqual(report["duplicate_path_ids"], ["scg-a"])
            self.assertFalse(report["complete"])

    def test_new_after_path_missing_from_ledger_blocks_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.json"
            after = root / "after.json"
            ledger = root / "ledger.json"
            write_json(before, snapshot("/repo", [entry("scg-a", "a.txt")]))
            write_json(
                after,
                snapshot("/repo", [entry("scg-a", "a.txt"), entry("scg-b", "docs/HANDOFF.md", "doc-sync")]),
            )
            write_json(ledger, [ledger_row("scg-a", "a.txt")])

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--ledger",
                    str(ledger),
                    "--format",
                    "json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertFalse(report["complete"])
            self.assertEqual(report["counts"]["expected"], 2)
            self.assertEqual(report["counts"]["ledger"], 1)
            self.assertIn("scg-b", report["missing_path_ids"])

    def test_five_field_ledger_contract_and_permission_enum_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.json"
            after = root / "after.json"
            ledger = root / "ledger.json"
            write_json(before, snapshot("/repo", [entry("scg-a", "a.txt")]))
            write_json(after, snapshot("/repo", [entry("scg-a", "a.txt")]))
            invalid = ledger_row("scg-a", "a.txt")
            invalid.pop("reason")
            invalid["permission"] = "maybe"
            write_json(ledger, [invalid])

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--ledger",
                    str(ledger),
                    "--format",
                    "json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertFalse(report["complete"])
            joined = "\n".join(report["errors"])
            self.assertIn("reason", joined)
            self.assertIn("permission", joined)

    def test_ledger_path_must_match_snapshot_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.json"
            after = root / "after.json"
            ledger = root / "ledger.json"
            write_json(before, snapshot("/repo", [entry("scg-a", "actual.txt")]))
            write_json(after, snapshot("/repo", [entry("scg-a", "actual.txt")]))
            write_json(ledger, [ledger_row("scg-a", "different.txt")])

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--ledger",
                    str(ledger),
                    "--format",
                    "json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("path does not match", "\n".join(json.loads(result.stdout)["errors"]))

    def test_complete_ledger_reports_outstanding_permission_separately(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.json"
            after = root / "after.json"
            ledger = root / "ledger.json"
            write_json(before, snapshot("/repo", [entry("scg-secret", ".env", "dangerous")]))
            write_json(after, snapshot("/repo", [entry("scg-secret", ".env", "dangerous")]))
            row = ledger_row("scg-secret", ".env")
            row["next_action"] = "leave untouched pending user decision"
            row["evidence"] = "status and ignore-policy metadata only"
            row["permission"] = "required"
            write_json(ledger, [row])

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--ledger",
                    str(ledger),
                    "--format",
                    "json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["complete"])
            self.assertFalse(report["work_ready"])
            self.assertEqual(report["outstanding_permission_path_ids"], ["scg-secret"])

    def test_human_report_lists_outstanding_permission_path_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = root / "before.json"
            after = root / "after.json"
            ledger = root / "ledger.json"
            write_json(before, snapshot("/repo", [entry("scg-secret", ".env", "dangerous")]))
            write_json(after, snapshot("/repo", [entry("scg-secret", ".env", "dangerous")]))
            row = ledger_row("scg-secret", ".env")
            row["permission"] = "required"
            write_json(ledger, [row])

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--ledger",
                    str(ledger),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("work ready: no", result.stdout)
            self.assertIn("Outstanding Permissions", result.stdout)
            self.assertIn("scg-secret", result.stdout)

    def test_real_before_and_after_snapshots_reconcile_every_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "feature.py").write_text("print('feature')\n", encoding="utf-8")
            before_result = subprocess.run(
                [sys.executable, str(SCANNER), "--cwd", str(root), "--format", "json"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(before_result.returncode, 0, before_result.stderr)
            (root / "docs").mkdir()
            (root / "docs" / "HANDOFF.md").write_text("# Handoff\n", encoding="utf-8")
            after_result = subprocess.run(
                [sys.executable, str(SCANNER), "--cwd", str(root), "--format", "json"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(after_result.returncode, 0, after_result.stderr)

            before = root / "before.json"
            after = root / "after.json"
            ledger = root / "ledger.json"
            before.write_text(before_result.stdout, encoding="utf-8")
            after.write_text(after_result.stdout, encoding="utf-8")
            combined: dict[str, dict] = {}
            for snapshot_value in (json.loads(before_result.stdout), json.loads(after_result.stdout)):
                for item in snapshot_value["entries"]:
                    combined[item["path_id"]] = item
            write_json(
                ledger,
                [ledger_row(path_id, item["path"]) for path_id, item in sorted(combined.items())],
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--ledger",
                    str(ledger),
                    "--format",
                    "json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["complete"])
            self.assertTrue(report["work_ready"])
            self.assertEqual(report["counts"]["expected"], 2)
            self.assertEqual(report["counts"]["ledger"], 2)

    def test_opted_in_ignored_entries_are_part_of_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before_value = snapshot("/repo", [])
            before_value["scope"]["ignored"] = "inventoried"
            before_value["ignored_entries"] = [entry("scg-secret", ".env", "dangerous")]
            after_value = snapshot("/repo", [])
            after_value["scope"]["ignored"] = "inventoried"
            after_value["ignored_entries"] = [entry("scg-secret", ".env", "dangerous")]
            before = root / "before.json"
            after = root / "after.json"
            ledger = root / "ledger.json"
            write_json(before, before_value)
            write_json(after, after_value)
            write_json(ledger, [])

            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--ledger",
                    str(ledger),
                    "--format",
                    "json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("scg-secret", json.loads(result.stdout)["missing_path_ids"])


if __name__ == "__main__":
    unittest.main()
