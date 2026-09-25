# Incident Report — INC-2026-1042

**Service:** victim-service  
**Endpoint:** POST /orders  
**Severity:** Critical  
**Status:** Resolved  
**Report date:** 2026-09-25  

---

## Summary

A `KeyError: None` exception in `apply_tax()` caused checkout failures for any
order submitted without a `region` field. Approximately 18 % of order attempts
returned HTTP 500 from roughly 13:58 Z until the fix was applied. The defect
was a single bare dictionary subscript (`TAX_RATES[region]`) that raised
`KeyError` whenever `region` was `None` or an unrecognised string. A one-line
patch replaced the subscript with `TAX_RATES.get(region, 0.0)`. Post-fix
regression tests confirmed the regression count dropped from 4 failing to 2
failing; the 2 remaining failures are attributed to separate incidents (002 and
003) and are out of scope for this report.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 2026-09-25 13:58:02 | First successful orders processed (ids 881–884). |
| 2026-09-25 14:00:40 | Warning: elevated 5xx rate on POST /orders (2 in last 60 s). |
| 2026-09-25 14:01:20 | First confirmed `KeyError: None` traceback logged; HTTP 500 returned. |
| 2026-09-25 14:01:55 | Second `KeyError: None`; second HTTP 500. |
| 2026-09-25 14:02:02 | Warning: 5xx rate — 5 errors in last 300 s. |
| 2026-09-25 14:02:11 | Third `KeyError: None`; HTTP 500 — becomes the alert trigger timestamp. |
| 2026-09-25 14:02:12 | Alertmanager fires CRITICAL alert INC-2026-1042 (`KeyError` spike on POST /orders). |
| 2026-09-25 14:02:44 | Fourth `KeyError: None`; HTTP 500. |
| *(uncertain)* | Fix (`fix_001.diff`) applied to `victim-service/app.py`. Exact deployment time not recorded in available sources. |

---

## Evidence

**Source:** `incidents/incident_001.json`  
- Alert ID: INC-2026-1042  
- Error signature: `KeyError: None`  
- Traceback frames: `app.py:97` → `app.py:60`  
- Customer impact: ~18 % of order attempts returning HTTP 500 since 13:58 Z

**Source:** `incidents/incident_001_logs.txt`  
- Four HTTP 500 responses confirmed between 14:01:21 Z and 14:02:45 Z, all from
  source IP `10.4.2.18`.  
- All failures share the identical traceback pointing to `TAX_RATES[region]`.  
- Successful orders (ids 881–888) processed concurrently confirm the failure is
  path-specific, not a full service outage.

---

## Root Cause

Full analysis: `triage/reports/root_cause_001.md`

`OrderIn.region` is declared `Optional[str] = None`. When a client omits
`region` from the request body, Pydantic defaults it to `None`. This `None`
value is forwarded to `apply_tax(subtotal, order.region)` at `app.py:97`.
Inside `apply_tax`, the lookup:

```python
# app.py:60  (before fix)
rate = TAX_RATES[region]
```

uses `region` as a bare dictionary key. `TAX_RATES` contains only the keys
`"NP"`, `"US"`, and `"IN"`. Any other value — including `None` or an unknown
region string — raises `KeyError`, which propagates uncaught through
`create_order` and is converted by FastAPI to HTTP 500.

Unaffected: `GET /orders/{id}`, `GET /health`, and any `POST /orders` request
carrying a known region code.

---

## Fix Applied

**Diff:** `triage/fixes/fix_001.diff`  
**File changed:** `victim-service/app.py`, line 60  

```diff
-    rate = TAX_RATES[region]
+    rate = TAX_RATES.get(region, 0.0)
```

`dict.get(key, default)` returns the mapped rate for known regions (behaviour
unchanged) and returns `0.0` for `None` or any unrecognised region string,
allowing the order to complete successfully with zero tax applied. No schema
changes, no changes to `OrderIn`, and no other callers of `apply_tax` exist in
the codebase.

> **Note:** Silently applying 0 % tax to unrecognised region codes is the
> behaviour specified by the in-code comment on `app.py:59` and by both
> targeted test cases. If explicit rejection of unknown regions is later
> required, an `HTTPException` should be added — that would be a separate
> change.

---

## Verification

Pytest suite: `victim-service/tests/test_orders.py`

| State | Passed | Failed |
|---|---|---|
| **Before fix** | 5 | 4 |
| **After fix** | 7 | 2 |

The 2 tests newly passing after the fix are:
- `test_missing_region_defaults_tax_to_zero` — `region` omitted → HTTP 200, `tax == 0.0`
- `test_unknown_region_defaults_tax_to_zero` — `region="XX"` → HTTP 200, `tax == 0.0`

The 2 remaining failures are attributed to **incidents 002 and 003** and are
out of scope for this report.

---

## Prevention Suggestions

1. **Input validation at the boundary** — Make `region` a required field in
   `OrderIn`, or validate it against the known `TAX_RATES` keys at request
   parse time and return HTTP 422 immediately, before the order reaches
   `apply_tax`.

2. **Defensive lookup pattern** — Replace bare dict subscripts (`d[key]`) with
   `.get(key, default)` or explicit presence checks wherever external input is
   used as a dictionary key. This is a code-review checklist item.

3. **Test coverage for missing/invalid optional fields** — The two failing
   tests (`test_missing_region_defaults_tax_to_zero`,
   `test_unknown_region_defaults_tax_to_zero`) existed before the incident but
   were not green. Enforcing a green test gate on those tests pre-deployment
   would have blocked this regression.

4. **Alert latency** — The first HTTP 500 was logged at 14:01:20 Z; the
   CRITICAL alert fired at 14:02:12 Z (~52 s later). Review alerting thresholds
   to determine whether a faster trigger is appropriate for checkout endpoints.
