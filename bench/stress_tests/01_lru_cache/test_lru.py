from lru import LRU


def test_basic_get_put():
    c = LRU(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    assert c.get("b") == 2


def test_eviction_order():
    c = LRU(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)   # evicts 'a'
    assert c.get("a") is None
    assert c.get("b") == 2
    assert c.get("c") == 3


def test_get_promotes():
    c = LRU(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1   # 'a' now MRU
    c.put("c", 3)            # should evict 'b' not 'a'
    assert c.get("a") == 1
    assert c.get("b") is None


def test_put_updates_and_promotes():
    c = LRU(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 99)           # update + promote
    c.put("c", 3)            # evicts 'b'
    assert c.get("a") == 99
    assert c.get("b") is None
    assert c.get("c") == 3


def test_capacity_one():
    c = LRU(1)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") is None
    assert c.get("b") == 2


def test_missing_key():
    c = LRU(3)
    assert c.get("nope") is None
