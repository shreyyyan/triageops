# Root Cause Analysis — INC-2026-1042

**Alert ID:** INC-2026-1042  
**Service:** victim-service  
**Endpoint:** POST /orders  
**Error signature:** `KeyError: None`  
**Severity:** Critical  
**First observed:** 2026-09-25T14:01:20Z  
**Alert fired:** 2026-09-25T14:02:12Z  
**Customer impact:** ~18 % of order attempts returning HTTP 500 since 13:58Z

---

## 1. Faulty Code Path

The complete call chain from the HTTP handler to the exception, confirmed against the traceback frames in `incidents/incident_001.json`:

```
POST /orders
  └─ victim-service/app.py:85   create_order(order: OrderIn)
       └─ victim-service/app.py:97   tax = apply_tax(subtotal, order.region)
            └─ victim-service/app.py:60   rate = TAX_RATES[region]
                 └─ KeyError: None          ← exception raised here
```

| Step | File | Line | Statement |
|------|------|------|-----------|
| 1 — HTTP handler entry | `victim-service/app.py` | 85 | `def create_order(order: OrderIn):` |
| 2 — quantity aggregation | `victim-service/app.py` | 87 | `total_quantity = sum(i.quantity for i in order.items)` |
| 3 — per-line subtotals | `victim-service/app.py` | 89 | `lines = [line_subtotal(i) for i in order.items]` |
| 4 — bulk discount (line) | `victim-service/app.py` | 91 | `lines = [apply_bulk_discount(lt, total_quantity) for lt in lines]` |
| 5 — order subtotal | `victim-service/app.py` | 92 | `subtotal = round(sum(lines), 2)` |
| 6 — bulk discount (order) | `victim-service/app.py` | 95 | `subtotal = apply_bulk_discount(subtotal, total_quantity)` |
| 7 — **tax call** ← crash | `victim-service/app.py` | 97 | `tax = apply_tax(subtotal, order.region)` |
| 8 — **dict lookup** ← exception | `victim-service/app.py` | 60 | `rate = TAX_RATES[region]` |

The traceback in `incident_001.json` pins frames exactly at lines 97 and 60, matching steps 7 and 8 above.

---

## 2. Why the Exception Happens

### The `region` value is `None`

`OrderIn.region` is declared as `Optional[str] = None`:

```python
# victim-service/app.py:50
region: Optional[str] = None
```

When a client omits `region` from the JSON body (or explicitly sends `"region": null`), Pydantic sets `order.region = None`. This value is passed unchanged to `apply_tax`:

```python
# victim-service/app.py:97
tax = apply_tax(subtotal, order.region)   # order.region is None
```

Inside `apply_tax`, the lookup uses `region` as a dictionary key against `TAX_RATES`:

```python
# victim-service/app.py:33
TAX_RATES = {"NP": 0.13, "US": 0.07, "IN": 0.18}

# victim-service/app.py:60
rate = TAX_RATES[region]   # region=None → KeyError: None
```

`None` is not a key in `TAX_RATES`, so Python raises `KeyError: None`. This exception is **not caught** anywhere in `create_order`, so FastAPI converts it to an unhandled HTTP 500 response.

The same crash occurs for any **unknown region string** (e.g. `"XX"`) because the dict lookup has no default or fallback — it is a bare subscript, not `.get()`.

---

## 3. Blast Radius

### Requests that trigger the crash

Any `POST /orders` request where:

1. `region` is **omitted** from the body entirely — Pydantic defaults it to `None`.
2. `region` is explicitly set to `null` in the JSON body.
3. `region` contains a **string not present in `TAX_RATES`** (e.g. `"XX"`, `"EU"`, `"CA"`).

All three cases result in `apply_tax` receiving a key not present in `TAX_RATES`, raising `KeyError` and returning HTTP 500.

The incident logs show requests from a single source IP (`10.4.2.18`) repeatedly hitting this path, with four confirmed HTTP 500 responses between 14:01 and 14:02.

### Requests that are **not** affected

`POST /orders` requests that include a `region` value that is one of the three known keys (`"NP"`, `"US"`, `"IN"`) complete successfully. The successful orders visible in the logs (ids 881–888) all carry a valid region. `GET /orders/{id}` and `GET /health` are completely unaffected; they do not call `apply_tax`.

---

## 4. Minimal Correct Behaviour

`apply_tax` should fall back to a tax rate of `0.0` whenever `region` is `None` or not present in `TAX_RATES`. The fix is a single-line change replacing the bare dict subscript with a `.get()` call:

```python
# Current (buggy) — victim-service/app.py:60
rate = TAX_RATES[region]

# Correct
rate = TAX_RATES.get(region, 0.0)
```

With this change:

- A missing or `null` region → 0 % tax, HTTP 200, order succeeds.
- An unknown region string → 0 % tax, HTTP 200, order succeeds.
- A known region (`"NP"`, `"US"`, `"IN"`) → correct tax rate, behaviour unchanged.

This matches the expected behaviour documented in the code comment on line 59 (`# Correct behaviour: fall back to a 0.0 rate.`) and in the test cases `test_missing_region_defaults_tax_to_zero` and `test_unknown_region_defaults_tax_to_zero` in `victim-service/tests/test_orders.py`.

No schema changes, no changes to `OrderIn`, and no additional validation are required. The field should remain `Optional[str]`; the fix belongs entirely inside `apply_tax`.
