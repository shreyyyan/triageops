# Root-Cause Analysis — INC-2026-1044

| Field            | Value                                      |
|------------------|--------------------------------------------|
| Alert ID         | INC-2026-1044                              |
| Severity         | Critical                                   |
| Service          | victim-service                             |
| Endpoint         | POST /orders                               |
| Error signature  | PaymentError → HTTP 502                    |
| First failure    | 2026-09-25T16:41:02Z                       |
| Alert fired      | 2026-09-25T16:47:33Z                       |
| Failed attempts  | ~340                                       |

---

## 1. Timeline

| Time (UTC)        | Event                                                                 |
|-------------------|-----------------------------------------------------------------------|
| 16:38:02          | Normal order processing (`mode=live`) — service healthy               |
| 16:39:55          | CI deploy: `victim-service:1.14.0` pushed to staging                  |
| **16:40:03**      | **`PAYMENTS_MODE` env var changed: `live` → `sandbox` (reason: "staging QA")** |
| 16:40:11          | Service restarted (pid=4412) — picks up new env var                   |
| **16:41:02**      | **First `PaymentError` — every subsequent order fails with HTTP 502** |
| 16:47:33          | Alertmanager fires INC-2026-1044 (5xx spike on POST /orders)          |

---

## 2. Code Path

### Entry point — `POST /orders`
**File:** [`victim-service/app.py`](../../victim-service/app.py), line 84

```
create_order(order)          # line 84
  → charge_payment(total)    # line 101
      → raises PaymentError  # line 80   ← root cause
  → except PaymentError      # line 102
      → raise HTTPException(502)  # line 104
```

### The defective function

**File:** [`victim-service/app.py`](../../victim-service/app.py), lines 74–81

```python
def charge_payment(amount: float) -> str:
    mode = os.environ.get("PAYMENTS_MODE", "live")   # line 75
    logger.info("charging payment amount=%.2f mode=%s", amount, mode)  # line 76
    if mode == "sandbox":
        # BUG 3: raises instead of returning a simulated transaction id
        raise PaymentError("sandbox gateway declined the charge")       # line 80
    return "txn_%d" % int(round(amount * 100))                         # line 81
```

When `PAYMENTS_MODE` is `"sandbox"`, the branch at **line 77** is taken unconditionally and **line 80 always raises `PaymentError`**. There is no happy-path return for sandbox mode; the simulated success path (`"txn_..."`) is only reached when `mode == "live"`.

### Exception propagation — `create_order`

**File:** [`victim-service/app.py`](../../victim-service/app.py), lines 100–104

```python
try:
    txn_id = charge_payment(total)       # line 101 — raises in sandbox mode
except PaymentError as exc:
    logger.error("payment failed: %s", exc)  # line 103
    raise HTTPException(status_code=502, detail="payment gateway error")  # line 104
```

`PaymentError` is caught and immediately converted to an HTTP 502. No retry, no fallback. **Every** `POST /orders` request in sandbox mode goes through this path and returns 502.

---

## 3. Root Cause

The root cause is an **incorrect implementation of sandbox-mode payment simulation** in [`charge_payment()`](../../victim-service/app.py#74).

The intent documented in the code comment (line 79) is that sandbox mode should *simulate* a successful charge — returning a test transaction ID — so that staging/QA environments can exercise the full order flow without hitting a real payment gateway. Instead, the code raises `PaymentError` unconditionally whenever `PAYMENTS_MODE == "sandbox"`, making it impossible for any order to complete in that environment.

This is **not** a misconfiguration of the environment. Setting `PAYMENTS_MODE=sandbox` is the correct and expected action for staging QA (as evidenced by the deploy log at 16:40:03). The defect is solely in the application code: the sandbox branch was written as a `raise` statement instead of a `return "test_..."` statement.

The deploy at 16:39:55 changed the artifact version to `1.14.0` *and* the env var was simultaneously flipped to `sandbox`. The service was healthy on `live` mode before the deploy. The instant the restarted process (pid=4412) began serving requests with the new env var, every payment call hit the buggy branch and every order failed.

---

## 4. Contributing Factors

| Factor | Detail |
|--------|--------|
| **No sandbox smoke-test** | The deploy pipeline did not run a canary or post-deploy smoke test against `POST /orders` after switching `PAYMENTS_MODE`. A single test request would have surfaced the 502 immediately. |
| **Test gap (pre-deploy)** | `test_sandbox_mode_simulates_payment` in [`tests/test_orders.py`](../../victim-service/tests/test_orders.py#107) explicitly covers this scenario and expects HTTP 200 + a `test_` prefixed txn ID. This test **fails** against the seeded code. Had CI run (or enforced) this test before the deploy, the bug would have been blocked from reaching staging. |
| **Env var change coupled to deploy** | The `PAYMENTS_MODE` flip happened in the same deploy event as the artifact upgrade, making it harder to isolate which change introduced the failure. |

---

## 5. Affected Test

**File:** [`victim-service/tests/test_orders.py`](../../victim-service/tests/test_orders.py), lines 107–112

```python
def test_sandbox_mode_simulates_payment(monkeypatch):
    monkeypatch.setenv("PAYMENTS_MODE", "sandbox")
    r = client.post("/orders", json=_order_payload())
    assert r.status_code == 200, ...              # FAILS: actual status is 502
    assert body["txn_id"].startswith("test_"), ... # FAILS: no txn_id in 502 response
```

This test documents the **correct** intended behaviour: sandbox mode must return HTTP 200 with a `test_`-prefixed transaction ID. On the seeded (buggy) code both assertions fail.

---

## 6. Scope and Impact

- **All** `POST /orders` requests in any environment where `PAYMENTS_MODE=sandbox` fail with HTTP 502 — 100% error rate from restart until env var is reverted or code is fixed.
- `GET /orders/{id}` and `GET /health` are unaffected.
- No data corruption: orders are never persisted (the `ORDERS` dict write at line 118 is after the payment call), so there are no orphaned records.
- Impact is fully reversible by reverting `PAYMENTS_MODE` to `live`, though this disables QA sandbox testing.

---

*Analysis only — no code changes made.*
