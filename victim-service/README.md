# Victim Service

The "production" application that TriageOps investigates. A small FastAPI
order-processing API. **All data here is synthetic.**

## Run it

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Endpoints:

- `POST /orders` — create an order: `{items, discount_code?, region?}`
- `GET /orders/{id}` — fetch an order
- `GET /health` — liveness check

## Run the tests

```bash
python -m pytest tests/ -v
```

## The three seeded bugs

1. **Crash (HTTP 500)** — `apply_tax()` does `TAX_RATES[region]`, raising
   `KeyError` when `region` is missing or unknown. Correct behaviour: fall
   back to a `0.0` tax rate.
2. **Silent logic bug (revenue leak)** — the 10% bulk discount for total
   quantity > 10 is applied twice: once per order line and once on the order
   subtotal. `12 x $10.00` totals `$97.20` instead of `$108.00`. No crash;
   only the test suite catches it. Correct behaviour: apply it exactly once.
3. **Config/env bug (HTTP 502)** — when `PAYMENTS_MODE=sandbox`, the
   simulated gateway raises `PaymentError` instead of simulating the charge,
   so every order fails. Correct behaviour: return a `test_`-prefixed
   transaction id without declining.

On the seeded code, the four bug-covering tests fail; everything else passes.
The Bob IDE workflow (see `../prompts/bob_tasks.md`) fixes incident 001's
bug: 5 passed / 4 failed → 7 passed / 2 failed. Incidents 002/003 have
proposed-only fixes in `triage/fixes/`; their tests remain failing by design,
which the dashboard shows honestly. That scoped red-to-green transition is
the demo's verification step.
