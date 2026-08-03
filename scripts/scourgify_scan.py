#!/usr/bin/env python3
"""Read-only repository hygiene scanner for the Scourgify skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


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

INSTRUCTION_NAMES = {".cursorrules", "agents.md", "claude.md"}
DOC_STATE_WORDS = {"current", "handoff", "intent", "plan", "roadmap", "sync", "thread_context"}
DOC_STATE_NAMES = {"codex_thread_context.md", "handoff.md"}
DOC_EXACT_NAMES = {
    ".cursorrules",
    "agents.md",
    "claude.md",
    "contributing.md",
    "design.md",
    "product.md",
    "project.md",
    "skill.md",
}

SECRET_NAMES = {
    ".env",
    ".envrc",
    ".git-credentials",
    ".netrc",
    ".env.local",
    ".env.production",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "id_dsa",
    "id_ecdsa",
    "id_rsa",
    "id_ed25519",
    "kubeconfig",
    "service-account.json",
    "service_account.json",
}

SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks")
SECRET_DATA_SUFFIXES = {
    ".cfg",
    ".conf",
    ".csv",
    ".ini",
    ".json",
    ".properties",
    ".tfvars",
    ".toml",
    ".tsv",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
SECRET_WORDS = {
    "credential",
    "credentials",
    "password",
    "passwords",
    "secret",
    "secrets",
    "token",
    "tokens",
}
SECRET_DIRECTORY_NAMES = {".aws", ".azure", ".env", ".gcp", ".ssh", *SECRET_WORDS}

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
LOCKFILES = {
    "bun.lock",
    "bun.lockb",
    "cargo.lock",
    "composer.lock",
    "gemfile.lock",
    "npm-shrinkwrap.json",
    "package-lock.json",
    "pipfile.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "yarn.lock",
}
DESTRUCTIVE_SCRIPT_SUFFIXES = {".bat", ".cmd", ".ps1", ".py", ".sh"}
DESTRUCTIVE_SCRIPT_WORDS = {"delete", "destroy", "drop", "migrate", "purge", "reset", "truncate", "wipe"}
EVIDENCE_PARTS = {"screenshots", "screenshot", "snapshots", "reports", "artifacts", "playwright-report", "test-results"}
GIT_TIMEOUT_SECONDS = 10
GIT_PATHSPEC_CHUNK_SIZE = 128
MAX_MANIFEST_BYTES = 1_000_000


@dataclass(frozen=True)
class DirtyEntry:
    status: str
    path: str
    source_path: str | None = None
    object_type: str = "unknown"


@dataclass(frozen=True)
class GitScanState:
    head: str | None
    branch: str
    porcelain: str
    ignored_porcelain: str | None
    path_metadata: tuple[tuple[object, ...], ...]


class ScanError(RuntimeError):
    pass


def render_untrusted(value: str) -> str:
    """Return one reversible, single-line representation for repository text."""
    rendered = json.dumps(value, ensure_ascii=False)
    escaped = "".join(
        json.dumps(character, ensure_ascii=True)[1:-1]
        if unicodedata.category(character) in {"Cc", "Cf", "Cs", "Zl", "Zp"}
        else character
        for character in rendered
    )
    return escaped.encode("utf-8", errors="backslashreplace").decode("utf-8")


def run_git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    environment = os.environ.copy()
    for variable in ("GIT_GLOB_PATHSPECS", "GIT_ICASE_PATHSPECS", "GIT_NOGLOB_PATHSPECS"):
        environment.pop(variable, None)
    environment["GIT_LITERAL_PATHSPECS"] = "1"
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        proc = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", *args],
            cwd=str(cwd),
            env=environment,
            encoding="utf-8",
            errors="surrogateescape",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        if not cwd.is_dir():
            return 126, "", "Git working directory is unavailable"
        return 127, "", "git executable not found"
    except OSError as error:
        return 126, "", f"git command could not start: {error.__class__.__name__}"
    except subprocess.TimeoutExpired:
        return 124, "", f"git command timed out after {GIT_TIMEOUT_SECONDS} seconds"
    return proc.returncode, proc.stdout.rstrip("\n"), proc.stderr.rstrip("\n")


def find_repo_root(start: Path) -> Path | None:
    code, stdout, stderr = run_git(["rev-parse", "--show-toplevel"], start)
    if code in {124, 126, 127}:
        raise ScanError(stderr)
    if code != 0 or not stdout:
        return None
    return Path(stdout).resolve()


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def split_parts(path: str) -> set[str]:
    return set(PurePosixPath(path.lower()).parts)


def is_dangerous_name(name: str) -> bool:
    if name in SECRET_NAMES or name.startswith(".env.") or name.endswith(SECRET_SUFFIXES):
        return True
    suffix = Path(name).suffix
    words = set(filter(None, re.split(r"[^a-z0-9]+", Path(name).stem)))
    return suffix in SECRET_DATA_SUFFIXES and bool(words & SECRET_WORDS)


def is_destructive_script(name: str) -> bool:
    path = Path(name)
    words = set(filter(None, re.split(r"[^a-z0-9]+", path.stem)))
    return path.suffix in DESTRUCTIVE_SCRIPT_SUFFIXES and bool(words & DESTRUCTIVE_SCRIPT_WORDS)


def classify(path: str) -> tuple[str, str, str]:
    lower = path.lower()
    path_parts = PurePosixPath(lower).parts
    name = path_parts[-1] if path_parts else ""
    parts = split_parts(lower)

    if name in SECRET_DIRECTORY_NAMES or is_dangerous_name(name) or any(
        part in SECRET_DIRECTORY_NAMES or is_dangerous_name(part) for part in path_parts[:-1]
    ):
        return ("dangerous", "do not read contents; inspect path, status, and ignore policy only", "secret-like path")
    if name in LOCKFILES:
        return ("review-required", "inspect diff and package-manager intent before staging", "lockfile")
    if parts & {"migrate", "migration", "migrations"}:
        return ("review-required", "inspect irreversible/runtime impact before cleanup or staging", "migration path")
    if is_destructive_script(name):
        return ("review-required", "inspect destructive/runtime impact before cleanup or staging", "destructive script name")
    if parts & GENERATED_PARTS or name.endswith(GENERATED_SUFFIXES):
        return ("generated-safe", "remove or ignore only if repo policy allows", "generated/cache pattern")
    if parts & EVIDENCE_PARTS:
        return ("verification-evidence", "keep if it supports the handoff; otherwise remove or ignore by policy", "test or screenshot evidence")
    is_markdown = Path(name).suffix in {".md", ".mdc"}
    if (
        lower in {candidate.lower() for candidate in DOC_CANDIDATES}
        or (is_markdown and bool(parts & {"docs", "references"}))
        or (is_markdown and name.startswith("readme"))
        or name in DOC_EXACT_NAMES
        or name in INSTRUCTION_NAMES
        or ".cursor/rules/" in f"/{lower}"
    ):
        return ("doc-sync", "read for truth drift; update only if behavior or verification changed", "documentation path")
    return ("unknown", "inspect diff before deciding ownership", "no known pattern")


def parse_porcelain_z(output: str) -> list[DirtyEntry]:
    entries: list[DirtyEntry] = []
    fields = [field for field in output.split("\0") if field]
    i = 0
    while i < len(fields):
        item = fields[i]
        status = item[:2]
        path = item[3:] if len(item) > 3 else ""
        source_path = None
        if "R" in status or "C" in status:
            i += 1
            if i < len(fields):
                source_path = fields[i]
        entries.append(DirtyEntry(status=status, path=path, source_path=source_path))
        i += 1
    return entries


def detect_filesystem_object_type(root: Path, path: str) -> str:
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        return "invalid-path"
    candidate = root.joinpath(*relative.parts)
    try:
        metadata = candidate.lstat()
    except OSError:
        return "missing"
    if stat.S_ISLNK(metadata.st_mode):
        return "symlink"
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if getattr(metadata, "st_file_attributes", 0) & reparse_flag:
        return "reparse-point"
    if stat.S_ISREG(metadata.st_mode):
        return "file"
    if stat.S_ISDIR(metadata.st_mode):
        return "directory"
    return "other"


def parse_git_modes(output: str, requested_paths: set[str]) -> dict[str, set[str]]:
    modes: dict[str, set[str]] = {}
    for record in output.split("\0"):
        if not record or "\t" not in record:
            continue
        metadata, path = record.split("\t", 1)
        if path not in requested_paths:
            continue
        mode = metadata.split(" ", 1)[0]
        modes.setdefault(path, set()).add(mode)
    return modes


def git_modes(root: Path, paths: list[str], treeish: str | None = None) -> dict[str, set[str]]:
    unique_paths = list(dict.fromkeys(paths))
    modes: dict[str, set[str]] = {}
    for offset in range(0, len(unique_paths), GIT_PATHSPEC_CHUNK_SIZE):
        chunk = unique_paths[offset : offset + GIT_PATHSPEC_CHUNK_SIZE]
        if treeish is None:
            args = ["ls-files", "--stage", "-z", "--", *chunk]
        else:
            args = ["ls-tree", "-z", treeish, "--", *chunk]
        code, output, error = run_git(args, root)
        if code != 0:
            label = "Git index" if treeish is None else "HEAD tree"
            raise ScanError(f"{label} object inventory failed: {error or 'no diagnostic'}")
        for path, path_modes in parse_git_modes(output, set(chunk)).items():
            modes.setdefault(path, set()).update(path_modes)
    return modes


def enrich_entries(root: Path, entries: list[DirtyEntry], head: str | None) -> list[DirtyEntry]:
    paths = [
        path
        for entry in entries
        for path in (entry.path, entry.source_path)
        if path is not None
    ]
    index_modes = git_modes(root, paths)
    head_modes = git_modes(root, paths, treeish=head) if head is not None else {}

    def object_type(entry: DirtyEntry) -> str:
        historical_modes = set()
        for path in (entry.path, entry.source_path):
            if path is not None:
                historical_modes.update(index_modes.get(path, set()))
                historical_modes.update(head_modes.get(path, set()))
        if "160000" in historical_modes:
            return "gitlink"
        if "120000" in historical_modes:
            return "symlink"
        return detect_filesystem_object_type(root, entry.path)

    return [
        DirtyEntry(
            status=entry.status,
            path=entry.path,
            source_path=entry.source_path,
            object_type=object_type(entry),
        )
        for entry in entries
    ]


def is_safe_regular_file(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(metadata.st_mode)


def candidate_docs(root: Path, dirty_paths: list[str]) -> list[str]:
    seen: set[str] = set()
    docs: list[str] = []

    def add(path: Path) -> None:
        if not is_safe_regular_file(path):
            return
        try:
            item = rel(path, root)
        except ValueError:
            return
        if item.lower() not in seen:
            docs.append(item)
            seen.add(item.lower())

    for candidate in DOC_CANDIDATES:
        add(root / candidate)

    docs_root = root / "docs"
    if docs_root.is_dir() and not docs_root.is_symlink():
        for path in docs_root.rglob("*.md"):
            words = set(filter(None, re.split(r"[^a-z0-9]+", path.stem.lower())))
            if path.name.lower() in DOC_STATE_NAMES or words & DOC_STATE_WORDS:
                add(path)

    for dirty_path in dirty_paths:
        relative = PurePosixPath(dirty_path)
        if relative.is_absolute() or ".." in relative.parts:
            continue
        parent_parts = relative.parent.parts
        for depth in range(len(parent_parts) + 1):
            ancestor = root.joinpath(*parent_parts[:depth])
            for instruction in ("AGENTS.md", "CLAUDE.md", ".cursorrules"):
                add(ancestor / instruction)
            add(ancestor / ".github" / "copilot-instructions.md")
            cursor_rules = ancestor / ".cursor" / "rules"
            if cursor_rules.is_dir() and not cursor_rules.is_symlink():
                for rule in cursor_rules.rglob("*.mdc"):
                    add(rule)
    return sorted(docs, key=lambda value: (value.count("/"), value.lower()))


def package_json_checks(root: Path) -> list[str]:
    path = root / "package.json"
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return []
    except OSError as error:
        return [f"package.json skipped: {error.__class__.__name__}"]
    if stat.S_ISLNK(metadata.st_mode):
        return ["package.json skipped: symlink"]
    if not stat.S_ISREG(metadata.st_mode):
        return ["package.json skipped: not a regular file"]
    if metadata.st_size > MAX_MANIFEST_BYTES:
        return [f"package.json skipped: larger than {MAX_MANIFEST_BYTES} bytes"]
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return ["package.json present; inspect scripts manually"]
    if not isinstance(data, dict):
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
            checks.append(f"untrusted candidate: {package_manager} run {name}")
    return checks


def suggested_checks(root: Path) -> list[str]:
    checks = package_json_checks(root)
    if (root / "pyproject.toml").exists():
        checks.append("untrusted candidate: python -m pytest or the repo-documented Python check")
    elif (root / "pytest.ini").exists() or (root / "tox.ini").exists():
        checks.append("untrusted candidate: python -m pytest")
    if (root / "Cargo.toml").exists():
        checks.extend(["untrusted candidate: cargo test", "untrusted candidate: cargo clippy"])
    if (root / "go.mod").exists():
        checks.append("untrusted candidate: go test ./...")
    if (root / "Makefile").exists() or (root / "makefile").exists():
        checks.append("untrusted candidate: make test/check target if documented")
    return list(dict.fromkeys(checks))


def upstream_state(root: Path) -> dict:
    code, upstream, _ = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], root)
    if code != 0 or not upstream:
        return {"name": None, "ahead": None, "behind": None}
    result = {"name": upstream, "ahead": None, "behind": None}
    code, counts, _ = run_git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"], root)
    if code == 0 and counts:
        ahead, behind = counts.split()[:2]
        result["ahead"] = int(ahead)
        result["behind"] = int(behind)
    return result


def stable_path_id(path: str) -> str:
    digest = hashlib.sha256(path.encode("utf-8", errors="surrogateescape")).hexdigest()
    return f"scg-{digest}"


def classify_entry(entry: DirtyEntry) -> tuple[str, str, str]:
    boundary = None
    if entry.object_type in {"gitlink", "invalid-path", "other", "reparse-point", "symlink"}:
        boundary = (
            "review-required",
            "treat as an object boundary; do not follow or inspect nested contents",
            f"{entry.object_type} boundary",
        )
    current = classify(entry.path)
    source = None
    if entry.source_path is not None:
        source_category, source_action, source_reason = classify(entry.source_path)
        source = (source_category, source_action, f"source path: {source_reason}")
    for candidate in (current, source):
        if candidate is not None and candidate[0] == "dangerous":
            return candidate
    if boundary is not None:
        return boundary
    for candidate in (current, source):
        if candidate is not None and candidate[0] == "review-required":
            return candidate
    return current


def entry_record(entry: DirtyEntry) -> dict:
    category, action, reason = classify_entry(entry)
    return {
        "path_id": stable_path_id(entry.path),
        "status": entry.status,
        "path": entry.path,
        "display_path": render_untrusted(entry.path),
        "source_path": entry.source_path,
        "display_source_path": render_untrusted(entry.source_path) if entry.source_path is not None else None,
        "object_type": entry.object_type,
        "category": category,
        "reason": reason,
        "next_action": action,
    }


def path_metadata_fingerprint(root: Path, porcelain_outputs: list[str]) -> tuple[tuple[object, ...], ...]:
    paths = {
        entry.path
        for output in porcelain_outputs
        for entry in parse_porcelain_z(output)
    }
    fingerprint: list[tuple[object, ...]] = []
    for path in sorted(paths):
        relative = PurePosixPath(path)
        if relative.is_absolute() or ".." in relative.parts:
            fingerprint.append((path, "invalid-path"))
            continue
        candidate = root.joinpath(*relative.parts)
        try:
            metadata = candidate.lstat()
        except OSError as error:
            fingerprint.append((path, "unavailable", error.__class__.__name__))
            continue
        fingerprint.append(
            (
                path,
                "present",
                metadata.st_mode,
                metadata.st_size,
                metadata.st_mtime_ns,
                metadata.st_ctime_ns,
                getattr(metadata, "st_dev", 0),
                getattr(metadata, "st_ino", 0),
            )
        )
    return tuple(fingerprint)


def capture_git_state(root: Path, include_ignored: bool) -> GitScanState:
    head_code, head, head_error = run_git(["rev-parse", "--verify", "HEAD"], root)
    if head_code in {124, 126, 127}:
        raise ScanError(f"Git HEAD inventory failed: {head_error or 'no diagnostic'}")
    if head_code != 0:
        head = None
    branch_code, branch, branch_error = run_git(["status", "--short", "--branch"], root)
    status_code, porcelain, status_error = run_git(
        ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--find-renames=50%"], root
    )
    if branch_code != 0 or status_code != 0:
        detail = status_error or branch_error or "git status returned no diagnostic"
        raise ScanError(f"git status failed: {detail}")
    ignored_porcelain: str | None = None
    if include_ignored:
        ignored_code, ignored_porcelain, ignored_error = run_git(
            [
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
                "--ignored=matching",
                "--find-renames=50%",
            ],
            root,
        )
        if ignored_code != 0:
            raise ScanError(f"git ignored-path inventory failed: {ignored_error or 'no diagnostic'}")
    metadata_outputs = [porcelain]
    if ignored_porcelain is not None:
        metadata_outputs.append(ignored_porcelain)
    return GitScanState(
        head=head,
        branch=branch,
        porcelain=porcelain,
        ignored_porcelain=ignored_porcelain,
        path_metadata=path_metadata_fingerprint(root, metadata_outputs),
    )


def collect_snapshot(root: Path, include_ignored: bool = False) -> dict:
    initial_state = capture_git_state(root, include_ignored)
    entries = enrich_entries(root, parse_porcelain_z(initial_state.porcelain), initial_state.head)
    ignored_entries: list[DirtyEntry] = []
    if initial_state.ignored_porcelain is not None:
        ignored_entries = enrich_entries(
            root,
            [
                entry
                for entry in parse_porcelain_z(initial_state.ignored_porcelain)
                if entry.status == "!!"
            ],
            initial_state.head,
        )
    docs = candidate_docs(root, [entry.path for entry in entries])
    checks = suggested_checks(root)
    upstream = upstream_state(root)
    if capture_git_state(root, include_ignored) != initial_state:
        raise ScanError("repository state changed during scan; retry from a stable worktree")

    return {
        "schema_version": 1,
        "repository": {
            "root": str(root),
            "head": initial_state.head,
            "status_line": initial_state.branch.splitlines()[0] if initial_state.branch else "(unknown)",
            "upstream": upstream,
        },
        "scope": {
            "untracked": "all",
            "ignored": "inventoried" if include_ignored else "not-inventoried",
            "nested_gitlinks": "not-inspected",
        },
        "candidate_docs": docs,
        "suggested_checks": checks,
        "entries": [entry_record(entry) for entry in entries],
        "ignored_entries": [entry_record(entry) for entry in ignored_entries],
    }


def print_human_scan(snapshot: dict) -> None:
    repository = snapshot["repository"]
    entries = snapshot["entries"]
    docs = snapshot["candidate_docs"]
    checks = snapshot["suggested_checks"]

    print("# Scourgify Scan")
    print()
    print(f"repo: {render_untrusted(repository['root'])}")
    print()
    print("## Branch")
    print(f"- status: {render_untrusted(repository['status_line'])}")
    upstream = repository["upstream"]
    if upstream["name"] is None:
        print('- "upstream: none configured"')
    else:
        print(f"- upstream: {render_untrusted(upstream['name'])}")
        if upstream["ahead"] is not None:
            print(f"- ahead/behind: {upstream['ahead']}/{upstream['behind']}")
    print()

    print("## Candidate Docs")
    if docs:
        for candidate in docs:
            print(f"- {render_untrusted(candidate)}")
    else:
        print("- none found")
    print()

    print("## Dirty Files")
    if not entries:
        print("- no non-ignored Git changes")
    else:
        for entry in entries:
            print(f"- `{entry['status']}` {entry['display_path']} [{entry['category']}]")
            if entry["source_path"] is not None:
                print(f"  from: {entry['display_source_path']}")
            print(f"  id: {entry['path_id']}")
            print(f"  object: {entry['object_type']}")
            print(f"  reason: {entry['reason']}")
            print(f"  next: {entry['next_action']}")
    if snapshot["scope"]["ignored"] == "not-inventoried":
        print("- ignored paths: not inventoried")
    print()

    if snapshot["scope"]["ignored"] == "inventoried":
        print("## Ignored Paths (opt-in)")
        if snapshot["ignored_entries"]:
            for entry in snapshot["ignored_entries"]:
                print(f"- {entry['display_path']} [{entry['category']}]")
                print(f"  object: {entry['object_type']}")
        else:
            print("- none reported by Git")
        print()

    print("## Suggested Checks")
    if checks:
        for check in checks:
            print(f"- {check}")
    else:
        print("- no common check command detected; use repo instructions")
    print()

    print("## Closeout Prompt")
    print("- For each dirty file: owner, reason, next action, evidence, and permission state.")
    print("- For docs: latest verified behavior, commands run, skipped checks, and known risks.")


def require_self_test(condition: bool, label: str) -> None:
    if not condition:
        raise ScanError(f"self-test failed: {label}")


def self_test() -> None:
    require_self_test(classify(".env")[0] == "dangerous", "secret classification")
    require_self_test(
        all(
            classify(path)[0] == "dangerous"
            for path in ("secrets/config.yaml", ".env/private.json", "passwords.csv", "token.txt")
        ),
        "nested and data-file secret classification",
    )
    require_self_test(
        classify_entry(DirtyEntry("R ", "safe.txt", ".env", "file"))[0] == "dangerous",
        "renamed secret-source classification",
    )
    require_self_test(
        classify("src/db/migrations/001_init.sql")[0] == "review-required",
        "migration classification",
    )
    require_self_test(classify("pnpm-lock.yaml")[0] == "review-required", "lockfile classification")
    require_self_test(classify("docs/CURRENT_STATE.md")[0] == "doc-sync", "documentation classification")
    require_self_test(
        classify("tmp/screenshots/home.png")[0] == "verification-evidence",
        "evidence classification",
    )
    require_self_test(
        classify("src/__pycache__/x.pyc")[0] == "generated-safe",
        "generated-file classification",
    )
    require_self_test(
        parse_porcelain_z(" M README.md\0R  new name.txt\0old name.txt\0")
        == [
            DirtyEntry(" M", "README.md"),
            DirtyEntry("R ", "new name.txt", "old name.txt"),
        ],
        "porcelain rename parsing",
    )
    rendered_untrusted = render_untrusted("safe\u202e.env\u2028line\u009b")
    require_self_test(
        all(control not in rendered_untrusted for control in ("\u202e", "\u2028", "\u009b")),
        "Unicode control escaping",
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "package.json").write_text('{"scripts":{"test":"vitest","build":"vite build"}}', encoding="utf-8")
        (root / "pnpm-lock.yaml").write_text("", encoding="utf-8")
        require_self_test(
            package_json_checks(root)
            == [
                "untrusted candidate: pnpm run test",
                "untrusted candidate: pnpm run build",
            ],
            "package command candidates",
        )
        for non_object_manifest in ("[]", "null"):
            (root / "package.json").write_text(non_object_manifest, encoding="utf-8")
            require_self_test(
                package_json_checks(root) == ["package.json present; inspect scripts manually"],
                "non-object package manifest handling",
            )
    print("self-test: ok")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Scourgify repository scanner.")
    parser.add_argument("--cwd", default=os.getcwd(), help="Directory inside the repository to inspect.")
    parser.add_argument("--format", choices=("human", "json"), default="human", help="Output format.")
    parser.add_argument(
        "--include-ignored",
        action="store_true",
        help="Opt in to a metadata-only inventory of ignored paths.",
    )
    parser.add_argument("--self-test", action="store_true", help="Run scanner self-tests.")
    args = parser.parse_args()

    if args.self_test:
        try:
            self_test()
        except ScanError as error:
            print(render_untrusted(str(error)), file=sys.stderr)
            return 3
        return 0

    requested_start = Path(args.cwd)
    try:
        start = requested_start.resolve(strict=True)
    except FileNotFoundError:
        print(
            f"Scourgify scan failed: {render_untrusted(str(requested_start))} does not exist",
            file=sys.stderr,
        )
        return 2
    except OSError as error:
        print(
            f"Scourgify scan failed: cannot resolve {render_untrusted(str(requested_start))}: "
            f"{error.__class__.__name__}",
            file=sys.stderr,
        )
        return 2
    if not start.is_dir():
        print(
            f"Scourgify scan failed: {render_untrusted(str(start))} is not a directory",
            file=sys.stderr,
        )
        return 2
    try:
        root = find_repo_root(start)
    except ScanError as error:
        print(f"Scourgify scan failed: {render_untrusted(str(error))}", file=sys.stderr)
        return 3
    if root is None:
        print(f"No git repository found from {render_untrusted(str(start))}")
        return 2

    try:
        snapshot = collect_snapshot(root, include_ignored=args.include_ignored)
    except ScanError as error:
        print(f"Scourgify scan failed: {render_untrusted(str(error))}", file=sys.stderr)
        return 3
    if args.format == "json":
        print(json.dumps(snapshot, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print_human_scan(snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
