import threading
from rl import TokenBucket


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t
    def __call__(self):
        return self.t
    def advance(self, dt):
        self.t += dt


def test_starts_full():
    c = FakeClock()
    b = TokenBucket(5, 1.0, now=c)
    for _ in range(5):
        assert b.try_acquire(1) is True
    assert b.try_acquire(1) is False


def test_refills():
    c = FakeClock()
    b = TokenBucket(5, 2.0, now=c)
    for _ in range(5):
        assert b.try_acquire(1)
    c.advance(1.0)            # +2 tokens
    assert b.try_acquire(1)
    assert b.try_acquire(1)
    assert not b.try_acquire(1)


def test_caps_at_capacity():
    c = FakeClock()
    b = TokenBucket(3, 100.0, now=c)
    for _ in range(3): b.try_acquire(1)
    c.advance(10.0)           # would be 1000 tokens
    for _ in range(3): assert b.try_acquire(1)
    assert not b.try_acquire(1)


def test_atomic_n_acquire():
    c = FakeClock()
    b = TokenBucket(5, 0.0, now=c)
    assert b.try_acquire(6) is False    # not enough; must NOT partially drain
    # all 5 should still be there
    for _ in range(5): assert b.try_acquire(1)


def test_thread_safety():
    c = FakeClock()
    b = TokenBucket(1000, 0.0, now=c)
    successes = []
    lock = threading.Lock()
    def worker():
        if b.try_acquire(1):
            with lock: successes.append(1)
    threads = [threading.Thread(target=worker) for _ in range(2000)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert sum(successes) == 1000   # never over-grant
