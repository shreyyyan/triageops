"""Pytest suite for the victim service.

On the SEEDED (buggy) code, the four tests marked BUG 1 / BUG 2 / BUG 3 FAIL.
After incident 001's fix is applied (via the Bob IDE workflow), the suite
goes from 5 passed / 4 failed to 7 passed / 2 failed. The 2 remaining
failures are the deliberately-unfixed seeded incidents 002/003 (fixes
proposed only, in triage/fixes/). Nothing here is faked: run `pytest -v`
to see it.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app import app, ORDERS

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    """Isolate tests: fresh order store, live payments mode by default."""
    ORDERS.clear()
    monkeypatch.setenv("PAYMENTS_MODE", "live")
    yield
    ORDERS.clear()


def _order_payload(**overrides):
    payload = {
        "items": [{"sku": "WIDGET-1", "quantity": 2, "unit_price": 10.0}],
        "region": "NP",
    }
    payload.update(overrides)
    return payload


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_order_happy_path():
    r = client.post("/orders", json=_order_payload())
    assert r.status_code == 200
    body = r.json()
    # 2 x 10.00 = 20.00 subtotal; NP tax 13% = 2.60; total 22.60
    assert body["subtotal"] == 20.0
    assert body["tax"] == 2.6
    assert body["total"] == 22.6
    assert body["txn_id"].startswith("txn_")


def test_get_order_roundtrip():
    created = client.post("/orders", json=_order_payload()).json()
    r = client.get(f"/orders/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_order_404():
    r = client.get("/orders/99999")
    assert r.status_code == 404


# ---------------------------------------------------------------- BUG 1 ----
# Missing or unknown region must fall back to a 0.0 tax rate (HTTP 200).
# Seeded code raises KeyError -> HTTP 500.


def test_missing_region_defaults_tax_to_zero():
    payload = _order_payload()
    del payload["region"]
    r = client.post("/orders", json=payload)
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert body["tax"] == 0.0
    assert body["total"] == body["subtotal"]


def test_unknown_region_defaults_tax_to_zero():
    r = client.post("/orders", json=_order_payload(region="XX"))
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
    assert r.json()["tax"] == 0.0


# ---------------------------------------------------------------- BUG 2 ----
# A bulk discount (10% for total quantity > 10) must be applied exactly ONCE.
# Seeded code applies it twice: 12 x $10.00 -> 97.20 instead of 108.00.


def test_bulk_discount_applied_exactly_once():
    payload = _order_payload(
        items=[{"sku": "WIDGET-9", "quantity": 12, "unit_price": 10.0}]
    )
    r = client.post("/orders", json=payload)
    assert r.status_code == 200
    body = r.json()
    # 12 x 10.00 = 120.00, single 10% bulk discount -> 108.00
    assert body["subtotal"] == 108.0, f"double discount suspected: {body['subtotal']}"


# ---------------------------------------------------------------- BUG 3 ----
# PAYMENTS_MODE=sandbox must SIMULATE the charge (test txn id, HTTP 200),
# not decline it (HTTP 502).


def test_sandbox_mode_simulates_payment(monkeypatch):
    monkeypatch.setenv("PAYMENTS_MODE", "sandbox")
    r = client.post("/orders", json=_order_payload())
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert body["txn_id"].startswith("test_"), f"not a simulated txn: {body['txn_id']}"


def test_bulk_threshold_boundary_no_discount():
    # Exactly 10 units -> no bulk discount (threshold is strictly greater).
    payload = _order_payload(
        items=[{"sku": "WIDGET-9", "quantity": 10, "unit_price": 10.0}]
    )
    r = client.post("/orders", json=payload)
    assert r.status_code == 200
    assert r.json()["subtotal"] == 100.0
