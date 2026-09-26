# Incident Report — INC-2026-1043

**Alert ID:** INC-2026-1043  
**Incident name:** BULK_DISCOUNT_ANOMALY  
**Service:** victim-service  
**Endpoint:** POST /orders  
**Severity:** High (Silent / Financial — no HTTP errors; incorrect totals returned)  
**Status:** Fix proposed, NOT yet applied  
**Report date:** 2026-09-25  

---

## 1. Summary

A silent financial defect in the `POST /orders` endpoint caused every bulk order
(total item quantity > 10) to be undercharged by approximately 9 percentage
points. No HTTP errors were raised and no customer-visible failures occurred;
the service accepted orders and returned HTTP 200 with a subtotals that were too
low.

The root cause is a double application of the 10 % bulk discount in
`create_order`: the discount function `apply_bulk_discount` is called once
per-line (line 91) and then called a second time on the already-discounted
subtotal (line 95), compounding the reduction to an effective 19 % instead of
the intended 10 %.

The defect was undetected at the HTTP layer and was surfaced only by the
`finance-recon` nightly reconciliation job, which flagged 6 anomalous orders
within a 7-day window and fired the alert at 09:15:00 Z on 2026-09-25.
Estimated revenue loss: **$1,240 over 7 days** ($68.04 confirmed in the
scanned window).

**The proposed fix (`triage/fixes/fix_002.diff`) has NOT been applied.** The
related regression test (`test_bulk_discount_applied_exactly_once`) is currently
**failing** in the live test suite.

---

## 2. Timeline

| Time (UTC) | Event |
|---|---|
| 2026-09-25 08:41:02 | Order id=812 processed — subtotal `$108.00` (correct; quantity ≤ 10). |
| 2026-09-25 08:42:55 | Order id=814 processed — subtotal `$97.20` (wrong; qty=12, expected `$108.00`). |
| 2026-09-25 08:44:10 | Order id=815 processed — subtotal `$174.96` (wrong; qty=24, expected `$194.40`). |
| 2026-09-25 09:00:00 | `finance-recon` nightly job starts; 7-day window, 312 orders scanned. |
| 2026-09-25 09:11:47 | First `BULK_DISCOUNT_ANOMALY` warnings raised (orders 814, 815, 817, 819, 821, 823). |
| 2026-09-25 09:11:49 | `finance-recon` confirms pattern: every order with `total_quantity > 10` undercharged by exactly one extra 10 % discount. |
| 2026-09-25 09:12:03 | `finance-recon` reports 6 anomalous orders; total leakage `$68.04`; 7-day projection `~$1,240`. |
| 2026-09-25 09:15:00 | Alertmanager fires **CRITICAL** alert INC-2026-1043 (`BULK_DISCOUNT_ANOMALY`). |
| *(pending)* | Fix (`fix_002.diff`) not yet deployed. Service continues to undercharge bulk orders. |

---

## 3. Key Evidence

### Log findings — `incidents/incident_002_logs.txt`

The reconciliation logs expose the pattern directly:

| Order | Qty | Unit price | Expected subtotal | Actual subtotal | Leakage |
|-------|-----|------------|-------------------|-----------------|---------|
| 814 | 12 | $10.00 | $108.00 | $97.20 | $10.80 |
| 815 | 24 | $9.00 | $194.40 | $174.96 | $19.44 |
| 817 | 12 | $10.00 | $108.00 | $97.20 | $10.80 |
| 819 | 24 | $9.00 | $194.40 | $174.96 | $19.44 |
| 821 | 12 | $10.00 | $108.00 | $97.20 | $10.80 |
| 823 | 24 | $9.00 | $194.40 | $174.96 | $19.44 |

Every affected order has `total_quantity > 10`. All orders with `total_quantity ≤ 10`
(e.g. ids 812, 813, 816, 818, 820, 822) show correct totals. The shortfall is
exactly `actual × (0.10 / 0.90) ≈ 11.1 %` of the actual charged amount —
consistent with a second independent 10 % reduction applied to an already-discounted
value.

### Alert data — `incidents/incident_002.json`

```json
{
  "alert_id": "INC-2026-1043",
  "error_signature": "BULK_DISCOUNT_ANOMALY",
  "severity": "high",
  "timestamp": "2026-09-25T09:15:00Z",
  "customer_impact": "No customer-facing errors, but bulk orders are undercharged by ~10%. Estimated revenue impact $1,240 over the last 7 days.",
  "traceback": null
}
```

No traceback is available because the service does not error; it silently returns
a lower total.

### Code findings — `victim-service/app.py`

The `apply_bulk_discount` helper (lines 68–71) is correct in isolation:

```python
# app.py:68-71
def apply_bulk_discount(amount: float, total_quantity: int) -> float:
    if total_quantity > BULK_THRESHOLD:          # BULK_THRESHOLD = 10
        return round(amount * (1 - BULK_DISCOUNT_RATE), 2)   # × 0.90
    return amount
```

The bug is in `create_order` (lines 89–95), where it is called **twice in
sequence** on the same value:

```python
# app.py:89-95  (current, buggy)
lines = [line_subtotal(i) for i in order.items]
# BUG 2: bulk discount applied at line level ...
lines = [apply_bulk_discount(lt, total_quantity) for lt in lines]   # ← 1st call (× 0.90)
subtotal = round(sum(lines), 2)
# ... and then applied a SECOND time on the order subtotal. Revenue leak.
# Correct behaviour: apply the bulk discount exactly once.
subtotal = apply_bulk_discount(subtotal, total_quantity)             # ← 2nd call (× 0.90 again)
```

After the first call `lines` already holds discounted values; the second call
multiplies that already-discounted subtotal by 0.90 once more.

---

## 4. Root Cause

The bulk discount function `apply_bulk_discount` is invoked twice within a
single order-pricing flow:

1. **Line 91** — applied per line item (correct, intended).  
2. **Line 95** — applied again to the summed subtotal (erroneous duplicate).

Because `sum(x_i × 0.90) = 0.90 × sum(x_i)`, either call alone produces the
correct 10 % reduction. With both active, the effective discount compounds to
`1 − 0.90² = 19 %` — an over-discount of 9 percentage points on every qualifying
order. Tax is then calculated on the doubly-discounted subtotal, further
amplifying the revenue shortfall.

The defect originates from a refactoring error: two equivalent but mutually
exclusive approaches to applying the bulk discount (per-line vs. per-order) were
both left active. The in-code comment on lines 93–94 explicitly marks the second
call as a bug (`BUG 2` label).

Full root-cause analysis: [`triage/reports/root_cause_002.md`](root_cause_002.md)

---

## 5. Proposed Fix

**Diff file:** `triage/fixes/fix_002.diff`  
**File to be changed:** `victim-service/app.py`  
> ⚠️ **This fix has NOT been applied. The source code is unchanged.**

The fix removes three lines from `create_order`: the two explanatory bug-marker
comments and the single executable duplicate call on line 95.

```diff
--- a/victim-service/app.py
+++ b/victim-service/app.py
@@ -89,9 +89,6 @@ def create_order(order: OrderIn):
     lines = [line_subtotal(i) for i in order.items]
-    # BUG 2: bulk discount applied at line level ...
     lines = [apply_bulk_discount(lt, total_quantity) for lt in lines]
     subtotal = round(sum(lines), 2)
-    # ... and then applied a SECOND time on the order subtotal. Revenue leak.
-    # Correct behaviour: apply the bulk discount exactly once.
-    subtotal = apply_bulk_discount(subtotal, total_quantity)

     tax = apply_tax(subtotal, order.region)
```

The sole functional change is the deletion of the `apply_bulk_discount` call at
line 95. No new logic is added. `apply_bulk_discount` itself is untouched. Orders
with `total_quantity ≤ 10` are unaffected (both calls were already no-ops for
them).

---

## 6. Verification Status

**Current state: fix NOT applied — test still failing.**

| Test | File | Pre-fix status | Expected post-fix |
|------|------|----------------|-------------------|
| `test_bulk_discount_applied_exactly_once` | `victim-service/tests/test_orders.py:91` | **FAILING** — code returns `97.20`; asserts `108.00` | PASS |
| `test_bulk_threshold_boundary_no_discount` | `victim-service/tests/test_orders.py:115` | PASSING | remains PASS |
| `test_create_order_happy_path` | `victim-service/tests/test_orders.py:42` | PASSING | remains PASS |
| `test_get_order_roundtrip` | `victim-service/tests/test_orders.py:53` | PASSING | remains PASS |

`test_bulk_discount_applied_exactly_once` **remains red** until `fix_002.diff`
is applied and deployed. All other tests are currently passing and are not
expected to regress once the fix is applied.
