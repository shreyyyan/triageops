# triage/realworld — real-world case study

This folder holds a **real bug from a real open-source project**, vendored
verbatim so Bob can diagnose third-party code, not just our seeded bugs.

## Provenance

- **Project:** [humanize](https://github.com/python-humanize/humanize)
  (`python-humanize/humanize`), MIT licensed, by Hugo van Kemenade and contributors.
- **Vendored version:** 4.3.0 — copied byte-for-byte from the official PyPI
  release (only the top-level directory was placed under `triage/realworld/`;
  pristine at intake � Bob's fix was applied to `humanize/number.py` in Task 15 (see `triage/fixes/fix_004.diff`).
- **The bug:** [`humanize.metric(0)` crashes](https://github.com/python-humanize/humanize/issues/57)
  with `ValueError: math domain error`.
- **Upstream fix:** [PR #47](https://github.com/python-humanize/humanize/pull/47),
  released in humanize 4.4.0.

## Layout

- `humanize/` — the vendored 4.3.0 package (verbatim).
- `repro_metric_zero.py` — minimal reproducer. Run from the repo root:

```bash
python triage/realworld/repro_metric_zero.py
```

Expected on 4.3.0: `ValueError: math domain error` (on Python 3.14 the message reads `ValueError: expected a positive input` � same exception, same line) from
`humanize/number.py:511`, in `metric()`.

## How Bob uses it (Tasks 12–16)

Bob gets the reproducer, the issue link, and the vendored source — but is
**not** shown the upstream fix. Bob traces the root cause, proposes a minimal
fix, applies it to this vendored copy, and verifies with the reproducer.
Only afterwards is Bob's fix compared against the real upstream fix (PR #47).
The comparison is documented in `triage/reports/incident_INC-2026-1045_report.md`.
