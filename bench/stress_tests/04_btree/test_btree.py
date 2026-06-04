import random
from btree import BTree


def test_empty():
    b = BTree(3)
    assert b.in_order() == []
    assert b.search(42) is False


def test_basic_insert_search():
    b = BTree(3)
    for k in [10, 20, 5, 6, 12, 30, 7, 17]:
        b.insert(k)
    for k in [10, 20, 5, 6, 12, 30, 7, 17]:
        assert b.search(k), f"missing {k}"
    assert not b.search(999)


def test_in_order_sorted():
    b = BTree(3)
    keys = [50, 10, 70, 20, 60, 80, 30, 40, 90, 5, 15]
    for k in keys:
        b.insert(k)
    assert b.in_order() == sorted(keys)


def test_duplicates_ignored():
    b = BTree(2)
    for k in [5, 5, 5, 10, 10]:
        b.insert(k)
    assert b.in_order() == [5, 10]


def test_many_random():
    random.seed(42)
    b = BTree(4)
    keys = random.sample(range(10_000), 1000)
    for k in keys:
        b.insert(k)
    assert b.in_order() == sorted(keys)
    for k in keys:
        assert b.search(k)
    for k in random.sample(range(20_000, 30_000), 200):
        assert not b.search(k)


def test_small_degree():
    b = BTree(2)   # min degree 2 → forces lots of splits
    for k in range(50):
        b.insert(k)
    assert b.in_order() == list(range(50))
