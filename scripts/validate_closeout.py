#!/usr/bin/env python3
"""Validate Scourgify before/after snapshots against a closeout ledger."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys


LEDGER_TEXT_FIELDS = {"path_id", "path", "owner", "reason", "next_action", "evidence"}
PERMISSION_STATES = {"denied", "granted", "not-required", "required"}


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot_entries(value: object, label: str, errors: list[str]) -> tuple[str | None, list[dict]]:
    if not isinstance(value, dict):
        errors.append(f"{label}: top level must be an object")
        return None, []
    if value.get("schema_version") != 1:
        errors.append(f"{label}: unsupported schema_version")
    repository = value.get("repository")
    root = repository.get("root") if isinstance(repository, dict) else None
    if not isinstance(root, str) or not root:
        errors.append(f"{label}: repository.root must be non-empty text")
        root = None
    entries = value.get("entries")
    if not isinstance(entries, list):
        errors.append(f"{label}: entries must be a list")
        return root, []
    entry_groups = [("entries", entries)]
    scope = value.get("scope")
    ignored_scope = scope.get("ignored") if isinstance(scope, dict) else None
    if ignored_scope == "inventoried":
        ignored_entries = value.get("ignored_entries")
        if not isinstance(ignored_entries, list):
            errors.append(f"{label}: ignored_entries must be a list when ignored paths are inventoried")
            ignored_entries = []
        entry_groups.append(("ignored_entries", ignored_entries))
    valid_entries: list[dict] = []
    for group_name, group in entry_groups:
        for number, entry in enumerate(group, start=1):
            prefix = f"{label}: {group_name} entry {number}"
            if not isinstance(entry, dict):
                errors.append(f"{prefix} must be an object")
                continue
            path_id = entry.get("path_id")
            path = entry.get("path")
            if not isinstance(path_id, str) or not path_id:
                errors.append(f"{prefix} path_id must be non-empty text")
                continue
            if not isinstance(path, str) or not path:
                errors.append(f"{prefix} path must be non-empty text")
                continue
            valid_entries.append(entry)
    return root, valid_entries


def validate(before: object, after: object, ledger: object) -> dict:
    errors: list[str] = []
    before_root, before_entries = snapshot_entries(before, "before", errors)
    after_root, after_entries = snapshot_entries(after, "after", errors)
    if before_root and after_root and before_root != after_root:
        errors.append("before and after repository roots differ")

    if not isinstance(ledger, list):
        errors.append("ledger: top level must be a list")
        ledger_rows: list[dict] = []
    else:
        ledger_rows = [row for row in ledger if isinstance(row, dict)]
        if len(ledger_rows) != len(ledger):
            errors.append("ledger: every row must be an object")
    for number, row in enumerate(ledger_rows, start=1):
        for field in sorted(LEDGER_TEXT_FIELDS):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"ledger: row {number} {field} must be non-empty text")
        if row.get("permission") not in PERMISSION_STATES:
            errors.append(
                f"ledger: row {number} permission must be one of {sorted(PERMISSION_STATES)}"
            )

    before_ids = [entry["path_id"] for entry in before_entries]
    after_ids = [entry["path_id"] for entry in after_entries]
    for label, path_ids in (("before", before_ids), ("after", after_ids)):
        duplicates_in_snapshot = sorted(
            path_id for path_id, count in Counter(path_ids).items() if count > 1
        )
        if duplicates_in_snapshot:
            errors.append(f"{label}: duplicate path IDs: {duplicates_in_snapshot}")
    expected_ids = set(before_ids) | set(after_ids)
    expected_paths: dict[str, str] = {}
    for entry in [*before_entries, *after_entries]:
        existing = expected_paths.get(entry["path_id"])
        if existing is not None and existing != entry["path"]:
            errors.append(
                f"snapshot path ID {entry['path_id']} maps to both {existing!r} and {entry['path']!r}"
            )
        expected_paths[entry["path_id"]] = entry["path"]
    ledger_ids = [row.get("path_id") for row in ledger_rows if isinstance(row.get("path_id"), str)]
    ledger_id_set = set(ledger_ids)
    missing = sorted(expected_ids - ledger_id_set)
    unexpected = sorted(ledger_id_set - expected_ids)
    duplicates = sorted(path_id for path_id, count in Counter(ledger_ids).items() if count > 1)
    if missing:
        errors.append(f"ledger missing path IDs: {missing}")
    if unexpected:
        errors.append(f"ledger has unexpected path IDs: {unexpected}")
    if duplicates:
        errors.append(f"ledger has duplicate path IDs: {duplicates}")
    for number, row in enumerate(ledger_rows, start=1):
        path_id = row.get("path_id")
        if path_id in expected_paths and row.get("path") != expected_paths[path_id]:
            errors.append(
                f"ledger: row {number} path does not match snapshot identity for {path_id}"
            )
    outstanding_permissions = sorted(
        row["path_id"]
        for row in ledger_rows
        if isinstance(row.get("path_id"), str) and row.get("permission") in {"denied", "required"}
    )
    complete = not errors

    return {
        "schema_version": 1,
        "complete": complete,
        "work_ready": complete and not outstanding_permissions,
        "counts": {
            "before": len(before_entries),
            "after": len(after_entries),
            "expected": len(expected_ids),
            "ledger": len(ledger_rows),
        },
        "missing_path_ids": missing,
        "unexpected_path_ids": unexpected,
        "duplicate_path_ids": duplicates,
        "outstanding_permission_path_ids": outstanding_permissions,
        "errors": errors,
    }


def print_human(report: dict) -> None:
    print("# Scourgify Closeout Validation")
    print()
    print(f"- complete: {'yes' if report['complete'] else 'no'}")
    print(f"- work ready: {'yes' if report['work_ready'] else 'no'}")
    for name, count in report["counts"].items():
        print(f"- {name}: {count}")
    if report["errors"]:
        print()
        print("## Blockers")
        for error in report["errors"]:
            print(f"- {json.dumps(error, ensure_ascii=False)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--format", choices=("human", "json"), default="human")
    args = parser.parse_args()

    try:
        report = validate(read_json(args.before), read_json(args.after), read_json(args.ledger))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        report = {
            "schema_version": 1,
            "complete": False,
            "work_ready": False,
            "counts": {"before": 0, "after": 0, "expected": 0, "ledger": 0},
            "missing_path_ids": [],
            "unexpected_path_ids": [],
            "duplicate_path_ids": [],
            "outstanding_permission_path_ids": [],
            "errors": [f"input error: {error}"],
        }
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
