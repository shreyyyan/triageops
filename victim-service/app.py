"""Victim Service - a small FastAPI order-processing API.

This is the "production" application that TriageOps investigates.
It contains three intentionally SEEDED bugs (documented below and in README.md).
All data in this repository is synthetic and was generated for the hackathon.

Seeded bugs:
  BUG 1 (crash):      apply_tax() raises KeyError when `region` is missing or unknown.
                      POST /orders without a region -> HTTP 500 with a real traceback.
  BUG 2 (silent):     the bulk discount is applied TWICE (once per line, once on the
                      order subtotal) when total quantity > 10. No crash; the order
                      total is wrong (revenue leak). Caught by tests/test_orders.py.
  BUG 3 (config/env): when the PAYMENTS_MODE env var is "sandbox", charge_payment()
                      raises PaymentError instead of simulating the charge, so every
                      order fails with HTTP 502. Diagnosable from the service logs.
"""

import logging
import os
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("victim-service")

app = FastAPI(title="Victim Service")

TAX_RATES = {"NP": 0.13, "US": 0.07, "IN": 0.18}
BULK_THRESHOLD = 10
BULK_DISCOUNT_RATE = 0.10

ORDERS: Dict[int, dict] = {}
NEXT_ID = 1


class Item(BaseModel):
    sku: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0)


class OrderIn(BaseModel):
    items: List[Item]
    discount_code: Optional[str] = None
    region: Optional[str] = None


class PaymentError(Exception):
    """Raised when the (simulated) payment gateway declines a charge."""


def apply_tax(subtotal: float, region: Optional[str]) -> float:
    # BUG 1: KeyError when region is missing (None) or unknown.
    # Correct behaviour: fall back to a 0.0 rate.
    rate = TAX_RATES[region]
    return round(subtotal * rate, 2)


def line_subtotal(item: Item) -> float:
    return round(item.quantity * item.unit_price, 2)


def apply_bulk_discount(amount: float, total_quantity: int) -> float:
    if total_quantity > BULK_THRESHOLD:
        return round(amount * (1 - BULK_DISCOUNT_RATE), 2)
    return amount


def charge_payment(amount: float) -> str:
    mode = os.environ.get("PAYMENTS_MODE", "live")
    logger.info("charging payment amount=%.2f mode=%s", amount, mode)
    if mode == "sandbox":
        # BUG 3: sandbox mode should SIMULATE the charge (return a test txn id),
        # but instead it raises, failing every order with HTTP 502.
        raise PaymentError("sandbox gateway declined the charge")
    return "txn_%d" % int(round(amount * 100))


@app.post("/orders")
def create_order(order: OrderIn):
    global NEXT_ID
    total_quantity = sum(i.quantity for i in order.items)

    lines = [line_subtotal(i) for i in order.items]
    # BUG 2: bulk discount applied at line level ...
    lines = [apply_bulk_discount(lt, total_quantity) for lt in lines]
    subtotal = round(sum(lines), 2)
    # ... and then applied a SECOND time on the order subtotal. Revenue leak.
    # Correct behaviour: apply the bulk discount exactly once.
    subtotal = apply_bulk_discount(subtotal, total_quantity)

    tax = apply_tax(subtotal, order.region)
    total = round(subtotal + tax, 2)

    try:
        txn_id = charge_payment(total)
    except PaymentError as exc:
        logger.error("payment failed: %s", exc)
        raise HTTPException(status_code=502, detail="payment gateway error")

    order_id = NEXT_ID
    NEXT_ID += 1
    record = {
        "id": order_id,
        "items": [i.model_dump() for i in order.items],
        "discount_code": order.discount_code,
        "region": order.region,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "txn_id": txn_id,
    }
    ORDERS[order_id] = record
    logger.info("order created id=%d total=%.2f", order_id, total)
    return record


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail="order not found")
    return ORDERS[order_id]


@app.get("/health")
def health():
    return {"status": "ok"}
