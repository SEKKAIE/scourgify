## What changed

Describe the focused change and the problem it solves.

## Evidence

List tests, sanitized examples, or source material used to verify the change.

## Checklist

- [ ] I ran `python -m unittest discover -s tests -p 'test_*.py' -v`.
- [ ] I ran `python scripts/scourgify_scan.py --self-test`.
- [ ] I added or updated tests for behavior changes.
- [ ] I preserved Scourgify's read-only and permission boundaries.
- [ ] I kept English and Simplified Chinese instructions aligned where applicable.
- [ ] I included no credentials, private repository material, unsanitized paths, or personal data.
- [ ] I documented compatibility or protocol implications.
