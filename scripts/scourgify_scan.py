#!/usr/bin/env python3
"""Read-only repository hygiene scanner for the Scourgify skill."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


DOC_CANDIDATES = [
    "AGENTS.md",
    "CLAUDE.md",
    ".cursorrules",
    ".github/copilot-instructions.md",
    "README.md",
    "CONTRIBUTING.md",
    "PROJECT.md",
    "PRODUCT.md",
    "design.md",
    "docs/project-memory.md",
]

DOC_GLOBS = [
    "docs/**/*CURRENT*.md",
    "docs/**/*SYNC*.md",
    "docs/**/*INTENT*.md",
    "docs/**/*PLAN*.md",
    "docs/**/*ROADMAP*.md",
]

SECRET_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".npmrc",
    ".pypirc",
    "id_rsa",
    "id_ed25519",
}

SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
SECRET_TOKENS = ("/.env", "secret", "credential", "token", "password")

GENERATED_PARTS = {
    ".cache",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".turbo",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
}

GENERATED_SUFFIXES = (".pyc", ".pyo", ".tsbuildinfo", ".log", ".tmp")
LOCKFILES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "poetry.lock", "uv.lock", "cargo.lock"}
EVIDENCE_PARTS = {"screenshots", "screenshot", "snapshots", "reports", "artifacts", "playwright-report", "test-results"}


def run_git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.returncode, proc.stdout.rstrip("\n"), proc.stderr.rstrip("\n")


def find_repo_root(start: Path) -> Path | None:
    code, stdout, _ = run_git(["rev-parse", "--show-toplevel"], start)
    if code != 0 or not stdout:
        return None
    return Path(stdout).resolve()


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def split_parts(path: str) -> set[str]:
    return set(Path(path.lower().replace("\\", "/")).parts)


def classify(path: str) -> tuple[str, str, str]:
    lower = path.lower().replace("\\", "/")
    name = Path(lower).name
    parts = split_parts(lower)

    if name in SECRET_NAMES or name.endswith(SECRET_SUFFIXES) or any(token in lower for token in SECRET_TOKENS):
        return ("dangerous", "do not read contents; inspect path, status, and ignore policy only", "secret-like path")
    if name in LOCKFILES:
        return ("review-required", "inspect diff and package-manager intent before staging", "lockfile")
    if "migration" in parts or "migrations" in parts:
        return ("review-required", "inspect irreversible/runtime impact before cleanup or staging", "migration path")
    if parts & GENERATED_PARTS or name.endswith(GENERATED_SUFFIXES):
        return ("generated-safe", "remove or ignore only if repo policy allows", "generated/cache pattern")
    if parts & EVIDENCE_PARTS:
        return ("verification-evidence", "keep if it supports the handoff; otherwise remove or ignore by policy", "test or screenshot evidence")
    if lower in {candidate.lower() for candidate in DOC_CANDIDATES} or lower.startswith("docs/"):
        return ("doc-sync", "read for truth drift; update only if behavior or verification changed", "documentation path")
    return ("unknown", "inspect diff before deciding ownership", "no known pattern")


def parse_porcelain_z(output: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    fields = [field for field in output.split("\0") if field]
    i = 0
    while i < len(fields):
        item = fields[i]
        status = item[:2]
        path = item[3:] if len(item) > 3 else ""
        if status.startswith("R") or status.startswith("C"):
            i += 1
            if i < len(fields):
                path = fields[i]
        entries.append((status, path))
        i += 1
    return entries


def candidate_docs(root: Path) -> list[str]:
    seen: set[str] = set()
    docs: list[str] = []
    for candidate in DOC_CANDIDATES:
        if (root / candidate).exists():
            docs.append(candidate)
            seen.add(candidate.lower())
    for pattern in DOC_GLOBS:
        for path in root.glob(pattern):
            if path.is_file():
                item = rel(path, root)
                if item.lower() not in seen:
                    docs.append(item)
                    seen.add(item.lower())
    return sorted(docs, key=lambda value: (value.count("/"), value.lower()))


def package_json_checks(root: Path) -> list[str]:
    path = root / "package.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return ["package.json present; inspect scripts manually"]
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return []

    checks: list[str] = []
    package_manager = "npm"
    if (root / "pnpm-lock.yaml").exists():
        package_manager = "pnpm"
    elif (root / "yarn.lock").exists():
        package_manager = "yarn"
    elif (root / "bun.lockb").exists():
        package_manager = "bun"

    for name in ("test", "lint", "typecheck", "build", "check"):
        if name in scripts:
            checks.append(f"{package_manager} run {name}")
    return checks


def suggested_checks(root: Path) -> list[str]:
    checks = package_json_checks(root)
    if (root / "pyproject.toml").exists():
        checks.append("python -m pytest or the repo-documented Python check")
    elif (root / "pytest.ini").exists() or (root / "tox.ini").exists():
        checks.append("python -m pytest")
    if (root / "Cargo.toml").exists():
        checks.extend(["cargo test", "cargo clippy"])
    if (root / "go.mod").exists():
        checks.append("go test ./...")
    if (root / "Makefile").exists() or (root / "makefile").exists():
        checks.append("make test/check target if documented")
    return list(dict.fromkeys(checks))


def upstream_summary(root: Path) -> list[str]:
    lines: list[str] = []
    code, upstream, _ = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], root)
    if code != 0 or not upstream:
        return ["upstream: none configured"]
    lines.append(f"upstream: {upstream}")
    code, counts, _ = run_git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"], root)
    if code == 0 and counts:
        ahead, behind = counts.split()[:2]
        lines.append(f"ahead/behind: {ahead}/{behind}")
    return lines


def print_scan(root: Path) -> None:
    _, branch, _ = run_git(["status", "--short", "--branch"], root)
    _, porcelain, _ = run_git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], root)
    docs = candidate_docs(root)
    checks = suggested_checks(root)

    print("# Scourgify Scan")
    print()
    print(f"repo: {root}")
    print()
    print("## Branch")
    print(f"- status: {branch.splitlines()[0] if branch else '(unknown)'}")
    for line in upstream_summary(root):
        print(f"- {line}")
    print()

    print("## Candidate Docs")
    if docs:
        for candidate in docs:
            print(f"- {candidate}")
    else:
        print("- none found")
    print()

    print("## Dirty Files")
    entries = parse_porcelain_z(porcelain)
    if not entries:
        print("- clean")
    else:
        for status, path in entries:
            category, action, reason = classify(path)
            print(f"- `{status}` {path} [{category}]")
            print(f"  reason: {reason}")
            print(f"  next: {action}")
    print()

    print("## Suggested Checks")
    if checks:
        for check in checks:
            print(f"- {check}")
    else:
        print("- no common check command detected; use repo instructions")
    print()

    print("## Closeout Prompt")
    print("- For each dirty file: owner, action, evidence, and whether user permission is required.")
    print("- For docs: latest verified behavior, commands run, skipped checks, and known risks.")


def self_test() -> None:
    assert classify(".env")[0] == "dangerous"
    assert classify("src/db/migrations/001_init.sql")[0] == "review-required"
    assert classify("pnpm-lock.yaml")[0] == "review-required"
    assert classify("docs/CURRENT_STATE.md")[0] == "doc-sync"
    assert classify("tmp/screenshots/home.png")[0] == "verification-evidence"
    assert classify("src/__pycache__/x.pyc")[0] == "generated-safe"
    assert parse_porcelain_z(" M README.md\0R  old name.txt\0new name.txt\0") == [
        (" M", "README.md"),
        ("R ", "new name.txt"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "package.json").write_text('{"scripts":{"test":"vitest","build":"vite build"}}', encoding="utf-8")
        (root / "pnpm-lock.yaml").write_text("", encoding="utf-8")
        assert package_json_checks(root) == ["pnpm run test", "pnpm run build"]
    print("self-test: ok")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Scourgify repository scanner.")
    parser.add_argument("--cwd", default=os.getcwd(), help="Directory inside the repository to inspect.")
    parser.add_argument("--self-test", action="store_true", help="Run scanner self-tests.")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    start = Path(args.cwd).resolve()
    root = find_repo_root(start)
    if root is None:
        print(f"No git repository found from {start}")
        return 2

    print_scan(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
