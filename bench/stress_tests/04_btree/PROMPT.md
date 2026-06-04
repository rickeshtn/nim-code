Paste into nimcode:

---

Implement a B-tree in `btree.py` with the following API:

    class BTree:
        def __init__(self, t: int):
            """t is the minimum degree (each non-root node has >= t-1 keys, <= 2t-1 keys)."""
        def insert(self, key: int) -> None
        def search(self, key: int) -> bool
        def in_order(self) -> list[int]:
            """Return all keys in sorted order."""

You must handle node splits correctly. No deletion required. Duplicate inserts are ignored.

Then run `./score.sh`. If it prints `FAIL`, fix and re-run. Only stop when it prints `PASS`. Do not modify the test file.
