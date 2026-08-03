<div align="center">

# Scourgify

### 除垢咒

**A conservative closeout for the messy moment after AI coding.**

*Understand every changed path before staging, deleting, or handing it off.*

[English](./README.md) · [简体中文](./README.zh-CN.md)

[![Codex verified](https://img.shields.io/badge/Codex-verified-111827?style=for-the-badge&logo=openai&logoColor=white)](https://learn.chatgpt.com/docs/build-skills)
[![Claude Code compatible](https://img.shields.io/badge/Claude%20Code-compatible-D97757?style=for-the-badge)](https://code.claude.com/docs/en/skills)
[![Cursor compatible](https://img.shields.io/badge/Cursor-compatible-111111?style=for-the-badge)](https://cursor.com/docs/skills)
![Protocol](https://img.shields.io/badge/Protocol-Conservative-2F6FED?style=for-the-badge)
![Scanner](https://img.shields.io/badge/Scanner-Read--only-6D28D9?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-D4A017?style=for-the-badge)

**Verified on Codex. Packaged for the documented Claude Code and Cursor Agent Skills layouts.**

</div>

<p align="center">
  <img src="./assets/scourgify-hero-v1.png" alt="A four-colour pixel-art wand casting a cleaning spell into the dark" width="100%">
</p>

---

AI coding rarely ends when the code starts working. It ends with a dirty worktree: source changes beside stale docs, generated files beside real work, and no reliable record of what should be kept, verified, staged, ignored, or left alone.

Scourgify does not chase a cosmetically empty `git status`. It makes repository state legible: every changed path gets an owner, a reason, a next action, evidence, and a permission state—and mechanically checks that none were omitted.

## What it does

1. **Scouts the repository** with a standard-library-only, read-only scanner. Runtime prerequisites are Python 3 and Git.
2. **Reads local rules first** before deciding what any path means.
3. **Classifies every non-ignored dirty path** without treating generated output, secrets, object boundaries, and user work as equivalent. Ignored metadata is explicit opt-in.
4. **Syncs only changed truth** instead of rewriting every document that happens to exist.
5. **Records verification honestly**, including checks that were skipped and why.
6. **Reconciles before and after snapshots** against a structured ledger, then leaves a bounded handoff for the developer, next agent, commit, or pull request.

## The closeout ledger

Before action, Scourgify makes every changed path answer the same questions:

| Field | Question | Typical values |
| --- | --- | --- |
| Owner | Whose work is this? | Current task, user, another agent, unknown |
| Reason | Why is it dirty? | Implementation, doc sync, generated output, evidence |
| Next action | What should happen next? | Keep, inspect, ignore, remove, stage, ask |
| Evidence | What supports that decision? | Diff, test, build, screenshot, repo rule |
| Permission | Is the action authorized? | `not-required`, `granted`, `required`, `denied` |

The scanner provides a first-pass category. The agent remains responsible for inspecting repository rules, diffs, and task context before acting.

## Use it when

- An AI coding session looks finished, but the worktree still needs a trustworthy closeout.
- Code, documentation, generated output, and verification evidence may have drifted apart.
- Work has moved across chats or agents and the repository needs one durable handoff.
- You want a safe boundary for the next commit or pull request.

## Do not use it when

- You want a refactor, formatter, or general-purpose code cleanup rather than a closeout.
- You expect every dirty path to be deleted or staged automatically.
- You cannot distinguish current-task work from unrelated user work.

## Start

```text
Scourgify!
```

Or be explicit:

```text
Use $scourgify to audit this repository, sync key docs, verify the work, and report remaining dirty files.
```

The skill will inspect first. Destructive cleanup, broad staging, commits, and pushes remain outside the default boundary.

## What it will not do

- It will not read or print secret-file contents.
- It will not use a broad `git add .` in a dirty repository.
- It will not silently revert, delete, overwrite, stage, or commit unrelated user work.
- It will not claim chats or docs are synchronized unless a durable source of truth was actually updated.

## Scanner

Run the read-only human report from the cloned skill directory:

```bash
python3 scripts/scourgify_scan.py --cwd /path/to/repository
```

Capture a machine-readable snapshot outside the target repository:

```bash
python3 scripts/scourgify_scan.py --cwd /path/to/repository --format json > /tmp/scourgify-before.json
```

Ignored-path metadata is opt-in:

```bash
python3 scripts/scourgify_scan.py --cwd /path/to/repository --include-ignored
```

After the closeout, validate the before/after snapshots and ledger:

```bash
python3 scripts/validate_closeout.py \
  --before /tmp/scourgify-before.json \
  --after /tmp/scourgify-after.json \
  --ledger /tmp/scourgify-ledger.json
```

Run its self-test with:

```bash
python3 scripts/scourgify_scan.py --self-test
```

On Windows, use `py -3` in place of `python3`.

## Included

- `SKILL.md` — the conservative closeout protocol
- `scripts/scourgify_scan.py` — standard-library-only human/JSON repository scanner
- `scripts/validate_closeout.py` — deterministic snapshot and ledger reconciliation
- `references/repo-doc-patterns.md` — fallback map for source-of-truth documentation
- `references/closeout-ledger.md` — five-field ledger contract and template
- `agents/openai.yaml` — Codex skill metadata
- `tests/` and `.github/workflows/ci.yml` — real Git fixtures on Linux, macOS, and Windows

## Install

### Codex — verified

With the Skills installer:

```bash
npx skills@latest add SEKKAIE/scourgify -g -a codex --copy --full-depth
```

Or clone it directly:

```bash
git clone https://github.com/SEKKAIE/scourgify.git ~/.codex/skills/scourgify
```

Start a new Codex chat after installation so the skill list reloads.

### Claude Code — compatible Agent Skill

Claude Code loads personal skills from `~/.claude/skills/<skill-name>/SKILL.md`:

```bash
git clone https://github.com/SEKKAIE/scourgify.git ~/.claude/skills/scourgify
```

Invoke it with `/scourgify`. If the top-level skills directory did not exist when Claude Code started, restart Claude Code once so it can watch the new directory. See the official [Claude Code skills documentation](https://code.claude.com/docs/en/skills).

### Cursor — compatible Agent Skill

Cursor loads user skills from `~/.cursor/skills/` or `~/.agents/skills/`:

```bash
git clone https://github.com/SEKKAIE/scourgify.git ~/.cursor/skills/scourgify
```

Invoke it with `/scourgify` or let Agent select it from the description. See the official [Cursor Agent Skills documentation](https://cursor.com/docs/skills).

Codex invocation is locally smoke-tested for this release. Claude Code and Cursor compatibility is kept deliberately narrower: the repository follows their documented Agent Skills format and install locations, but does not claim a live host smoke test where those applications are unavailable.

## Name note

This project only borrows the cleaning-spell metaphor. It is not affiliated with Harry Potter, Wizarding World, Warner Bros. Discovery, or J.K. Rowling. [HarryPotter.com](https://www.harrypotter.com/features/every-spell-we-wish-we-could-use-for-spring-cleaning-season) uses `Scourgify` as a cleaning-spell reference; the fan-maintained Harry Potter Wiki lists the [Scouring Charm](https://harrypotter.fandom.com/wiki/Scouring_Charm) incantation as `Scourgify` and its [Simplified Chinese page](https://harrypotter.fandom.com/zh/wiki/%E9%99%A4%E5%9E%A2%E5%92%92) lists `除垢咒` / `清理一新`.
