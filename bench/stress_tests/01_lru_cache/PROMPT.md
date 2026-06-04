Paste this into nimcode:

---

Implement an LRU cache in `lru.py`. Class name `LRU`, constructor takes `capacity: int`. Methods: `get(key) -> value | None` and `put(key, value) -> None`. Both must be O(1). Evict the least-recently-used key when over capacity. Touching a key (get or re-put) makes it most-recently-used.

Then run `./score.sh`. If it prints `FAIL`, read the failure, fix the code, and re-run. Only stop when `./score.sh` prints `PASS`. Do not modify the test file.
