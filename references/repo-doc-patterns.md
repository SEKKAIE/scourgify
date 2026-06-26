# Repo Doc Patterns

Use this reference only when the repository does not clearly identify its canonical docs.

## Common Instruction Files

- `AGENTS.md`: agent-facing repo rules for Codex/OpenAI-style workflows.
- `CLAUDE.md`: Claude Code project memory and instructions.
- `.cursorrules`: Cursor-oriented repo guidance.
- `.github/copilot-instructions.md`: GitHub Copilot repository instructions.
- `CONTRIBUTING.md`: contributor workflow, tests, PR rules.

## Common Product And Process Files

- `README.md`: setup, status, commands, entrypoints, public overview.
- `PROJECT.md`: current project state, roadmap, active process.
- `PRODUCT.md`: audience, positioning, product contract.
- `design.md`: UI/UX rules, visual system, interaction contracts.
- `docs/PRODUCT_INTENT.md`: durable product spine and boundaries.
- `docs/*PLAN*.md`: implementation plan or orchestration design.
- `docs/*CURRENT*.md`, `docs/*SYNC*.md`, `docs/project-memory.md`: latest verified state and handoff notes.

## What To Update Where

- Durable future-agent rule changed: update `AGENTS.md` or `CLAUDE.md`.
- User-facing setup or command changed: update `README.md`.
- Current runtime or verification state changed: update `PROJECT.md` or current-state docs.
- UI behavior or design standard changed: update `design.md`.
- Product boundary changed: update product intent docs.
- Only a local transient check happened: usually final response is enough unless the repo tracks process sync.

## Common Action Groups

- Ready to keep: task-owned source changes with verification.
- Docs synced: documentation edits that match source/runtime truth.
- Evidence: screenshots, reports, fixtures, or logs that prove the handoff.
- Generated cleanup: cache/build output that repo policy allows removing.
- Needs permission: secrets, migrations, lockfiles, destructive scripts, unrelated user work.
- Unresolved: files whose owner, purpose, or safety is still unclear.

## Staleness Search

After changing docs, search for old terminology:

- Old feature names.
- Old command names.
- Old ports or service names.
- Old provider/model/prompt versions.
- Old design rules that contradict the new behavior.
- "TODO", "temporary", "mock", "fake", or "fallback" when the latest truth changed.

Do not remove historical notes just because they are old. Mark them historical if they explain prior verification or risk.
