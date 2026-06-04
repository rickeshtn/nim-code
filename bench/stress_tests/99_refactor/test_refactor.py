"""These tests must pass against the REFACTORED code without modification.
The refactor MUST split godclass.py into at least:
  - parser.py     (parse_order(raw_json) -> dict, raises ValueError)
  - validator.py  (validate(order) -> list[str] of errors)
  - pricing.py    (price(order, tax_rates, discount_codes) -> float)
  - repo.py       (OrderRepo with save(order, total))
  - notifier.py   (EmailNotifier with send(to, total))
  - service.py    (OrderService.process(raw_json) -> result dict)

OrderService.process must return a dict shaped:
  {"ok": bool, "total": float | None, "errors": list[str]}

It must NOT mutate self.errors / self.total / self.order between calls
(call it twice with different inputs — they must not leak)."""
import json
import os
import tempfile
import pytest

from service import OrderService

TAX_RATES = {"US": 0.08, "DE": 0.19, "JP": 0.10, "IN": 0.18}
DISCOUNT_CODES = {"WELCOME10": 0.10, "VIP25": 0.25, "STAFF50": 0.50}


@pytest.fixture
def svc(tmp_path):
    db = tmp_path / "orders.jsonl"
    from repo import OrderRepo
    from notifier import EmailNotifier
    return OrderService(
        repo=OrderRepo(str(db)),
        notifier=EmailNotifier(host="localhost"),
        tax_rates=TAX_RATES,
        discount_codes=DISCOUNT_CODES,
    ), db


def test_happy_path(svc):
    s, db = svc
    payload = json.dumps({
        "customer": {"email": "x@y.com", "country": "US"},
        "items": [{"sku": "A", "qty": 2, "unit_price": 10.0}],
    })
    r = s.process(payload)
    assert r["ok"] is True
    assert r["errors"] == []
    assert round(r["total"], 2) == 21.60   # 20 + 8% tax
    assert db.exists() and db.read_text().strip() != ""


def test_validation_errors_aggregate(svc):
    s, _ = svc
    r = s.process(json.dumps({"customer": {"email": "bad"}, "items": []}))
    assert r["ok"] is False
    assert r["total"] is None
    # multiple errors should be reported, not just first
    assert len(r["errors"]) >= 2


def test_discount_applied(svc):
    s, _ = svc
    r = s.process(json.dumps({
        "customer": {"email": "a@b.com", "country": "DE"},
        "items": [{"sku": "X", "qty": 1, "unit_price": 100.0}],
        "discount_code": "VIP25",
    }))
    assert r["ok"]
    # 100 * 0.75 = 75; 75 * 1.19 = 89.25
    assert round(r["total"], 2) == 89.25


def test_no_state_leak_between_calls(svc):
    s, _ = svc
    bad = json.dumps({"customer": {}, "items": []})
    good = json.dumps({
        "customer": {"email": "x@y.com", "country": "JP"},
        "items": [{"sku": "A", "qty": 1, "unit_price": 50.0}],
    })
    r1 = s.process(bad)
    r2 = s.process(good)
    assert r1["ok"] is False
    assert r2["ok"] is True
    assert r2["errors"] == []   # not contaminated by r1
