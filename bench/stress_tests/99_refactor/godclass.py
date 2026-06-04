"""Order processing — pre-refactor. Deliberately a mess.
Single class doing parsing, validation, pricing, tax, persistence, and email.
All state mutated in-place. ~200 lines."""
import json
import re
from datetime import datetime


class OrderProcessor:
    TAX_RATES = {"US": 0.08, "DE": 0.19, "JP": 0.10, "IN": 0.18}
    DISCOUNT_CODES = {"WELCOME10": 0.10, "VIP25": 0.25, "STAFF50": 0.50}

    def __init__(self, db_path, smtp_host):
        self.db_path = db_path
        self.smtp_host = smtp_host
        self.order = None
        self.errors = []
        self.total = 0.0

    def process(self, raw_json):
        # parse
        try:
            self.order = json.loads(raw_json)
        except Exception as e:
            self.errors.append(f"parse: {e}")
            return False

        # validate
        if "customer" not in self.order:
            self.errors.append("missing customer"); return False
        c = self.order["customer"]
        if "email" not in c or not re.match(r"[^@]+@[^@]+\.[^@]+", c["email"]):
            self.errors.append("bad email"); return False
        if "country" not in c or c["country"] not in self.TAX_RATES:
            self.errors.append("unsupported country"); return False
        if "items" not in self.order or not self.order["items"]:
            self.errors.append("no items"); return False
        for i, item in enumerate(self.order["items"]):
            if "sku" not in item or "qty" not in item or "unit_price" not in item:
                self.errors.append(f"item {i} missing fields"); return False
            if item["qty"] <= 0 or item["unit_price"] < 0:
                self.errors.append(f"item {i} bad qty/price"); return False

        # subtotal
        subtotal = 0.0
        for item in self.order["items"]:
            subtotal += item["qty"] * item["unit_price"]

        # discount
        code = self.order.get("discount_code")
        if code:
            if code not in self.DISCOUNT_CODES:
                self.errors.append("bad discount"); return False
            subtotal = subtotal * (1 - self.DISCOUNT_CODES[code])

        # tax
        tax = subtotal * self.TAX_RATES[c["country"]]
        self.total = subtotal + tax

        # persist
        try:
            with open(self.db_path, "a") as f:
                f.write(json.dumps({
                    "ts": datetime.utcnow().isoformat(),
                    "email": c["email"],
                    "total": round(self.total, 2),
                }) + "\n")
        except Exception as e:
            self.errors.append(f"db: {e}"); return False

        # "send" email (stub)
        self._send_email(c["email"], self.total)
        return True

    def _send_email(self, to, total):
        # would connect to self.smtp_host
        print(f"[email] to={to} total={total:.2f}")
