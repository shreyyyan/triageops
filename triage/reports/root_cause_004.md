# Root Cause Analysis — INC-2026-1045
**Vendored library:** humanize 4.3.0  
**Affected function:** `metric()` in `triage/realworld/humanize/number.py`  
**Trigger input:** `0` (integer zero)

---

## 1. Reproduced Traceback

```
vendored module: S:\HACKERTHONE\triageops\triage\realworld\humanize\number.py
Traceback (most recent call last):
  File "S:\HACKERTHONE\triageops\triage\realworld\repro_metric_zero.py", line 40, in <module>
    print(number.metric(0))
          ~~~~~~~~~~~~~^^^
  File "S:\HACKERTHONE\triageops\triage\realworld\humanize\number.py", line 511, in metric
    exponent = int(math.floor(math.log10(abs(value))))
                              ~~~~~~~~~~^^^^^^^^^^^^
ValueError: expected a positive input
```

Reproduced by running from the repo root:

```
python triageops/triage/realworld/repro_metric_zero.py
```

---

## 2. Faulty Code Path, Step by Step

### Step 1 — Caller (`repro_metric_zero.py:40`)

```python
print(number.metric(0))
```

`value = 0` is passed directly to `metric()` with no pre-validation.

---

### Step 2 — `metric()` entry point (`number.py:511`)

```python
def metric(value: float, unit: str = "", precision: int = 3) -> str:
    exponent = int(math.floor(math.log10(abs(value))))   # line 511
```

This is the **first and only statement** in the function body.  
There is no guard or early-return for zero before this line executes.

---

### Step 3 — `abs(value)` (`number.py:511`, innermost call)

```python
abs(0)  # → 0
```

`abs()` succeeds and returns `0`.

---

### Step 4 — `math.log10(0)` (`number.py:511`)

```python
math.log10(0)   # → ValueError: expected a positive input
```

`math.log10` is defined only for **strictly positive** real numbers (its domain is
`(0, +∞)`).  
Passing `0` is mathematically undefined: log₁₀(0) = −∞, which cannot be
represented as a finite float and is therefore rejected by CPython's `math`
module with the error `ValueError: expected a positive input`.

The exception propagates immediately; lines 513–529 are **never reached**.

---

## 3. Root Cause

On `number.py` line 511, the very first statement of `metric()` computes
`math.log10(abs(value))` without any guard for the case `value == 0`.
`math.log10` requires a strictly positive argument; `abs(0)` is `0`, so the
call raises `ValueError: expected a positive input`.
The entire function body beyond that single line is unreachable for this input:
there is no zero-check, no early return, and no `try/except` anywhere in
`metric()`.  The crash is therefore deterministic and immediate whenever
`value` is `0` (or any value whose absolute value is `0`).

---

## 4. Why Zero Is a Legitimate Input

In the billing and invoicing domain, a line-item amount of `0` is a normal,
expected value.  It arises in at least two common scenarios:

1. **Credit / refund line items** — when a full credit is applied against a
   charge, the net amount on that line becomes exactly `0`.  The UI must be
   able to render `"0"` or `"0 "` (with a blank SI prefix) without crashing.

2. **Placeholder / template rows** — draft invoices often contain skeleton rows
   initialised to `0` before the operator fills in the actual amounts.

In both cases, passing `0` to `metric()` for display is entirely valid
business logic.  The function's contract (return a human-readable metric
string for *any* float) implies it must handle zero; the 4.3.0 implementation
silently assumes `value > 0` without documenting or enforcing that constraint.
