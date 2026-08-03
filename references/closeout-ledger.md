# Closeout ledger

Create a JSON array outside the target repository. Include exactly one row for every `path_id` in the union of the before and after snapshots.

## Required fields

| Field | Requirement |
|---|---|
| `path_id` | Copy exactly from the scanner snapshot. |
| `path` | Copy the repository-relative path for that identity exactly from the snapshot. |
| `owner` | Name the current task, user, agent, or unrelated-work owner. |
| `reason` | Explain why the path is dirty or why it appeared. |
| `next_action` | State the bounded disposition or next decision. |
| `evidence` | Cite a test, command, diff, repository rule, or metadata observation. |
| `permission` | Use `not-required`, `granted`, `required`, or `denied`. |

For dangerous paths, evidence may describe only path, Git status, object type, and ignore-policy metadata. Never copy file contents into the ledger.

## Example

```json
[
  {
    "path_id": "scg-<sha256>",
    "path": "src/example.py",
    "owner": "current task",
    "reason": "implements the requested behavior",
    "next_action": "keep; eligible for the requested change group",
    "evidence": "targeted test and full test suite passed",
    "permission": "not-required"
  },
  {
    "path_id": "scg-<sha256>",
    "path": ".env.staging",
    "owner": "unknown",
    "reason": "secret-like path present in Git status",
    "next_action": "leave untouched pending explicit user decision",
    "evidence": "path, status, and ignore-policy metadata only",
    "permission": "required"
  }
]
```

Run the validator after capturing the final snapshot:

```text
<python3> <skill-dir>/scripts/validate_closeout.py \
  --before <before.json> \
  --after <after.json> \
  --ledger <ledger.json>
```

`complete: yes` means the ledger is structurally complete and reconciled. `work ready: no` means the handoff is valid but one or more recorded actions still need permission.
