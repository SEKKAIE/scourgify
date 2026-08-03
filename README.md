<div align="center">

# Scourgify

### 除垢咒

**Scourgify is a permission-aware Codex closeout protocol that snapshots a dirty Git worktree, reconciles every in-scope path in a five-field ledger, and validates the handoff before work is called complete.**

[English](./README.md) · [简体中文](./README.zh-CN.md)

[![Codex skill](https://img.shields.io/badge/Codex-skill-111827?logo=openai&logoColor=white)](#quickstart)
[![CI](https://github.com/SEKKAIE/scourgify/actions/workflows/ci.yml/badge.svg)](https://github.com/SEKKAIE/scourgify/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/SEKKAIE/scourgify?display_name=tag&sort=semver)](https://github.com/SEKKAIE/scourgify/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-D4A017.svg)](./LICENSE)

</div>

<p align="center">
  <img src="./assets/scourgify-hero-v1.png" alt="A four-colour pixel-art wand casting a cleaning spell into the dark" width="860">
</p>

AI coding rarely ends when the code starts working. It ends with source changes beside stale docs, generated files beside real work, and no reliable record of what should be kept, verified, staged, ignored, or left alone.

Scourgify does not chase a cosmetically empty `git status`. It makes the in-scope repository state legible, preserves unrelated user work, and distinguishes a structurally complete ledger from work that is actually ready to proceed.

## Quickstart

### 1. Install

Install the reviewed `v1.1.0` release in your Codex skills directory:

```bash
git clone --branch v1.1.0 --depth 1 \
  https://github.com/SEKKAIE/scourgify.git \
  ~/.codex/skills/scourgify
```

On Windows PowerShell:

```powershell
git clone --branch v1.1.0 --depth 1 `
  https://github.com/SEKKAIE/scourgify.git `
  "$env:USERPROFILE\.codex\skills\scourgify"
```

Python 3.10 or later and Git are required for the included scanner and validator.

### 2. Verify the CLI

```bash
python3 ~/.codex/skills/scourgify/scripts/scourgify_scan.py --self-test
```

On Windows PowerShell:

```powershell
py -3 "$env:USERPROFILE\.codex\skills\scourgify\scripts\scourgify_scan.py" --self-test
```

Expected result:

```text
self-test: ok
```

### 3. Invoke

Open a new Codex task and write:

```text
Use $scourgify to close out this dirty repository, reconcile every in-scope path, and report anything that still needs permission.
```

### 4. Confirm the result

The first report should identify the exact repository root, branch, upstream, snapshot scope, candidate docs, and each in-scope path. It should not silently delete, revert, stage, commit, or push anything.

A completed closeout ends with validated before/after/expected/ledger counts. `complete: yes` means the ledger reconciles structurally; `work ready: no` is still an honest result when one or more actions need permission.

## How it works

1. **Confirm scope.** Resolve the repository, branch, upstream, object boundaries, and allowed actions.
2. **Freeze the baseline.** Capture a standard-library-only, read-only JSON snapshot outside the target repository.
3. **Read local rules.** Inspect applicable instructions and durable state before interpreting a path.
4. **Build the ledger.** Give every in-scope path an owner, reason, next action, evidence, and permission state.
5. **Sync changed truth.** Update only the smallest durable documentation surface that actually drifted.
6. **Verify safely.** Treat discovered commands as untrusted candidates and record skipped checks honestly.
7. **Reconcile mechanically.** Validate the union of the before and after snapshots against the ledger.
8. **Hand off.** Report what is ready, what remains dirty, and which exact path IDs still need a decision.

| Ledger field | Question |
| --- | --- |
| `owner` | Whose work is this? |
| `reason` | Why is the path dirty or newly present? |
| `next_action` | What bounded disposition comes next? |
| `evidence` | What test, diff, rule, or observation supports it? |
| `permission` | Is the action authorized? |

The scanner provides a first-pass category. The agent remains responsible for checking repository rules, diffs, evidence, and task context before acting.

## Worked example

[`examples/worked-closeout`](./examples/worked-closeout/README.md) contains synthetic before and after snapshots plus a complete permission-aware ledger.

Run the validator from the repository root:

```bash
python3 scripts/validate_closeout.py \
  --before examples/worked-closeout/before.json \
  --after examples/worked-closeout/after.json \
  --ledger examples/worked-closeout/ledger.json
```

Expected summary: two paths appear before, two appear after, the union contains three stable path IDs, all three have exactly one ledger row, and the validator reports both `complete: yes` and `work ready: yes`.

## Scope and limitations

- The deterministic scanner operates on a Git repository. A non-Git fallback is a separately bounded name inventory and is not equivalent to a validated Git closeout.
- “Every in-scope path” means the union of non-ignored paths captured in the before and after snapshots, plus ignored-path metadata only when both snapshots explicitly use `--include-ignored`.
- Symlinks and gitlinks/submodules are reported as object boundaries; their targets or nested contents are not inspected by the parent scan.
- Classification is heuristic. A category never grants authority to delete, ignore, stage, commit, or push.
- Secret-file contents are not read or copied into the ledger. Snapshots still contain metadata such as the absolute repository root and filenames; sanitize private paths and identifiers before sharing them.
- Suggested test, build, or lint commands are untrusted candidates until repository instructions and their exact definitions have been inspected.
- A valid ledger proves structural reconciliation, not that its evidence is true or that an outstanding action is authorized.

## Compatibility and evidence

| Host | Evidence-scoped status |
| --- | --- |
| Codex | The `v1.1.0` package metadata and deterministic CLI behavior are verified with skill validation, the scanner self-test, the full unittest suite, and the runnable worked example. This does not claim identical model behavior on every repository. |
| Claude Code | Layout-compatible only: the repository follows the documented personal Agent Skills directory and top-level `SKILL.md` format. No live-host smoke test is claimed. See the [Claude Code skills documentation](https://code.claude.com/docs/en/skills). |
| Cursor | Layout-compatible only: the repository follows the documented user Agent Skills directories and top-level `SKILL.md` format. No live-host smoke test is claimed. See the [Cursor Agent Skills documentation](https://cursor.com/docs/skills). |

## CLI reference

Run a human-readable scan from the cloned skill directory:

```bash
python3 scripts/scourgify_scan.py --cwd /path/to/repository
```

Capture a JSON snapshot outside the target repository:

```bash
python3 scripts/scourgify_scan.py --cwd /path/to/repository --format json > /tmp/scourgify-before.json
```

Opt in to ignored-path metadata without reading ignored-file contents:

```bash
python3 scripts/scourgify_scan.py --cwd /path/to/repository --include-ignored
```

Validate a completed packet:

```bash
python3 scripts/validate_closeout.py \
  --before /tmp/scourgify-before.json \
  --after /tmp/scourgify-after.json \
  --ledger /tmp/scourgify-ledger.json
```

## Repository map

- [`SKILL.md`](./SKILL.md) — permission-aware closeout protocol
- [`scripts/scourgify_scan.py`](./scripts/scourgify_scan.py) — read-only human/JSON repository scanner
- [`scripts/validate_closeout.py`](./scripts/validate_closeout.py) — deterministic snapshot and ledger reconciliation
- [`agents/openai.yaml`](./agents/openai.yaml) — Codex skill metadata
- [`references/closeout-ledger.md`](./references/closeout-ledger.md) — ledger contract and template
- [`references/repo-doc-patterns.md`](./references/repo-doc-patterns.md) — fallback map for durable repository docs
- [`examples/worked-closeout`](./examples/worked-closeout/README.md) — runnable synthetic packet
- [`evals/trigger-cases.json`](./evals/trigger-cases.json) — intended trigger and non-trigger cases; not a behavioral benchmark result
- [`tests`](./tests) and [`ci.yml`](./.github/workflows/ci.yml) — real Git fixtures and the cross-platform verification matrix

## Contributing and security

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the local verification commands and pull-request expectations. Report vulnerabilities privately through the process in [`SECURITY.md`](./SECURITY.md); never attach unsanitized snapshots, ledgers, secrets, or private repository material to a public issue.

## License

[MIT](./LICENSE)

## Name note

Scourgify is an unofficial project name chosen for its cleaning metaphor; no affiliation or endorsement is claimed.
