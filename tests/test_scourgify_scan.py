from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.scourgify_scan import ScanError, collect_snapshot, render_untrusted


REPO_ROOT = Path(__file__).resolve().parents[1]
SCANNER = REPO_ROOT / "scripts" / "scourgify_scan.py"


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def init_repo(root: Path) -> None:
    run(["git", "init", "-q"], root)
    run(["git", "config", "user.name", "Scourgify Test"], root)
    run(["git", "config", "user.email", "scourgify@example.invalid"], root)


class ScannerIntegrationTests(unittest.TestCase):
    def test_scanner_self_test_remains_active_under_python_optimization(self) -> None:
        syntax = ast.parse(SCANNER.read_text(encoding="utf-8"))
        self.assertFalse(
            [node for node in ast.walk(syntax) if isinstance(node, ast.Assert)],
            "scanner runtime self-tests must not use optimization-sensitive assert statements",
        )

        result = run([sys.executable, "-O", str(SCANNER), "--self-test"], REPO_ROOT)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("self-test: ok", result.stdout)

    def test_untrusted_renderer_escapes_structure_and_terminal_controls(self) -> None:
        hostile = "evil\n## Forged Section\n- clean\x1b[31m`name`.txt"

        rendered = render_untrusted(hostile)

        self.assertNotIn("\n", rendered)
        self.assertNotIn("\x1b", rendered)
        self.assertIn(r"\n## Forged Section\n- clean\u001b[31m`name`.txt", rendered)

    def test_untrusted_renderer_escapes_unicode_controls_and_line_separators(self) -> None:
        hostile = "safe\u202e.env\u2028## Forged\u009b31m.txt"

        rendered = render_untrusted(hostile)

        for control in ("\u202e", "\u2028", "\u009b"):
            self.assertNotIn(control, rendered)
        self.assertIn(r"\u202e", rendered)
        self.assertIn(r"\u2028", rendered)
        self.assertIn(r"\u009b", rendered)
        self.assertEqual(len(rendered.splitlines()), 1)

    def test_all_detected_commands_are_labeled_untrusted_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            for manifest in ("pyproject.toml", "Cargo.toml", "go.mod", "Makefile"):
                (root / manifest).write_text("fixture\n", encoding="utf-8")

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            for command in ("python -m pytest", "cargo test", "cargo clippy", "go test ./...", "make test/check"):
                self.assertIn(f"untrusted candidate: {command}", result.stdout)

    def test_oversized_package_manifest_is_not_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / "package.json").write_bytes(b" " * 1_000_001)

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("package.json skipped: larger than 1000000 bytes", result.stdout)

    def test_non_object_package_manifest_is_reported_without_crashing(self) -> None:
        for manifest in ("[]\n", "null\n"):
            with self.subTest(manifest=manifest.strip()), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                init_repo(root)
                (root / "package.json").write_text(manifest, encoding="utf-8")

                result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("package.json present; inspect scripts manually", result.stdout)

    def test_rename_to_secret_reports_current_and_original_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / "safe.txt").write_text("safe\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", "safe.txt"], root).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "base"], root).returncode, 0)
            self.assertEqual(run(["git", "mv", "safe.txt", ".env.staging"], root).returncode, 0)

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('".env.staging" [dangerous]', result.stdout)
            self.assertIn('from: "safe.txt"', result.stdout)

    def test_rename_from_secret_stays_dangerous_with_renames_disabled_in_repo_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / ".env").write_text("secret\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", ".env"], root).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "base"], root).returncode, 0)
            self.assertEqual(run(["git", "mv", ".env", "safe.txt"], root).returncode, 0)
            self.assertEqual(run(["git", "config", "status.renames", "false"], root).returncode, 0)

            result = run(
                [sys.executable, str(SCANNER), "--cwd", str(root), "--format", "json"],
                root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            entries = json.loads(result.stdout)["entries"]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["status"], "R ")
            self.assertEqual(entries[0]["path"], "safe.txt")
            self.assertEqual(entries[0]["source_path"], ".env")
            self.assertEqual(entries[0]["category"], "dangerous")

    def test_rename_from_review_required_path_stays_review_required(self) -> None:
        for source_path in ("migrations/001.sql", "pnpm-lock.yaml"):
            with self.subTest(source_path=source_path), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                init_repo(root)
                source = root / source_path
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("base\n", encoding="utf-8")
                self.assertEqual(run(["git", "add", source_path], root).returncode, 0)
                self.assertEqual(run(["git", "commit", "-qm", "base"], root).returncode, 0)
                self.assertEqual(run(["git", "mv", source_path, "safe.txt"], root).returncode, 0)

                result = run(
                    [sys.executable, str(SCANNER), "--cwd", str(root), "--format", "json"],
                    root,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                entry = json.loads(result.stdout)["entries"][0]
                self.assertEqual(entry["source_path"], source_path)
                self.assertEqual(entry["category"], "review-required")

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows")
    def test_renamed_secret_symlink_keeps_dangerous_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            root = fixture / "repo"
            root.mkdir()
            init_repo(root)
            outside = fixture / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            (root / ".env").symlink_to(outside)
            self.assertEqual(run(["git", "add", ".env"], root).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "base"], root).returncode, 0)
            self.assertEqual(run(["git", "mv", ".env", "safe.txt"], root).returncode, 0)

            result = run(
                [sys.executable, str(SCANNER), "--cwd", str(root), "--format", "json"],
                root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            entry = json.loads(result.stdout)["entries"][0]
            self.assertEqual(entry["object_type"], "symlink")
            self.assertEqual(entry["source_path"], ".env")
            self.assertEqual(entry["category"], "dangerous")

    def test_git_status_failure_is_not_reported_as_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / "tracked.txt").write_text("base\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", "tracked.txt"], root).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "base"], root).returncode, 0)
            (root / ".git" / "index").write_bytes(b"not-a-git-index")

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("- clean", result.stdout)
            self.assertIn("scan failed", result.stderr.lower())

    @unittest.skipIf(os.name == "nt", "Windows forbids newline and ESC in filenames")
    def test_untrusted_path_cannot_inject_report_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            hostile = "evil\n## Forged Section\n- clean\x1b[31m`name`.txt"
            (root / hostile).write_text("untrusted\n", encoding="utf-8")

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("\n## Forged Section", result.stdout)
            self.assertNotIn("\x1b", result.stdout)
            self.assertIn(r"\n## Forged Section\n- clean\u001b[31m`name`.txt", result.stdout)

    def test_scan_does_not_refresh_git_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            tracked = root / "tracked.txt"
            tracked.write_text("base\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", "tracked.txt"], root).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "base"], root).returncode, 0)
            index = root / ".git" / "index"
            before = index.read_bytes()
            metadata = tracked.stat()
            os.utime(
                tracked,
                ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 2_000_000_000),
            )

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(index.read_bytes(), before)

    def test_snapshot_fails_if_the_worktree_changes_during_collection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / "tracked.txt").write_text("base\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", "tracked.txt"], root).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "base"], root).returncode, 0)

            def mutate_during_scan(_root: Path, _dirty_paths: list[str]) -> list[str]:
                (root / "late.txt").write_text("late\n", encoding="utf-8")
                return []

            with mock.patch(
                "scripts.scourgify_scan.candidate_docs",
                side_effect=mutate_during_scan,
            ):
                with self.assertRaisesRegex(ScanError, "changed during scan"):
                    collect_snapshot(root)

    def test_snapshot_fails_if_dirty_file_content_changes_without_status_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            tracked = root / "tracked.txt"
            tracked.write_text("base\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", "tracked.txt"], root).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "base"], root).returncode, 0)
            tracked.write_text("dirty-one\n", encoding="utf-8")
            metadata = tracked.stat()
            os.utime(
                tracked,
                ns=(metadata.st_atime_ns, metadata.st_mtime_ns - 2_000_000_000),
            )

            def mutate_during_scan(_root: Path, _dirty_paths: list[str]) -> list[str]:
                tracked.write_text("dirty-two\n", encoding="utf-8")
                return []

            with mock.patch(
                "scripts.scourgify_scan.candidate_docs",
                side_effect=mutate_during_scan,
            ):
                with self.assertRaisesRegex(ScanError, "changed during scan"):
                    collect_snapshot(root)

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows")
    def test_snapshot_fails_if_untracked_file_becomes_a_symlink_mid_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            root = fixture / "repo"
            root.mkdir()
            init_repo(root)
            item = root / "item.txt"
            item.write_text("regular\n", encoding="utf-8")
            outside = fixture / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")

            def mutate_during_scan(_root: Path, _dirty_paths: list[str]) -> list[str]:
                item.unlink()
                item.symlink_to(outside)
                return []

            with mock.patch(
                "scripts.scourgify_scan.candidate_docs",
                side_effect=mutate_during_scan,
            ):
                with self.assertRaisesRegex(ScanError, "changed during scan"):
                    collect_snapshot(root)

    @unittest.skipIf(os.name == "nt", "POSIX fsmonitor control fixture")
    def test_scan_does_not_execute_repository_fsmonitor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            marker = root / "fsmonitor-executed"
            hook = root / "fsmonitor-hook"
            hook.write_text(
                "#!/bin/sh\nprintf invoked > \"$SCG_FSMONITOR_MARKER\"\nprintf '0\\n'\n",
                encoding="utf-8",
            )
            hook.chmod(0o755)
            self.assertEqual(run(["git", "config", "core.fsmonitor", str(hook)], root).returncode, 0)
            environment = os.environ.copy()
            environment["SCG_FSMONITOR_MARKER"] = str(marker)
            control = subprocess.run(
                ["git", "status", "--short"],
                cwd=root,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(control.returncode, 0, control.stderr)
            self.assertTrue(marker.exists(), "control git status did not exercise fsmonitor fixture")
            marker.unlink()

            result = subprocess.run(
                [sys.executable, str(SCANNER), "--cwd", str(root)],
                cwd=root,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(marker.exists())

    def test_symlinked_package_manifest_is_not_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            root = fixture / "repo"
            root.mkdir()
            init_repo(root)
            outside = fixture / "outside-package.json"
            outside.write_text('{"scripts":{"test":"touch escaped"}}', encoding="utf-8")
            (root / "package.json").symlink_to(outside)

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("npm run test", result.stdout)
            self.assertIn("package.json skipped: symlink", result.stdout)

    def test_secret_classification_uses_path_semantics_not_substrings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / ".env.staging").write_text("", encoding="utf-8")
            (root / ".netrc").write_text("", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "tokenizer.py").write_text("", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "password-policy.md").write_text("", encoding="utf-8")

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('".env.staging" [dangerous]', result.stdout)
            self.assertIn('".netrc" [dangerous]', result.stdout)
            self.assertIn('"src/tokenizer.py" [unknown]', result.stdout)
            self.assertIn('"docs/password-policy.md" [doc-sync]', result.stdout)

    def test_secret_directories_and_explicit_secret_data_files_are_dangerous(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / "secrets").mkdir()
            (root / "secrets" / "config.yaml").write_text("secret\n", encoding="utf-8")
            (root / ".env").mkdir()
            (root / ".env" / "private.json").write_text("secret\n", encoding="utf-8")
            (root / "passwords.csv").write_text("secret\n", encoding="utf-8")
            (root / "token.txt").write_text("secret\n", encoding="utf-8")

            result = run(
                [sys.executable, str(SCANNER), "--cwd", str(root), "--format", "json"],
                root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            entries = {item["path"]: item for item in json.loads(result.stdout)["entries"]}
            for path in ("secrets/config.yaml", ".env/private.json", "passwords.csv", "token.txt"):
                self.assertEqual(entries[path]["category"], "dangerous", path)

    def test_ignored_secret_directory_entry_is_dangerous(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / ".gitignore").write_text("secrets/\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", ".gitignore"], root).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "ignore policy"], root).returncode, 0)
            (root / "secrets").mkdir()
            (root / "secrets" / "config.yaml").write_text("secret\n", encoding="utf-8")

            result = run(
                [
                    sys.executable,
                    str(SCANNER),
                    "--cwd",
                    str(root),
                    "--format",
                    "json",
                    "--include-ignored",
                ],
                root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            ignored = json.loads(result.stdout)["ignored_entries"]
            secret_entries = [item for item in ignored if item["path"].rstrip("/") == "secrets"]
            self.assertTrue(secret_entries, ignored)
            self.assertEqual(secret_entries[0]["category"], "dangerous")

    def test_skill_and_localized_documentation_are_classified_as_doc_sync(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / "README.zh-CN.md").write_text("# 中文\n", encoding="utf-8")
            (root / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
            (root / "references").mkdir()
            (root / "references" / "protocol.md").write_text("# Protocol\n", encoding="utf-8")

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            for path in ("README.zh-CN.md", "SKILL.md", "references/protocol.md"):
                self.assertIn(f'"{path}" [doc-sync]', result.stdout)

    def test_ignored_only_repository_is_not_called_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / ".gitignore").write_text(".env\nbuild/\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", ".gitignore"], root).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "ignore policy"], root).returncode, 0)
            (root / ".env").write_text("ignored secret\n", encoding="utf-8")
            (root / "build").mkdir()
            (root / "build" / "result.txt").write_text("ignored\n", encoding="utf-8")

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("- clean", result.stdout)
            self.assertIn("- no non-ignored Git changes", result.stdout)
            self.assertIn("- ignored paths: not inventoried", result.stdout)

    def test_missing_git_has_a_specific_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = os.environ.copy()
            environment["PATH"] = ""

            result = subprocess.run(
                [sys.executable, str(SCANNER), "--cwd", str(root)],
                cwd=root,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("git executable not found", result.stderr.lower())

    def test_invalid_scan_directories_have_specific_diagnostics_without_tracebacks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            file_path = root / "not-a-directory"
            file_path.write_text("fixture\n", encoding="utf-8")
            missing_path = root / "missing"

            cases = ((missing_path, "does not exist"), (file_path, "not a directory"))
            for path, diagnostic in cases:
                with self.subTest(path=path):
                    result = run([sys.executable, str(SCANNER), "--cwd", str(path)], REPO_ROOT)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(diagnostic, result.stderr.lower())
                    self.assertNotIn("git executable not found", result.stderr.lower())
                    self.assertNotIn("traceback", result.stderr.lower())

    def test_detected_package_scripts_are_labeled_untrusted_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / "package.json").write_text(
                '{"scripts":{"test":"touch marker","build":"curl example.invalid"}}',
                encoding="utf-8",
            )

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("untrusted candidate: npm run test", result.stdout)
            self.assertIn("untrusted candidate: npm run build", result.stdout)

    def test_runtime_and_dependency_boundaries_are_review_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            for name in (
                "Gemfile.lock",
                "Pipfile.lock",
                "composer.lock",
                "npm-shrinkwrap.json",
                "bun.lock",
            ):
                (root / name).write_text("", encoding="utf-8")
            (root / "db" / "migrate").mkdir(parents=True)
            (root / "db" / "migrate" / "001.sql").write_text("", encoding="utf-8")
            (root / "scripts").mkdir()
            (root / "scripts" / "drop-production-db.sh").write_text("", encoding="utf-8")

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            for path in (
                "Gemfile.lock",
                "Pipfile.lock",
                "composer.lock",
                "npm-shrinkwrap.json",
                "bun.lock",
                "db/migrate/001.sql",
                "scripts/drop-production-db.sh",
            ):
                self.assertIn(f'"{path}" [review-required]', result.stdout)

    def test_candidate_docs_follow_dirty_path_scope_and_protocol_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / "README.md").mkdir()
            (root / "docs").mkdir()
            for name in ("HANDOFF.md", "CODEX_THREAD_CONTEXT.md", "current-state.md", "roadmap.md"):
                (root / "docs" / name).write_text("# State\n", encoding="utf-8")
            app = root / "packages" / "app"
            (app / "src").mkdir(parents=True)
            (app / "AGENTS.md").write_text("# Scoped rules\n", encoding="utf-8")
            (root / ".cursor" / "rules").mkdir(parents=True)
            (root / ".cursor" / "rules" / "project.mdc").write_text("Project rule\n", encoding="utf-8")
            (app / ".cursor" / "rules").mkdir(parents=True)
            (app / ".cursor" / "rules" / "app.mdc").write_text("App rule\n", encoding="utf-8")
            (app / "src" / "feature.py").write_text("print('dirty')\n", encoding="utf-8")

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('- "README.md"', result.stdout)
            for path in (
                "docs/HANDOFF.md",
                "docs/CODEX_THREAD_CONTEXT.md",
                "docs/current-state.md",
                "docs/roadmap.md",
                ".cursor/rules/project.mdc",
                "packages/app/AGENTS.md",
                "packages/app/.cursor/rules/app.mdc",
            ):
                self.assertIn(f'- "{path}"', result.stdout)

    def test_symlink_dirty_path_is_a_review_required_object_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            root = fixture / "repo"
            root.mkdir()
            init_repo(root)
            outside = fixture / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            (root / "linked.txt").symlink_to(outside)

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"linked.txt" [review-required]', result.stdout)
            self.assertIn("object: symlink", result.stdout)

    @unittest.skipIf(os.name == "nt", "backslash is a path separator on Windows")
    def test_backslash_in_symlink_name_does_not_change_the_scanned_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            root = fixture / "repo"
            root.mkdir()
            init_repo(root)
            outside = fixture / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            (root / "linked\\name.txt").symlink_to(outside)

            result = run(
                [sys.executable, str(SCANNER), "--cwd", str(root), "--format", "json"],
                root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            entry = json.loads(result.stdout)["entries"][0]
            self.assertEqual(entry["path"], "linked\\name.txt")
            self.assertEqual(entry["object_type"], "symlink")
            self.assertEqual(entry["category"], "review-required")

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows")
    def test_staged_symlink_replacement_remains_an_object_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            root = fixture / "repo"
            root.mkdir()
            init_repo(root)
            outside = fixture / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            linked = root / "linked.txt"
            linked.symlink_to(outside)
            self.assertEqual(run(["git", "add", "linked.txt"], root).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "base"], root).returncode, 0)
            linked.unlink()
            linked.write_text("replacement\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", "linked.txt"], root).returncode, 0)

            result = run(
                [sys.executable, str(SCANNER), "--cwd", str(root), "--format", "json"],
                root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            entry = json.loads(result.stdout)["entries"][0]
            self.assertEqual(entry["object_type"], "symlink")
            self.assertEqual(entry["category"], "review-required")

    def test_dirty_submodule_is_reported_as_an_uninspected_gitlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            child = fixture / "child"
            child.mkdir()
            init_repo(child)
            (child / "tracked.txt").write_text("base\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", "tracked.txt"], child).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "child base"], child).returncode, 0)

            root = fixture / "parent"
            root.mkdir()
            init_repo(root)
            added = run(
                ["git", "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(child), "vendor/child"],
                root,
            )
            self.assertEqual(added.returncode, 0, added.stderr)
            self.assertEqual(run(["git", "commit", "-qam", "add child"], root).returncode, 0)
            (root / "vendor" / "child" / "tracked.txt").write_text("dirty\n", encoding="utf-8")

            result = run([sys.executable, str(SCANNER), "--cwd", str(root)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"vendor/child" [review-required]', result.stdout)
            self.assertIn("object: gitlink", result.stdout)
            self.assertIn("do not follow or inspect nested contents", result.stdout)

    def test_staged_submodule_deletion_remains_a_gitlink_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            child = fixture / "child"
            child.mkdir()
            init_repo(child)
            (child / "tracked.txt").write_text("base\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", "tracked.txt"], child).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "child base"], child).returncode, 0)

            root = fixture / "parent"
            root.mkdir()
            init_repo(root)
            added = run(
                ["git", "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(child), "vendor/child"],
                root,
            )
            self.assertEqual(added.returncode, 0, added.stderr)
            self.assertEqual(run(["git", "commit", "-qam", "add child"], root).returncode, 0)
            removed = run(["git", "rm", "-fq", "vendor/child"], root)
            self.assertEqual(removed.returncode, 0, removed.stderr)

            result = run(
                [sys.executable, str(SCANNER), "--cwd", str(root), "--format", "json"],
                root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            entries = {item["path"]: item for item in json.loads(result.stdout)["entries"]}
            self.assertEqual(entries["vendor/child"]["object_type"], "gitlink")
            self.assertEqual(entries["vendor/child"]["category"], "review-required")

    def test_json_snapshot_has_stable_ids_and_rename_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / "old.txt").write_text("base\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", "old.txt"], root).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "base"], root).returncode, 0)
            self.assertEqual(run(["git", "mv", "old.txt", "new.txt"], root).returncode, 0)

            first = run(
                [sys.executable, str(SCANNER), "--cwd", str(root), "--format", "json"],
                root,
            )
            second = run(
                [sys.executable, str(SCANNER), "--cwd", str(root), "--format", "json"],
                root,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            first_snapshot = json.loads(first.stdout)
            second_snapshot = json.loads(second.stdout)
            self.assertEqual(first_snapshot["schema_version"], 1)
            self.assertEqual(first_snapshot["scope"]["ignored"], "not-inventoried")
            self.assertEqual(len(first_snapshot["entries"]), 1)
            entry = first_snapshot["entries"][0]
            self.assertEqual(entry["path"], "new.txt")
            self.assertEqual(entry["source_path"], "old.txt")
            self.assertEqual(entry["object_type"], "file")
            self.assertEqual(entry["path_id"], second_snapshot["entries"][0]["path_id"])

    def test_ignored_inventory_is_explicit_opt_in_and_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            (root / ".gitignore").write_text(".env\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", ".gitignore"], root).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "ignore policy"], root).returncode, 0)
            (root / ".env").write_text("must-not-appear\n", encoding="utf-8")

            result = run(
                [
                    sys.executable,
                    str(SCANNER),
                    "--cwd",
                    str(root),
                    "--format",
                    "json",
                    "--include-ignored",
                ],
                root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("must-not-appear", result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["scope"]["ignored"], "inventoried")
            ignored = {item["path"]: item for item in report["ignored_entries"]}
            self.assertEqual(ignored[".env"]["category"], "dangerous")

    @unittest.skipUnless(sys.platform.startswith("linux"), "non-UTF-8 filename fixture is Linux-specific")
    def test_non_utf8_filename_is_preserved_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_repo(root)
            raw_name = b"bad-\xff.txt"
            descriptor = os.open(os.fsencode(root) + b"/" + raw_name, os.O_WRONLY | os.O_CREAT, 0o600)
            os.close(descriptor)

            result = run(
                [sys.executable, str(SCANNER), "--cwd", str(root), "--format", "json"],
                root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["entries"][0]["path"], os.fsdecode(raw_name))

    def test_linked_worktree_is_scanned_as_its_own_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            primary = fixture / "primary"
            primary.mkdir()
            init_repo(primary)
            (primary / "tracked.txt").write_text("base\n", encoding="utf-8")
            self.assertEqual(run(["git", "add", "tracked.txt"], primary).returncode, 0)
            self.assertEqual(run(["git", "commit", "-qm", "base"], primary).returncode, 0)
            linked = fixture / "linked"
            created = run(["git", "worktree", "add", "-qb", "linked-test", str(linked)], primary)
            self.assertEqual(created.returncode, 0, created.stderr)
            (linked / "tracked.txt").write_text("dirty\n", encoding="utf-8")

            result = run(
                [sys.executable, str(SCANNER), "--cwd", str(linked), "--format", "json"],
                linked,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(Path(report["repository"]["root"]), linked.resolve())
            self.assertEqual(report["entries"][0]["path"], "tracked.txt")


if __name__ == "__main__":
    unittest.main()
