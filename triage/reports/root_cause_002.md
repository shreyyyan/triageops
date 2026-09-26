# Root Cause Analysis — INC-2026-1043

**Alert ID:** INC-2026-1043  
**Incident name:** BULK_DISCOUNT_ANOMALY  
**Service:** victim-service  
**Endpoint:** POST /orders  
**Symptom:** Bulk discount applied twice — once per line item, once on the order subtotal — so customers are undercharged (revenue leak).  
**Severity:** Silent / Financial — no crash, no HTTP error; the wrong total is returned and charged.  
**Bug label in source:** BUG 2 (seeded)

---

## 1. Faulty Code Path

The complete call chain inside `create_order` that produces the double-discount:

```
POST /orders
  └─ victim-service/app.py:85   create_order(order: OrderIn)
       ├─ victim-service/app.py:89   lines = [line_subtotal(i) for i in order.items]
       ├─ victim-service/app.py:91   lines = [apply_bulk_discount(lt, total_quantity) for lt in lines]
       │    └─ victim-service/app.py:68   apply_bulk_discount(amount, total_quantity)
       │         └─ discount applied FIRST TIME — each line is multiplied by (1 - 0.10)
       ├─ victim-service/app.py:92   subtotal = round(sum(lines), 2)
       └─ victim-service/app.py:95   subtotal = apply_bulk_discount(subtotal, total_quantity)
            └─ victim-service/app.py:68   apply_bulk_discount(amount, total_quantity)
                 └─ discount applied SECOND TIME — the already-discounted subtotal is
                    multiplied by (1 - 0.10) again
```

| Step | File | Line | Statement | Effect |
|------|------|------|-----------|--------|
| 1 — compute line totals | `victim-service/app.py` | 89 | `lines = [line_subtotal(i) for i in order.items]` | Raw `qty × unit_price` for each item |
| 2 — **first discount** | `victim-service/app.py` | 91 | `lines = [apply_bulk_discount(lt, total_quantity) for lt in lines]` | Each line multiplied by `0.90` when `total_quantity > 10` |
| 3 — sum lines | `victim-service/app.py` | 92 | `subtotal = round(sum(lines), 2)` | Subtotal is already discounted |
| 4 — **second discount** | `victim-service/app.py` | 95 | `subtotal = apply_bulk_discount(subtotal, total_quantity)` | Already-discounted subtotal multiplied by `0.90` again |
| 5 — tax on wrong base | `victim-service/app.py` | 97 | `tax = apply_tax(subtotal, order.region)` | Tax is calculated on the doubly-discounted amount |
| 6 — wrong total returned | `victim-service/app.py` | 98 | `total = round(subtotal + tax, 2)` | Charge sent to payment gateway is too low |

---

## 2. Root Cause

### The helper `apply_bulk_discount` is called twice on the same value

[`apply_bulk_discount`](triageops/victim-service/app.py:68) is a pure, stateless function that takes an `amount` and a `total_quantity` and returns `amount * 0.90` whenever `total_quantity > BULK_THRESHOLD` (10):

```python
# victim-service/app.py:68-71
def apply_bulk_discount(amount: float, total_quantity: int) -> float:
    if total_quantity > BULK_THRESHOLD:
        return round(amount * (1 - BULK_DISCOUNT_RATE), 2)
    return amount
```

There is nothing wrong with the function itself. The bug is in [`create_order`](triageops/victim-service/app.py:84), where it is called **twice** in sequence:

**Call 1 — line-item level (line 91):**

```python
# victim-service/app.py:91
lines = [apply_bulk_discount(lt, total_quantity) for lt in lines]
```

This iterates over every raw line total and applies `× 0.90`. After this list-comprehension, each element already reflects the 10 % reduction.

**Call 2 — order-subtotal level (line 95):**

```python
# victim-service/app.py:95
subtotal = apply_bulk_discount(subtotal, total_quantity)
```

`subtotal` at this point is `sum(lines)`, where `lines` already holds the discounted values from Call 1. Calling `apply_bulk_discount` again on this value compounds the reduction: the effective discount becomes `1 − 0.90² = 19 %` instead of the intended `10 %`.

### Numerical walk-through

Order: 12 units of `WIDGET-9` at `$10.00` each.

| Step | Value | Calculation |
|------|-------|-------------|
| Raw line total | `$120.00` | `12 × $10.00` |
| After **1st** bulk discount (line 91) | `$108.00` | `120.00 × 0.90` |
| Subtotal (sum of lines) | `$108.00` | (single item) |
| After **2nd** bulk discount (line 95) | `$97.20` | `108.00 × 0.90` |
| **Correct** subtotal (discount once) | `$108.00` | `120.00 × 0.90` |
| **Revenue lost per order** | `$10.80` | `108.00 − 97.20` |

This matches exactly what the failing test asserts:

```python
# victim-service/tests/test_orders.py:91-99
def test_bulk_discount_applied_exactly_once():
    payload = _order_payload(
        items=[{"sku": "WIDGET-9", "quantity": 12, "unit_price": 10.0}]
    )
    r = client.post("/orders", json=payload)
    body = r.json()
    # 12 x 10.00 = 120.00, single 10% bulk discount -> 108.00
    assert body["subtotal"] == 108.0, f"double discount suspected: {body['subtotal']}"
    # Seeded code returns 97.20 — assertion fails.
```

---

## 3. Why the Bug Was Introduced

The code comments in `app.py` (lines 90–94) make the intent transparent:

```python
# BUG 2: bulk discount applied at line level ...
lines = [apply_bulk_discount(lt, total_quantity) for lt in lines]
subtotal = round(sum(lines), 2)
# ... and then applied a SECOND time on the order subtotal. Revenue leak.
# Correct behaviour: apply the bulk discount exactly once.
subtotal = apply_bulk_discount(subtotal, total_quantity)
```

The likely origin is a refactoring error. One approach to bulk discounts is to apply it per-line (Call 1 pattern). A different, equally valid approach is to apply it once to the whole order subtotal (Call 2 pattern). Both are correct in isolation. The bug is that **both were left active** after the design decision should have settled on one. Neither call was removed when the other was added.

---

## 4. Blast Radius

### Conditions that trigger the double-discount

Any `POST /orders` request where `sum(item.quantity for item in order.items) > 10`.  
There is no other condition; no special discount code or region is needed.

### Conditions that are **not** affected

- Orders with total quantity ≤ 10 — `apply_bulk_discount` returns `amount` unchanged on both calls, so there is no compounding.
- `GET /orders/{id}` and `GET /health` — neither calls `apply_bulk_discount`.

### Financial impact

With a 10 % bulk discount rate, the effective over-discount is:

```
effective_discount = 1 − (1 − 0.10)² = 1 − 0.81 = 19 %
```

For every qualifying order, the service under-collects **9 percentage points** of the order value (i.e. `(0.10² / (1 − 0.10)) ≈ 1.11 %` expressed differently, but practically: the customer keeps `$10.80` per `$120.00` order that should not be discounted). Tax is also calculated on the wrong base, amplifying the shortfall slightly.

---

## 5. Minimal Correct Behaviour

The bulk discount must be applied **exactly once**. The fix is to remove one of the two calls. The subtotal-level call (line 95) should be removed, retaining the per-line application; or the per-line calls (line 91) should be removed, retaining the order-level application. Either produces the correct single-application result.

Keeping the per-line call (line 91) and removing the redundant subtotal call (line 95):

```python
# Current (buggy) — victim-service/app.py:89-95
lines = [line_subtotal(i) for i in order.items]
lines = [apply_bulk_discount(lt, total_quantity) for lt in lines]   # first discount
subtotal = round(sum(lines), 2)
subtotal = apply_bulk_discount(subtotal, total_quantity)              # REMOVE THIS LINE

# Correct
lines = [line_subtotal(i) for i in order.items]
lines = [apply_bulk_discount(lt, total_quantity) for lt in lines]   # discount applied once
subtotal = round(sum(lines), 2)
```

With this change:
- 12 × $10.00 order → subtotal `$108.00`, matching the test assertion.
- Orders with ≤ 10 units → no discount applied; behaviour unchanged.
- Tax is calculated on the correct base; total charged is accurate.

The boundary-condition test (`test_bulk_threshold_boundary_no_discount`) confirms that exactly 10 units must not trigger the discount (`total_quantity > BULK_THRESHOLD`, strictly greater-than), and this remains correct either way.

---

## 6. Affected Files and Lines Summary

| File | Lines | Role in Bug |
|------|-------|-------------|
| `victim-service/app.py` | 68–71 | `apply_bulk_discount` — correct helper, called too many times |
| `victim-service/app.py` | 91 | **First** (intended) discount call — per-line |
| `victim-service/app.py` | 95 | **Second** (erroneous) discount call — on already-discounted subtotal |
| `victim-service/tests/test_orders.py` | 91–99 | Failing regression test that catches this exact condition |
