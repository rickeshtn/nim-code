Paste into nimcode:

---

Read `godclass.py`. It is a 200-line monolith doing parsing, validation, pricing, persistence, and notification — all mutating shared state. Refactor it into focused modules:

- `parser.py` — `parse_order(raw_json: str) -> dict` (raises `ValueError` on bad JSON or missing top-level keys)
- `validator.py` — `validate(order: dict) -> list[str]` (returns all errors; does NOT short-circuit on first)
- `pricing.py` — `price(order: dict, tax_rates: dict, discount_codes: dict) -> float`
- `repo.py` — class `OrderRepo` with `__init__(db_path)` and `save(order, total)`
- `notifier.py` — class `EmailNotifier` with `__init__(host)` and `send(to, total)`
- `service.py` — class `OrderService` that composes the above and exposes `process(raw_json) -> {"ok": bool, "total": float|None, "errors": list[str]}`

Constraints:
- No shared mutable state between calls — calling `process` twice must not leak errors or totals.
- Validator must aggregate errors, not stop at the first one.
- The test file `test_refactor.py` must pass without modification.
- Delete `godclass.py` when done.

Then run `./score.sh`. If it prints `FAIL`, fix and re-run. Only stop when it prints `PASS`. Do not modify the test file.
