# Scourgify

Repo hygiene and handoff sync for AI coding sessions.

Scourgify is a Codex skill for the messy moment after coding work is "done": `git status` is dirty, docs may be stale, generated files are mixed with real work, and nobody is fully sure what should be staged, ignored, deleted, or left alone.

It gives an agent a conservative closeout workflow:

- classify every dirty path before acting
- protect secrets and unrelated user work
- sync only docs whose truth actually changed
- record verification honestly
- leave a clear handoff instead of chasing an empty `git status`

## Name And Chinese Localization

`Scourgify` borrows the exact Harry Potter incantation for the Scouring Charm: `Scourgify`. In Simplified Chinese Harry Potter references, the incantation is listed as `清理一新`, with the charm name rendered as `除垢咒`.

For this project, the grounded Chinese localization is:

**Scourgify / 清理一新：AI 编程后的仓库收尾清理技能**

这里的“清理一新”不是把工作区删到空，也不是为了追求一个表面干净的 `git status`。它指的是：在一次 AI 编程之后，把仓库里每个变更的归属、原因、下一步和验证证据清点清楚，让开发者或下一个 agent 能放心接手。

This project only borrows the cleaning-spell metaphor. It is not affiliated with Harry Potter, Wizarding World, Warner Bros. Discovery, or J.K. Rowling.

Reference wording: [HarryPotter.com](https://www.harrypotter.com/features/every-spell-we-wish-we-could-use-for-spring-cleaning-season) uses `Scourgify` as a cleaning spell reference, while the fan-maintained Harry Potter Wiki lists the [Scouring Charm](https://harrypotter.fandom.com/wiki/Scouring_Charm) incantation as `Scourgify` and its [Simplified Chinese page](https://harrypotter.fandom.com/zh/wiki/%E9%99%A4%E5%9E%A2%E5%92%92) lists `清理一新` / `除垢咒`.

## Who It Is For

Scourgify is useful for:

- developers using Codex, Claude Code, Cursor, or other coding agents
- vibe coders who want a safer "clean this repo up" workflow
- teams that hand work between multiple AI chats or agents
- maintainers who want docs, tests, and git state to agree before a commit or PR

It is deliberately read-only by default. The bundled scanner reports what it sees; the agent still needs explicit user permission before destructive cleanup or staging unrelated work.

## Install

If your skill installer supports GitHub skill repos, install from this repository:

```powershell
npx skills@latest add SEKKAIE/scourgify -g -a codex --copy --full-depth
```

You can also copy this repository into your Codex skills directory:

```powershell
git clone https://github.com/SEKKAIE/scourgify.git "$env:USERPROFILE\.codex\skills\scourgify"
```

Then start a new Codex chat so the skill list reloads.

## Use

In a repository, ask:

```text
Scourgify!
```

Or:

```text
Use $scourgify to audit this repository, sync key docs, verify the work, and report remaining dirty files.
```

The skill will run the scanner, read repo instructions, classify changes, update only the docs that need it, run relevant checks, and finish with a compact handoff.

## Scanner

The scanner is a small dependency-free Python script:

```powershell
py -3 .\scripts\scourgify_scan.py --cwd C:\path\to\repo
```

It reports:

- branch and upstream state
- candidate source-of-truth docs
- dirty files with first-pass categories
- reasons and suggested next actions
- common test/build commands from project files
- a closeout prompt for the agent

Run its self-test with:

```powershell
py -3 .\scripts\scourgify_scan.py --self-test
```

## Categories

Scourgify classifies dirty files into practical buckets:

- `task-owned`: work from the current request
- `doc-sync`: docs or handoff notes that may need truth updates
- `generated-safe`: build/cache output
- `verification-evidence`: screenshots, reports, snapshots, or test artifacts
- `review-required`: lockfiles, migrations, destructive scripts, runtime-affecting changes
- `dangerous`: secrets, env files, credentials, tokens, keys, personal data
- `unrelated-user-work`: work that belongs to the user or another task
- `unknown`: inspect before acting

The scanner gives a first pass. The agent must still inspect repo rules, diffs, and task context before making final decisions.

## Safety Model

Scourgify is built around one rule:

> Clean does not mean empty `git status`. Clean means every changed path has an owner, a reason, a next action, and evidence.

The skill tells agents not to:

- read or print secret file contents
- run broad `git add .` in dirty repos
- silently revert, delete, overwrite, stage, or commit unrelated user work
- claim chats or docs are synced unless durable surfaces were actually updated

## Repository Layout

```text
.
|-- SKILL.md
|-- agents/
|   `-- openai.yaml
|-- references/
|   `-- repo-doc-patterns.md
`-- scripts/
    `-- scourgify_scan.py
```

## License

MIT
