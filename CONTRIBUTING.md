# Contributing

Thanks for helping improve Scourgify. Focused fixes, tests, documentation corrections, and clearly scoped protocol proposals are welcome.

## Before opening a pull request

1. For a protocol or behavior change, open a proposal first so its evidence, safety boundaries, and compatibility impact can be discussed.
2. Use CPython 3.10 or newer. Scourgify has no runtime dependencies outside the standard library.
3. Run:

   ```bash
   python -m compileall -q scripts tests
   python scripts/scourgify_scan.py --help
   python scripts/scourgify_scan.py --self-test
   python scripts/validate_closeout.py --help
   python -m unittest discover -s tests -p 'test_*.py' -v
   ```

4. Add or update tests for behavior changes. Keep `README.md` and `README.zh-CN.md` behaviorally aligned when user-facing instructions change.
5. Preserve the scanner's read-only behavior and the skill's explicit permission boundaries. Use a specific, imperative commit subject and keep each commit focused on one purpose.

## Privacy and security

Scanner snapshots, ledger files, logs, and screenshots can reveal repository paths or project structure even when they contain no file contents. Sanitize every reproduction and do not commit credentials, private repository material, local usernames, or personal data.

Report security issues privately as described in [SECURITY.md](SECURITY.md).
