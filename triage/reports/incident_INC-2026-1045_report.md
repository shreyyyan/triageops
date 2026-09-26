# Incident Report — INC-2026-1045

| Field | Value |
|---|---|
| **Alert ID** | INC-2026-1045 |
| **Severity** | High |
| **Service** | billing-worker |
| **Endpoint** | POST /invoices |
| **Opened** | 2026-09-27T00:10:00Z |
| **Error** | `ValueError: math domain error` |

---

## Summary

A deploy introduced (or exposed) vendored `humanize 4.3.0` whose `metric()`
function crashes unconditionally when passed the value `0`.  Invoice PDF
generation calls `metric(0)` for credit / refund line items (net amount = 0).
The unhandled `ValueError` caused `billing-worker` to restart; **41 invoice
jobs failed** in the 10-minute window before the alert fired.  Non-zero line
items were unaffected throughout.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 00:02:11 | `billing-worker` / `worker-3` starts, consuming invoice queue |
| 00:03:44 | `inv-88121` (12 line items) renders OK |
| 00:05:02 | `inv-88122` (4 line items) renders OK |
| 00:06:30 | `inv-88123` starts — 7 line items, **includes 1 credit** |
| 00:06:31 | **First crash** — `ValueError: math domain error` at `number.py:511` |
| 00:06:32 | `inv-88123` queued for retry 1/3 |
| 00:07:15 | `inv-88124` (9 line items, no credits) renders OK |
| 00:08:03 | Second crash — `inv-88125` fails |
| 00:09:47 | API-gateway p99 latency 1.8 s (normal) |
| **00:10:00** | **INC-2026-1045 raised** — `ValueError` rate > threshold (41 jobs failed in 10 min) |
| 00:11:20 | Third logged crash — `inv-88127` fails |
| 00:13:05 | `inv-88128` (6 line items) renders OK |

*The logs show representative crashes; the alert reports 41 total failures in
the 10-minute window before 00:10:00.*

---

## Evidence

**Traceback (from logs and `incident_004.json`):**

```
File "triage/realworld/humanize/number.py", line 511, in metric
    exponent = int(math.floor(math.log10(abs(value))))
ValueError: math domain error
```

**Affected library:** `humanize 4.3.0` (vendored at
`triage/realworld/humanize/number.py`)

**Trigger input:** integer `0` — passed when a credit line item has a net
amount of zero.

**Customer impact (from `incident_004.json`):** Invoice PDF generation crashes
for zero-amount line items (refunds/credits); `billing-worker` restarts on the
unhandled `ValueError`; 41 invoice jobs failed since the deploy.

---

## Root Cause

`metric()` in `humanize/number.py` computes `math.log10(abs(value))` as its
**first and only statement** before any guard.  `math.log10` is defined only
on the strictly positive reals — its domain is `(0, +∞)`.  When `value = 0`,
`abs(0) = 0`, and `math.log10(0)` raises `ValueError` because log₁₀(0) = −∞
cannot be represented as a finite float.  No zero-check, early return, or
`try/except` exists anywhere in `metric()`; the crash is therefore
**deterministic and immediate** for any call with `value = 0`.

Zero is a fully legitimate billing input: it arises on credit/refund line
items and on template rows initialised before operator entry.  The 4.3.0
implementation silently assumed `value > 0` without documenting or enforcing
that constraint.

*(Full step-by-step analysis: `triage/reports/root_cause_004.md`)*

---

## Fix Applied and Verified

**Source:** `triage/fixes/fix_004.diff` — proposed by Bob in Task 14,
**before** any upstream fix was consulted.

**Change:** A two-line early-return guard inserted immediately before the
crash site on `number.py` line 511:

```python
# Before (line 511, verbatim):
exponent = int(math.floor(math.log10(abs(value))))

# After (lines 511–512 added, original line unchanged at 513):
if value == 0:
    return format(0, ".%if" % (precision - 1)) + \
           (" " if unit and unit not in ("°", "′", "″") else "") + unit
exponent = int(math.floor(math.log10(abs(value))))
```

**Verified outputs post-patch:**

| Call | Return |
|---|---|
| `metric(0)` | `"0.00"` |
| `metric(0, "V")` | `"0.00 V"` |
| `metric(0, "°")` | `"0.00°"` |
| `metric(0, unit="W", precision=4)` | `"0.000 W"` |

The fix is confirmed applied: `number.py` line 511 in the working tree now
reads `if value == 0:` (verified by direct file inspection).  All non-zero
paths are unaffected — the guard is gated strictly on `value == 0`.

---

## Prevention Suggestions

1. **Pin / upgrade the vendored library.** `humanize ≥ 4.4.0` ships the
   upstream fix; updating the vendor copy eliminates the divergence entirely.
2. **Add a regression test.** A unit test asserting `metric(0) == "0.00"`
   (and variants with units) would have caught this before merge.
3. **Input validation at the caller.** The billing layer could assert or log a
   warning when `metric()` is called with zero, making the data-flow visible
   even if the library handles it silently.
4. **Fuzz / boundary tests for vendored libraries.** When vendoring a
   third-party library, run its own test suite plus a boundary sweep
   (`-1, -0.001, 0, 0.001, 1`) against numeric utility functions.

---

## Bob vs Upstream

**Upstream fix — humanize PR #47, released in 4.4.0:**

```python
exponent = int(math.floor(math.log10(abs(value)))) if value != 0 else 0
```

This is an **inline ternary** on the existing line: it short-circuits to
`exponent = 0` when `value == 0`, then falls through to the rest of the
function body with `exponent = 0`.

**Bob's fix (Task 14, proposed independently):**

```python
if value == 0:
    return format(0, ".%if" % (precision - 1)) + \
           (" " if unit and unit not in ("°", "′", "″") else "") + unit
```

This is an **early return** before the `exponent` line: it never enters the
rest of the function body for zero.

### Are they equivalent?

**For the crash: yes.** Both fixes prevent `math.log10(0)` from being called,
so neither raises `ValueError` for `value = 0`.

**For output: effectively yes, but via different paths.**

- Upstream sets `exponent = 0`, then the main function body runs with
  `value /= 10 ** 0 == 1` (value stays `0`), `ordinal = ""` (exponent 0),
  and formats `0` with `precision - 1` decimal places — producing `"0.00"`
  for the default precision, with the unit suffix appended by the normal path.
- Bob's fix formats `0` directly with `precision - 1` decimal places and
  applies the same unit-spacing rule, producing the same string.

Both return `"0.00"` for `metric(0)` and `"0.00 V"` for `metric(0, "V")`.

### Where they differ

Bob's fix uses `value == 0` (equality on float/int).  Upstream uses
`value != 0` (same boundary, negated).  Neither handles negative-zero
(`-0.0`) differently from `+0.0` in Python — `abs(-0.0) == 0.0` and
`-0.0 == 0` are both `True`, so both fixes handle it identically.

**Upstream's approach is marginally better** for two reasons:

1. **Less code duplication.** The early-return in Bob's fix re-implements the
   unit-spacing logic that already exists in the function body; upstream
   re-uses that logic by falling through.  If the spacing rules ever change,
   upstream's fix requires only one edit.
2. **Single responsibility.** The inline ternary is a minimal, surgical change
   to exactly one expression; Bob's guard is a separate execution path that
   could drift from the main path over time.

Bob's fix is **functionally correct and sufficient** to close the incident, and
the output it produces matches upstream's for all inputs tested.  Upgrading the
vendored library to `≥ 4.4.0` (which ships the upstream fix) is the preferred
long-term resolution.
