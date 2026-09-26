# Incident Report — INC-2026-1044

| Field            | Value                                         |
|------------------|-----------------------------------------------|
| Alert ID         | INC-2026-1044                                 |
| Severity         | **Critical**                                  |
| Service          | victim-service                                |
| Endpoint         | `POST /orders`                                |
| Error signature  | `PaymentError` → HTTP 502 (100% failure rate) |
| Report status    | Fix proposed — **NOT applied**                |

---

## 1. Incident Summary

At **2026-09-25 16:41:02 UTC**, every request to `POST /orders` on `victim-service` began
returning HTTP 502. Approximately 340 order attempts failed before the alert fired.

A CI deploy of `victim-service:1.14.0` was pushed to staging at 16:39:55 UTC. Eight seconds
later (16:40:03 UTC), the environment variable `PAYMENTS_MODE` was changed from `live` to
`sandbox` as part of the staging QA setup. The service restarted at 16:40:11 UTC (pid=4412),
picked up the new env var, and began failing immediately. Alertmanager fired alert
**INC-2026-1044** at 16:47:33 UTC on a 5xx spike threshold breach for `POST /orders`.

| Time (UTC)   | Event                                                                      |
|--------------|----------------------------------------------------------------------------|
| 16:38:02     | Normal order processing (`mode=live`) — service healthy                    |
| 16:39:55     | CI deploy: `victim-service:1.14.0` pushed to staging                       |
| **16:40:03** | **`PAYMENTS_MODE` changed: `live` → `sandbox` (reason: "staging QA")**     |
| 16:40:11     | Service restarted (pid=4412) — new env var active                          |
| **16:41:02** | **First `PaymentError` — every subsequent order fails with HTTP 502**      |
| 16:47:33     | Alertmanager fires INC-2026-1044 (5xx spike on `POST /orders`)             |

`GET /orders/{id}` and `GET /health` were unaffected throughout. No data corruption occurred;
orders are never persisted until after a successful payment call, so there are no orphaned
records.

---

## 2. Key Evidence

### Log signature
Every failed request produced the same log line immediately before returning 502:

```
ERROR  payment failed: sandbox gateway declined the charge
```

This pinpointed `charge_payment()` as the failure site and `PAYMENTS_MODE=sandbox` as the
trigger.

### Defective code — `victim-service/app.py`, lines 74–81

```python
def charge_payment(amount: float) -> str:
    mode = os.environ.get("PAYMENTS_MODE", "live")        # line 75
    logger.info("charging payment amount=%.2f mode=%s", amount, mode)
    if mode == "sandbox":
        # BUG: raises instead of returning a simulated transaction ID
        raise PaymentError("sandbox gateway declined the charge")  # line 80
    return "txn_%d" % int(round(amount * 100))            # line 81 — never reached in sandbox
```

When `PAYMENTS_MODE == "sandbox"` the `raise` on line 80 executes unconditionally. There is no
return path for sandbox mode; `charge_payment()` never produces a transaction ID.

### Exception propagation — `create_order()`, lines 100–104

```python
try:
    txn_id = charge_payment(total)           # raises in sandbox mode
except PaymentError as exc:
    logger.error("payment failed: %s", exc)
    raise HTTPException(status_code=502, detail="payment gateway error")
```

`PaymentError` is caught and converted directly to HTTP 502 with no retry or fallback.

### Failing test — `victim-service/tests/test_orders.py`, lines 107–112

```python
def test_sandbox_mode_simulates_payment(monkeypatch):
    monkeypatch.setenv("PAYMENTS_MODE", "sandbox")
    r = client.post("/orders", json=_order_payload())
    assert r.status_code == 200   # FAILS: actual status is 502
    assert body["txn_id"].startswith("test_")  # FAILS: no txn_id in 502 response
```

This test documents the correct intended behaviour and **currently fails** against the live
codebase.

---

## 3. Root Cause

The root cause is an **incorrect implementation of sandbox-mode payment simulation** in
`charge_payment()` (`victim-service/app.py`, line 80).

The design intent — evidenced by the surrounding comment and the existing test — is that
`PAYMENTS_MODE=sandbox` should *simulate* a successful charge by returning a test transaction
ID, allowing QA environments to exercise the full order flow without a real payment gateway.
Instead, the sandbox branch unconditionally raises `PaymentError`, making it impossible for
any order to complete when the env var is set to `sandbox`.

This is **not** a misconfiguration. Setting `PAYMENTS_MODE=sandbox` for staging QA is correct
and expected. The defect is solely in the application: a `raise` statement was written where a
`return "test_..."` statement was intended.

---

## 4. Proposed Fix

**Diff file:** [`triage/fixes/fix_003.diff`](../fixes/fix_003.diff)
**Status: NOT applied — the fix is proposed only.**

The fix replaces the single defective statement on line 80 of `victim-service/app.py`:

| | Code |
|-|------|
| **Before** | `raise PaymentError("sandbox gateway declined the charge")` |
| **After**  | `return "test_sandbox_txn"` |

The two comment lines (78–79) describing the bug are also removed, as they exist solely to
document the defect and would be misleading once the fix is in place. No other lines, functions,
endpoints, imports, or dependencies are touched.

**Why it is safe:**
- The `if mode == "sandbox":` guard is unchanged; live-mode behaviour is unaffected.
- `"test_sandbox_txn"` satisfies the existing assertion `txn_id.startswith("test_")`.
- `charge_payment()` has exactly one call site (`create_order()`, line 101); blast radius is
  minimal.
- `PaymentError` is not removed; real gateway failures can still raise it as intended.

---

## 5. Verification Status

| Test | Current status | Expected after fix is applied |
|------|---------------|-------------------------------|
| `test_sandbox_mode_simulates_payment` | **FAILING** — 502, no `txn_id` | PASS — 200, `txn_id == "test_sandbox_txn"` |
| `test_create_order_happy_path` | PASSING | remains PASSING |
| `test_get_order_roundtrip` | PASSING | remains PASSING |
| `test_bulk_threshold_boundary_no_discount` | PASSING | remains PASSING |
| `test_bulk_discount_applied_exactly_once` | FAILING (unrelated bug, BUG 2) | unchanged — out of scope |

**The fix has not been applied.** `test_sandbox_mode_simulates_payment` still fails in the
live test suite. Incident INC-2026-1044 remains open pending code review, merge, and a
successful post-deploy smoke test confirming `POST /orders` returns HTTP 200 with a
`test_`-prefixed transaction ID in sandbox mode.

---

*No source code was modified in the production of this report.*
