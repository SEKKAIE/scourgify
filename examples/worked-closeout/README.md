# Worked closeout

This synthetic packet demonstrates deterministic reconciliation without containing source code, credentials, or real repository identifiers.

It represents a closeout in which:

- `README.md` was stale in the before snapshot and is reconciled by the end;
- `src/app.py` remains as reviewed task work in both snapshots;
- `docs/HANDOFF.md` appears during closeout and is therefore added to the ledger;
- every path ID in the before/after union appears exactly once in `ledger.json`.

Run from the repository root:

```bash
python3 scripts/validate_closeout.py \
  --before examples/worked-closeout/before.json \
  --after examples/worked-closeout/after.json \
  --ledger examples/worked-closeout/ledger.json
```

The output should match [`expected.txt`](./expected.txt):

```text
# Scourgify Closeout Validation

- complete: yes
- work ready: yes
- before: 2
- after: 2
- expected: 3
- ledger: 3
```

This proves that the packet is structurally reconciled. It does not prove that evidence in an arbitrary ledger is true or that an external action is authorized.
