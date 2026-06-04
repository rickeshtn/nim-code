Paste into nimcode:

---

Implement a thread-safe token-bucket rate limiter in `rl.py`.

    class TokenBucket:
        def __init__(self, capacity: int, refill_per_sec: float, now: Callable[[], float] = time.monotonic):
            ...
        def try_acquire(self, n: int = 1) -> bool:
            """Return True if n tokens were available and consumed; False otherwise. Never blocks."""

Bucket starts full. Refills at `refill_per_sec` tokens per second up to `capacity`. The `now` callable is for tests to inject a fake clock. Must be safe to call from multiple threads.

Then run `./score.sh`. If it prints `FAIL`, fix and re-run. Only stop when it prints `PASS`. Do not modify the test file.
