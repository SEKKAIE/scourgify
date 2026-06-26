---
name: scourgify
description: Scourgify closes out AI coding work by auditing dirty repository state, classifying changed files, syncing source-of-truth docs and handoff notes, recording verification, and preparing safe commit or PR boundaries. Use when the user says "Scourgify!", asks to clean up after Codex/Claude/vibe-coding sessions, reconcile multi-chat or multi-agent work, update repo hygiene, prepare a handoff, decide what to stage/ignore/remove, or verify docs and git status before calling work done.
---

# Scourgify

Scourgify is a repo-hygiene closeout. Make the repository tell one true story: dirty files understood, docs current where needed, verification recorded, and unsafe actions left for explicit user permission.

## Contract

Clean does not mean empty `git status`. Clean means every changed path has an owner, a reason, a next action, and evidence.

Never silently revert, delete, overwrite, stage, commit, or hide unrelated user work. Never read or print secret file contents.

## Run Loop

1. **Scout.**
   - Run `py -3 <skill-dir>/scripts/scourgify_scan.py`.
   - If `py -3` is unavailable, try `python <skill-dir>/scripts/scourgify_scan.py`.
   - If the directory is not a git repo, say so and switch to a best-effort file/doc handoff instead of pretending git evidence exists.
2. **Read the rules.**
   - Read repo guidance before edits: `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md`, then equivalent local files.
   - If canonical docs are unclear, read `references/repo-doc-patterns.md`.
3. **Classify every dirty path.**
   - Assign owner, reason, action, and permission state.
   - If ownership is unclear, inspect diffs and nearby references before deciding.
4. **Sync only changed truth.**
   - Update durable docs only when behavior, setup, runtime state, verification, product/design contract, or future-agent instructions changed.
   - Do not edit every doc because it exists.
5. **Verify.**
   - Run relevant tests/build/smoke checks when behavior changed.
   - Always run `git diff --check` after edits and finish with `git status --short --branch`.
   - Report skipped checks with the concrete reason.
6. **Handoff.**
   - Group remaining paths by action: ready to keep, docs synced, generated/evidence cleanup, needs user permission, unrelated user work, unresolved risk.

## Classification

- `task-owned`: produced by this request; keep, stage, or commit only when requested.
- `doc-sync`: documentation or handoff state that may need truth updates.
- `generated-safe`: cache/build output; remove or ignore only when repo policy allows.
- `verification-evidence`: screenshots, reports, snapshots, or test artifacts; keep only if they support the handoff.
- `review-required`: lockfiles, migrations, destructive scripts, or runtime-affecting changes; inspect before staging or deleting.
- `dangerous`: secrets, env files, credentials, tokens, keys, large personal data; do not read contents.
- `unrelated-user-work`: pre-existing or user-created work; report and leave untouched.
- `unknown`: not yet understood; keep investigating or ask the user.

The scanner gives a first-pass category. The agent owns the final classification after reading repo rules, diffs, and task context.

## Doc Sync Rules

Update the smallest durable surface that future agents or users will read:

- Future-agent rule changed: `AGENTS.md`, `CLAUDE.md`, or equivalent.
- Setup, install, command, port, or runtime entrypoint changed: `README.md`.
- Current verified state, local gaps, or operational evidence changed: `PROJECT.md`, `docs/*CURRENT*`, `docs/*SYNC*`, or handoff docs.
- Product boundary changed: `PRODUCT.md`, product-intent docs, or roadmap docs.
- UI/UX contract changed: `design.md` or design-system docs.
- Only a transient local check happened: final response is usually enough unless the repo explicitly tracks process sync.

After doc edits, search for stale old terms: feature names, commands, ports, providers, model names, temporary/mock/fallback notes, and design rules that now contradict the code.

## Safety Boundaries

- Use `git check-ignore -v <path>` for secret-like paths instead of opening them.
- Do not remove generated files unless the user requested cleanup or repo policy clearly permits it.
- Do not stage broad patterns such as `git add .` in dirty repos.
- Do not claim "all chats are synced" unless durable repo or memory surfaces were actually updated.
- Update global/managed memory only when the user explicitly asks for memory updates, and use the environment's approved memory mechanism.
- If a commit or push is requested, stage only the intended change group and confirm branch/upstream first.

## Multi-Chat Closeout

When the user mentions multiple chats, forks, agents, or "sync all chats":

1. Treat durable repo docs and approved memory notes as the shared source of truth.
2. Preserve dates when nearby chats disagree.
3. Record latest verified behavior, commands run, skipped checks, and known risks.
4. Put recurring rules in repo instructions, not only in the final chat response.
5. Explicitly name any context that remains unsynced.

## Final Response

Keep it short and concrete:

- What changed.
- What was verified.
- What remains dirty and why.
- What still needs user permission, if anything.

When no files need edits, say that clearly and still report repo status.
